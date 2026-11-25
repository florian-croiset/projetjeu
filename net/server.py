"""Game server: sockets, sessions and the fixed-rate simulation loop.

Thread layout
-------------
* accept thread       - accepts TCP connections, performs the handshake.
* reader thread / TCP client - decodes incoming frames into ``self._inbox``.
* writer thread / TCP client - sends queued frames (a slow client never blocks
  the simulation; stale snapshots are coalesced).
* game thread         - the ONLY thread touching the ``World``: drains the
  inbox, polls UDP, steps the simulation at ``TICK_RATE`` Hz and broadcasts.

LAN play is unchanged: clients connect to ``<host ip>:TCP_PORT`` (handshake +
fallback transport) and, when possible, switch gameplay traffic to
``UDP_PORT`` using the one-time token received over TCP.
"""

import collections
import queue
import secrets
import socket
import threading
import time
import traceback

from core.world import World
from net import codec, framing, protocol as P
from net import udp
from settings import USE_UDP, TCP_PORT, UDP_PORT

BIND_HOST = "0.0.0.0"
MAX_CLIENT_FRAME = 64 * 1024          # clients only send tiny messages
HELLO_TIMEOUT_S = 5.0
SILENCE_TIMEOUT_MS = 10_000
UDP_TOKEN_TTL_MS = 30_000
UDP_MAX_HANDSHAKES_PER_IP = 10
UDP_HANDSHAKE_WINDOW_MS = 10_000
MAX_MESSAGES_PER_SECOND = 1500
MAX_TICKS_PER_ITERATION = 5
TICK_DT = 1.0 / P.TICK_RATE
STATE_INTERVAL_TICKS = max(1, P.TICK_RATE // P.STATE_RATE)


class Session:
    """One connected client."""

    def __init__(self, pid, sock, addr):
        self.id = pid
        self.sock = sock
        self.addr = addr
        self.closed = False
        self.joined = False

        # TCP outgoing: reliable frames in order + one coalesced snapshot slot
        self._out = collections.deque()
        self._pending_snapshot = None
        self._cond = threading.Condition()

        self.udp = None                    # UdpConnection once the UDP handshake succeeded
        self.udp_token = None
        self.sent_state = {}               # stream key -> (payload bytes, sent at ms)
        self.last_rx_ms = udp.now_ms()
        self._budget = MAX_MESSAGES_PER_SECOND
        self._budget_ms = udp.now_ms()

    # -- TCP output --------------------------------------------------------

    def send_tcp(self, type_, payload, droppable=False):
        with self._cond:
            if self.closed:
                return
            if droppable:
                self._pending_snapshot = (type_, payload)
            else:
                self._out.append((type_, payload))
            self._cond.notify()

    def writer_loop(self):
        try:
            while True:
                with self._cond:
                    while not self._out and self._pending_snapshot is None and not self.closed:
                        self._cond.wait()
                    if self.closed:
                        return
                    frames = list(self._out)
                    self._out.clear()
                    snapshot, self._pending_snapshot = self._pending_snapshot, None
                if snapshot is not None:
                    frames.append(snapshot)
                self.sock.sendall(b''.join(framing.encode_frame([t, p]) for t, p in frames))
        except (OSError, codec.CodecError):
            pass
        finally:
            self.close()

    def close(self):
        with self._cond:
            if self.closed:
                return
            self.closed = True
            self._cond.notify_all()
        try:
            self.sock.close()
        except OSError:
            pass

    def allow_message(self, now_ms):
        """Token bucket against message floods."""
        elapsed = now_ms - self._budget_ms
        if elapsed >= 1000:
            self._budget = MAX_MESSAGES_PER_SECOND
            self._budget_ms = now_ms
        self._budget -= 1
        return self._budget >= 0


class Server:
    def __init__(self, slot_id, new_game, relay_host="", relay_port=7777, base_dir=None,
                 tcp_port=None, udp_port=None, bind_host=BIND_HOST, enable_pathfinding=True,
                 save_enabled=True):
        import os
        import sys
        if base_dir is None:
            if getattr(sys, 'frozen', False):
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.world = World(base_dir, slot_id, new_game,
                           enable_pathfinding=enable_pathfinding, save_enabled=save_enabled)

        self.running = False
        self.room_code = None
        self.relay_host = relay_host
        self.relay_port = relay_port

        self._inbox = queue.SimpleQueue()
        self._sessions = {}                    # id -> Session
        self._free_ids = list(range(P.MAX_PLAYERS))
        self._ids_lock = threading.Lock()
        self._udp_by_addr = {}                 # (ip, port) -> Session
        self._udp_tokens = {}                  # token -> (Session, deadline ms)
        self._udp_attempts = {}                # ip -> [ms, ...]
        self._state_bytes = {}
        self._threads = []

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((bind_host, TCP_PORT if tcp_port is None else tcp_port))
        self.tcp_port = self.tcp_socket.getsockname()[1]
        print(f"[SERVER] TCP listening on {bind_host}:{self.tcp_port}")

        self.udp_endpoint = None
        if USE_UDP:
            try:
                self.udp_endpoint = udp.UdpEndpoint(bind_host,
                                                    UDP_PORT if udp_port is None else udp_port)
                print(f"[SERVER] UDP listening on port {self.udp_endpoint.bind_port}")
            except OSError as exc:
                print(f"[SERVER] UDP unavailable ({exc}); TCP only")

    @property
    def udp_port(self):
        return self.udp_endpoint.bind_port if self.udp_endpoint else None

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start all threads and return immediately."""
        self.running = True
        self.tcp_socket.listen()
        self._spawn(self._game_loop, "game")
        self._spawn(self._accept_loop, "accept")
        if self.relay_host:
            self._spawn(self._relay_loop, "relay")

    def _spawn(self, target, name, *args):
        t = threading.Thread(target=target, args=args, name=f"server-{name}", daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self):
        if not self.running:
            return
        self.running = False
        try:
            self.tcp_socket.close()
        except OSError:
            pass
        for session in list(self._sessions.values()):
            session.close()
        if self.udp_endpoint is not None:
            self.udp_endpoint.close()
        for t in self._threads:
            if t is not threading.current_thread():
                t.join(timeout=2.0)
        self.world.close()
        print("[SERVER] stopped")

    # ------------------------------------------------------------------
    #  Accepting clients
    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.tcp_socket.accept()
            except OSError:
                break
            self._spawn(self._handshake, "handshake", sock, addr)

    def _handshake(self, sock, addr):
        """Runs in its own short-lived thread so a slow client cannot block accepts."""
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._ids_lock:
                pid = self._free_ids.pop(0) if self._free_ids else None
            if pid is None:
                framing.send_message(sock, {'error': 'SERVER_FULL', 'proto': P.PROTOCOL_VERSION})
                sock.close()
                return
            session = Session(pid, sock, addr)
            token = None
            if self.udp_endpoint is not None:
                token = secrets.token_hex(32)
                session.udp_token = token
            framing.send_message(sock, {
                'proto': P.PROTOCOL_VERSION, 'id': pid,
                'udp_token': token, 'udp_port': self.udp_port,
            })
            sock.settimeout(HELLO_TIMEOUT_S)
            hello = framing.recv_message(sock, MAX_CLIENT_FRAME)
            ok = (isinstance(hello, list) and len(hello) == 2 and hello[0] == P.T_ACTION)
            action = codec.decode(hello[1]) if ok else None
            if not isinstance(action, dict) or action.get('a') != 'hello':
                raise ValueError("bad hello")
            sock.settimeout(None)
            self._inbox.put(('joined', session, action))
            self._spawn(self._reader_loop, f"reader{pid}", session)
            self._spawn(session.writer_loop, f"writer{pid}")
            print(f"[SERVER] player {pid} connected from {addr}")
        except (OSError, ValueError, EOFError, codec.CodecError) as exc:
            print(f"[SERVER] handshake with {addr} failed: {exc}")
            try:
                sock.close()
            except OSError:
                pass
            if 'session' in locals():
                self._release_id(session.id)

    def _release_id(self, pid):
        with self._ids_lock:
            if pid not in self._free_ids:
                self._free_ids.append(pid)
                self._free_ids.sort()

    def _reader_loop(self, session):
        try:
            while self.running and not session.closed:
                frame = framing.recv_message(session.sock, MAX_CLIENT_FRAME)
                if (isinstance(frame, list) and len(frame) == 2
                        and type(frame[0]) is int and isinstance(frame[1], bytes)):
                    self._inbox.put(('msg', session, frame[0], frame[1]))
        except (OSError, EOFError, ValueError):
            pass
        finally:
            self._inbox.put(('closed', session))
            session.close()

    # ------------------------------------------------------------------
    #  Relay (room code) hosting
    # ------------------------------------------------------------------

    def _relay_loop(self):
        from net import relay_client
        try:
            ctrl, self.room_code = relay_client.relay_create_room(self.relay_host, self.relay_port)
            print(f"[SERVER] relay connected - room code: {self.room_code}")
        except Exception as exc:
            print(f"[SERVER] cannot reach relay {self.relay_host}:{self.relay_port}: {exc}")
            return
        while self.running:
            try:
                slot = relay_client.relay_wait_client(ctrl)
                sock = relay_client.relay_open_channel_data(self.relay_host, self.relay_port,
                                                            self.room_code, slot)
                self._spawn(self._handshake, "handshake", sock, ("relay", slot))
            except EOFError:
                print("[SERVER] relay connection lost")
                break
            except Exception as exc:
                print(f"[SERVER] relay error: {exc}")
                break
        self.room_code = None

    # ------------------------------------------------------------------
    #  Game thread
    # ------------------------------------------------------------------

    def _game_loop(self):
        next_tick = time.perf_counter()
        errors = 0
        while self.running:
            now = time.perf_counter()
            ticks = 0
            while now >= next_tick and ticks < MAX_TICKS_PER_ITERATION and self.running:
                try:
                    self._pump()
                    self.world.step()
                    self._broadcast()
                except Exception:
                    errors += 1
                    if errors <= 5:
                        traceback.print_exc()
                next_tick += TICK_DT
                ticks += 1
            if now - next_tick > 0.25:          # hopelessly behind: skip instead of spiralling
                next_tick = now
            try:
                self._pump()
                self._housekeeping()
            except Exception:
                errors += 1
                if errors <= 5:
                    traceback.print_exc()
            remaining = next_tick - time.perf_counter()
            if remaining > 0:
                time.sleep(min(remaining, 0.004))

    # -- inbound -----------------------------------------------------------

    def _pump(self):
        """Drain TCP inbox and UDP socket, applying everything to the world."""
        now_ms = udp.now_ms()
        if self.udp_endpoint is not None:
            for data, addr in self.udp_endpoint.poll():
                self._on_datagram(data, addr, now_ms)
            for session in list(self._udp_by_addr.values()):
                for type_, payload in session.udp.drain():
                    session.last_rx_ms = now_ms
                    self._on_message(session, type_, payload, now_ms)
        while True:
            try:
                item = self._inbox.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == 'joined':
                self._on_joined(item[1], item[2])
            elif kind == 'msg':
                session = item[1]
                if session.id in self._sessions:
                    session.last_rx_ms = now_ms
                    self._on_message(session, item[2], item[3], now_ms)
            elif kind == 'closed':
                self._on_closed(item[1])

    def _on_joined(self, session, hello):
        pid = session.id
        self._sessions[pid] = session
        self.world.add_player(pid)
        self.world.set_profile(pid, hello.get('nickname'), hello.get('skin'))
        if session.udp_token:
            self._udp_tokens[session.udp_token] = (session, udp.now_ms() + UDP_TOKEN_TTL_MS)
        session.joined = True

    def _on_closed(self, session):
        if self._sessions.get(session.id) is not session:
            return
        pid = session.id
        del self._sessions[pid]
        if session.udp is not None:
            self._udp_by_addr.pop(session.udp.addr, None)
        if session.udp_token:
            self._udp_tokens.pop(session.udp_token, None)
        self.world.remove_player(pid)
        self._release_id(pid)
        print(f"[SERVER] player {pid} disconnected")

    def _on_datagram(self, data, addr, now_ms):
        session = self._udp_by_addr.get(addr)
        if session is not None:
            session.udp.receive_datagram(data)
            return
        # Unknown peer: only a HANDSHAKE carrying a valid one-time token is accepted.
        if len(data) < udp.HEADER_SIZE or len(data) > 512:
            return
        _, _, _, channel, type_ = udp.HEADER.unpack_from(data)
        if channel != udp.CH_CONTROL or type_ != P.T_HANDSHAKE:
            return
        if not self._udp_rate_ok(addr[0], now_ms):
            return
        try:
            body = codec.decode(data[udp.HEADER_SIZE:])
            token = body['token']
        except (codec.CodecError, KeyError, TypeError):
            return
        entry = self._udp_tokens.pop(token, None) if isinstance(token, str) else None
        if entry is None or now_ms > entry[1]:
            return
        session = entry[0]
        if session.closed:
            return
        conn = udp.UdpConnection(self.udp_endpoint, addr, heartbeat_ms=P.HEARTBEAT_MS,
                                 timeout_ms=P.UDP_TIMEOUT_MS)
        conn.receive_datagram(data)
        conn.send_control(P.T_HANDSHAKE_ACK, codec.encode({'id': session.id}))
        session.udp = conn
        self._udp_by_addr[addr] = session
        print(f"[SERVER] player {session.id}: UDP active from {addr}")

    def _udp_rate_ok(self, ip, now_ms):
        history = self._udp_attempts.setdefault(ip, [])
        horizon = now_ms - UDP_HANDSHAKE_WINDOW_MS
        history[:] = [t for t in history if t >= horizon]
        if len(history) >= UDP_MAX_HANDSHAKES_PER_IP:
            return False
        history.append(now_ms)
        return True

    def _on_message(self, session, type_, payload, now_ms):
        if not session.allow_message(now_ms):
            return
        pid = session.id
        if type_ == P.T_INPUT:
            self.world.push_inputs(pid, P.unpack_inputs(payload))
        elif type_ == P.T_ACTION:
            try:
                action = codec.decode(payload)
            except codec.CodecError:
                return
            if not isinstance(action, dict):
                return
            if action.get('a') == 'profile':
                self.world.set_profile(pid, action.get('nickname'), action.get('skin'))
            else:
                self.world.handle_action(pid, action)
        elif type_ == P.T_PING:
            try:
                ping = codec.decode(payload)
                client_ms = ping['c']
            except (codec.CodecError, KeyError, TypeError):
                return
            reply = codec.encode({'c': client_ms, 's': int(self.world.time_ms)})
            self._send(session, P.T_PONG, reply, reliable=False)

    # -- housekeeping ----------------------------------------------------

    def _housekeeping(self):
        now_ms = udp.now_ms()
        for session in list(self._sessions.values()):
            conn = session.udp
            if conn is not None:
                conn.tick(now_ms)
                if not conn.alive:
                    print(f"[SERVER] player {session.id}: UDP timeout, falling back to TCP")
                    self._udp_by_addr.pop(conn.addr, None)
                    session.udp = None
            if now_ms - session.last_rx_ms > SILENCE_TIMEOUT_MS:
                print(f"[SERVER] player {session.id}: silent for too long")
                session.close()
                self._on_closed(session)
        if len(self._udp_tokens) > 64:
            self._udp_tokens = {k: v for k, v in self._udp_tokens.items() if v[1] > now_ms}

    # -- outbound ----------------------------------------------------------

    def _send(self, session, type_, payload, reliable, key=0, droppable=False):
        conn = session.udp
        if conn is not None and conn.alive:
            if reliable:
                conn.send_reliable(type_, payload, key)
            else:
                conn.send_unreliable(type_, payload)
        else:
            session.send_tcp(type_, payload, droppable=droppable and not reliable)

    def _broadcast(self):
        world = self.world
        sessions = [s for s in self._sessions.values() if s.joined and not s.closed]
        if not sessions:
            world.pop_events()
            return

        # Events: sounds etc. (targeted events only go to their recipient)
        events = world.pop_events()
        for session in sessions:
            if session.id in world.vis_full_pending:
                world.vis_full_pending.discard(session.id)
                events_for = [(None, {'e': 'vis_full', 'b': world.vis_full_bits(session.id),
                                      'w': world.game_map.width_map, 'h': world.game_map.height_map})]
            else:
                events_for = []
            delta = world.pop_vis_delta(session.id)
            if delta:
                events_for.append((None, {'e': 'vis', 't': delta}))
            events_for += [(t, e) for t, e in events if t is None or t == session.id]
            if events_for:
                self._send(session, P.T_EVENTS, codec.encode([e for _, e in events_for]),
                           reliable=True)

        # Snapshot: everything needed to render + this client's own physics state
        for session in sessions:
            self._send(session, P.T_SNAPSHOT, world.snapshot_for(session.id),
                       reliable=False, droppable=True)

        # "Latest state" streams, only when changed (or refreshed)
        if world.tick % STATE_INTERVAL_TICKS == 0:
            now_ms = udp.now_ms()
            streams = ((P.KEY_PLAYERS, world.state_players),
                       (P.KEY_ENEMIES, world.state_enemies),
                       (P.KEY_WORLD, world.state_world))
            for key, build in streams:
                payload = codec.encode(dict(build(), k=key))
                for session in sessions:
                    last = session.sent_state.get(key)
                    if (last is None or last[0] != payload
                            or now_ms - last[1] >= P.STATE_REFRESH_MS):
                        session.sent_state[key] = (payload, now_ms)
                        self._send(session, P.T_STATE, payload, reliable=True, key=key)
