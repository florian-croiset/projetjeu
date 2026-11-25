"""Client side of the network layer (no pygame, no game logic).

``NetClient`` connects over TCP (handshake + fallback transport), then tries to
switch gameplay traffic to UDP. The game loop only calls :meth:`poll`,
:meth:`send_inputs` and :meth:`send_action`; transport details (UDP vs TCP,
fragmentation, retransmission, clock sync) stay in here.
"""

import collections
import queue
import socket
import threading
import time

from net import codec, framing, protocol as P
from net import udp

CONNECT_TIMEOUT_S = 5.0
HANDSHAKE_RETRY_S = 0.2
PING_INTERVAL_MS = 500
MAX_TCP_BACKLOG = 6          # queued unreliable frames before older ones are dropped


class ConnectError(Exception):
    """Connection failed. ``code`` is one of: refused, timeout, address, full,
    version, protocol, network."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class NetClient:
    def __init__(self):
        self.sock = None
        self.my_id = -1
        self.error = None
        self.rtt_ms = 0.0
        self.udp_active = False
        self.server_host = None

        self._endpoint = None
        self._conn = None
        self._tcp_in = queue.SimpleQueue()
        self._tcp_out = collections.deque()
        self._tcp_cond = threading.Condition()
        self._closed = False
        self._next_ping_ms = 0
        self._threads = []

    # ------------------------------------------------------------------
    #  Connecting
    # ------------------------------------------------------------------

    def connect(self, host, port, nickname, skin, want_udp=True):
        """Open the TCP connection and complete the handshake."""
        self.server_host = host
        try:
            sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT_S)
        except socket.timeout as exc:
            raise ConnectError("timeout", f"{host}:{port}") from exc
        except ConnectionRefusedError as exc:
            raise ConnectError("refused", f"{host}:{port}") from exc
        except socket.gaierror as exc:
            raise ConnectError("address", host) from exc
        except OSError as exc:
            raise ConnectError("network", str(exc)) from exc
        self.adopt_socket(sock, nickname, skin, want_udp=want_udp, host=host)

    def adopt_socket(self, sock, nickname, skin, want_udp=False, host=None):
        """Handshake over an already connected stream socket (direct or relay)."""
        self.sock = sock
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        sock.settimeout(CONNECT_TIMEOUT_S)
        try:
            info = framing.recv_message(sock, 64 * 1024)
        except socket.timeout as exc:
            raise ConnectError("timeout", "no handshake from server") from exc
        except (OSError, EOFError, ValueError) as exc:
            raise ConnectError("network", str(exc)) from exc
        if not isinstance(info, dict):
            raise ConnectError("protocol", "bad handshake")
        if info.get('error') == 'SERVER_FULL':
            raise ConnectError("full")
        if info.get('proto') != P.PROTOCOL_VERSION:
            raise ConnectError("version", f"server={info.get('proto')} client={P.PROTOCOL_VERSION}")
        self.my_id = info['id']
        hello = codec.encode({'a': 'hello', 'proto': P.PROTOCOL_VERSION,
                              'nickname': nickname, 'skin': skin})
        try:
            framing.send_message(sock, [P.T_ACTION, hello])
        except OSError as exc:
            raise ConnectError("network", str(exc)) from exc
        sock.settimeout(None)
        self._start_thread(self._reader_loop, "net-reader")
        self._start_thread(self._writer_loop, "net-writer")
        if want_udp and info.get('udp_token') and info.get('udp_port') and host:
            self._try_udp(host, info['udp_port'], info['udp_token'])

    def _start_thread(self, target, name):
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        self._threads.append(t)

    def _try_udp(self, host, port, token):
        try:
            endpoint = udp.UdpEndpoint("0.0.0.0", 0)
        except OSError as exc:
            print(f"[NET] cannot open UDP socket: {exc}")
            return
        addr = (host, port)
        conn = udp.UdpConnection(endpoint, addr, heartbeat_ms=P.HEARTBEAT_MS,
                                 timeout_ms=P.UDP_TIMEOUT_MS)
        handshake = codec.encode({'token': token})
        deadline = time.monotonic() + P.UDP_HANDSHAKE_TIMEOUT_MS / 1000.0
        next_send = 0.0
        while time.monotonic() < deadline and not self._closed:
            now = time.monotonic()
            if now >= next_send:
                conn.send_control(P.T_HANDSHAKE, handshake)
                next_send = now + HANDSHAKE_RETRY_S
            for data, src in endpoint.poll():
                if src[0] == addr[0] and src[1] == addr[1]:
                    conn.receive_datagram(data)
            for type_, _payload in conn.drain():
                if type_ == P.T_HANDSHAKE_ACK:
                    self._endpoint, self._conn, self.udp_active = endpoint, conn, True
                    return
            time.sleep(0.01)
        print("[NET] UDP handshake failed, staying on TCP")
        endpoint.close()

    # ------------------------------------------------------------------
    #  TCP threads
    # ------------------------------------------------------------------

    def _reader_loop(self):
        try:
            while not self._closed:
                frame = framing.recv_message(self.sock)
                if (isinstance(frame, list) and len(frame) == 2
                        and type(frame[0]) is int and isinstance(frame[1], bytes)):
                    self._tcp_in.put((frame[0], frame[1]))
        except (OSError, EOFError, ValueError) as exc:
            if not self._closed:
                self.error = f"connection lost ({exc})"
        finally:
            self._tcp_in.put(None)

    def _writer_loop(self):
        try:
            while True:
                with self._tcp_cond:
                    while not self._tcp_out and not self._closed:
                        self._tcp_cond.wait()
                    if self._closed:
                        return
                    frames = list(self._tcp_out)
                    self._tcp_out.clear()
                self.sock.sendall(b''.join(framing.encode_frame([t, p]) for t, p in frames))
        except OSError as exc:
            if not self._closed:
                self.error = f"connection lost ({exc})"

    def _send_tcp(self, type_, payload, droppable=False):
        with self._tcp_cond:
            if droppable:
                # keep only the freshest few input frames when the link is slow
                while len(self._tcp_out) >= MAX_TCP_BACKLOG:
                    self._tcp_out.popleft()
            self._tcp_out.append((type_, payload))
            self._tcp_cond.notify()

    # ------------------------------------------------------------------
    #  Sending
    # ------------------------------------------------------------------

    def send_inputs(self, last_seq, bits):
        payload = P.pack_inputs(last_seq, bits)
        if self.udp_active:
            self._conn.send_unreliable(P.T_INPUT, payload)
        else:
            self._send_tcp(P.T_INPUT, payload, droppable=True)

    def send_action(self, action: dict):
        payload = codec.encode(action)
        if self.udp_active:
            self._conn.send_reliable(P.T_ACTION, payload)
        else:
            self._send_tcp(P.T_ACTION, payload)

    # ------------------------------------------------------------------
    #  Receiving
    # ------------------------------------------------------------------

    def poll(self):
        """Non-blocking. Returns decoded messages ``[(kind, data), ...]`` with
        kind in ``snapshot`` | ``state`` | ``events``."""
        raw = []
        now = udp.now_ms()
        if self.udp_active:
            conn = self._conn
            for data, src in self._endpoint.poll():
                if src[0] == conn.addr[0] and src[1] == conn.addr[1]:
                    conn.receive_datagram(data)
            conn.tick(now)
            raw.extend(conn.drain())
            self.rtt_ms = conn.rtt_ms or self.rtt_ms
            if not conn.alive:
                print("[NET] UDP timed out, falling back to TCP")
                self.udp_active = False
        while True:
            try:
                item = self._tcp_in.get_nowait()
            except queue.Empty:
                break
            if item is None:
                if self.error is None:
                    self.error = "connection closed by server"
                break
            raw.append(item)
        if now >= self._next_ping_ms and not self._closed:
            self._next_ping_ms = now + PING_INTERVAL_MS
            ping = codec.encode({'c': now})
            if self.udp_active:
                self._conn.send_unreliable(P.T_PING, ping)
            else:
                self._send_tcp(P.T_PING, ping, droppable=True)
        return self._decode(raw, now)

    def _decode(self, raw, now):
        out = []
        for type_, payload in raw:
            try:
                if type_ == P.T_SNAPSHOT:
                    out.append(('snapshot', P.unpack_snapshot(payload)))
                elif type_ == P.T_STATE:
                    state = codec.decode(payload)
                    if isinstance(state, dict):
                        out.append(('state', state))
                elif type_ == P.T_EVENTS:
                    events = codec.decode(payload)
                    if isinstance(events, list):
                        out.append(('events', events))
                elif type_ == P.T_PONG:
                    pong = codec.decode(payload)
                    sample = now - pong['c']
                    if 0 <= sample < 10_000:
                        self.rtt_ms = sample if self.rtt_ms == 0 else \
                            self.rtt_ms + 0.2 * (sample - self.rtt_ms)
            except (ValueError, KeyError, TypeError):
                continue                     # malformed message: ignore it
        return out

    # ------------------------------------------------------------------

    def close(self):
        if self._closed:
            return
        self._closed = True
        with self._tcp_cond:
            self._tcp_cond.notify_all()
        if self._conn is not None:
            try:
                self._conn.send_control(P.T_DISCONNECT)
            except OSError:
                pass
        if self._endpoint is not None:
            self._endpoint.close()
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
