"""Standalone TCP relay for room-code play (no port forwarding / VPN needed).

Usage::

    python -m net.relay_server [port]

Protocol: every connection starts with ONE JSON line (max ``MAX_LINE`` bytes)::

    {"cmd": "host"}                          -> {"code": "ABCDEF"}   (control channel, stays open)
    {"cmd": "join", "code": "ABCDEF"}        -> {"status": "bridged"} once the host answered
    {"cmd": "data", "code": ..., "slot": n}  -> {"status": "bridged"} (host side of one client)

After ``bridged`` the relay just copies bytes both ways; the game protocol
(``net.framing``) runs unchanged on top of it. The relay never looks at, nor
trusts, the bridged data. Relay sessions are TCP-only.

Rooms live as long as their host keeps the control channel open. The host sends
a keep-alive byte every ``KEEPALIVE_S`` seconds; a room whose host is silent for
``HOST_TIMEOUT_S`` is closed.
"""

import json
import secrets
import socket
import string
import sys
import threading
import time

MAX_LINE = 1024
COMMAND_TIMEOUT_S = 10.0
BRIDGE_WAIT_S = 15.0
HOST_TIMEOUT_S = 120.0
CLEANUP_INTERVAL_S = 15.0
MAX_ROOMS = 500
MAX_SLOTS_PER_ROOM = 8
MAX_CONNECTIONS_PER_IP = 24
MAX_FAILED_JOINS_PER_MINUTE = 20
CHUNK = 8192


class LineError(ValueError):
    pass


def recv_line(sock) -> str:
    """Read one ``\\n``-terminated line without consuming a single byte more
    (the stream continues with binary data after the handshake lines)."""
    buf = bytearray()
    while True:
        byte = sock.recv(1)
        if not byte:
            raise EOFError("connection closed")
        if byte == b'\n':
            return buf.decode('utf-8', errors='replace')
        buf += byte
        if len(buf) > MAX_LINE:
            raise LineError("line too long")


def send_json(sock, obj):
    sock.sendall(json.dumps(obj).encode('utf-8') + b'\n')


class Room:
    def __init__(self, code, host_ctrl):
        self.code = code
        self.host_ctrl = host_ctrl
        self.next_slot = 1
        self.slots = {}                      # slot id -> {"client": sock, "host_data": sock|None}
        self.last_host_activity = time.monotonic()
        self.cond = threading.Condition()


class RelayServer:
    def __init__(self, port=7777, bind_host="0.0.0.0"):
        self.port = port
        self.bind_host = bind_host
        self.rooms = {}
        self.lock = threading.Lock()
        self._server_socket = None
        self._running = False
        self._connections_per_ip = {}
        self._failed_joins = {}

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.bind_host, self.port))
        self.port = self._server_socket.getsockname()[1]
        self._server_socket.listen()
        self._running = True
        print(f"[RELAY] listening on {self.bind_host}:{self.port}")
        threading.Thread(target=self._cleanup_loop, daemon=True).start()
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def serve_forever(self):
        self.start()
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self._running = False
        with self.lock:
            codes = list(self.rooms)
        for code in codes:
            self._close_room(code)
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        print("[RELAY] stopped")

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
            except OSError:
                break
            ip = addr[0]
            with self.lock:
                count = self._connections_per_ip.get(ip, 0)
                if count >= MAX_CONNECTIONS_PER_IP:
                    conn.close()
                    continue
                self._connections_per_ip[ip] = count + 1
            threading.Thread(target=self._serve_connection, args=(conn, ip), daemon=True).start()

    def _serve_connection(self, sock, ip):
        try:
            sock.settimeout(COMMAND_TIMEOUT_S)
            msg = json.loads(recv_line(sock))
            if not isinstance(msg, dict):
                raise LineError("command must be an object")
            cmd = msg.get("cmd")
            if cmd == "host":
                self._cmd_host(sock)
            elif cmd == "join":
                self._cmd_join(sock, ip, str(msg.get("code", "")))
            elif cmd == "data":
                self._cmd_data(sock, str(msg.get("code", "")), msg.get("slot"))
            else:
                send_json(sock, {"error": "unknown command"})
                sock.close()
        except (EOFError, OSError, ValueError):
            try:
                sock.close()
            except OSError:
                pass
        finally:
            with self.lock:
                n = self._connections_per_ip.get(ip, 1) - 1
                if n <= 0:
                    self._connections_per_ip.pop(ip, None)
                else:
                    self._connections_per_ip[ip] = n

    # ------------------------------------------------------------------
    #  Commands
    # ------------------------------------------------------------------

    def _cmd_host(self, sock):
        with self.lock:
            if len(self.rooms) >= MAX_ROOMS:
                send_json(sock, {"error": "relay is full"})
                sock.close()
                return
            for _ in range(100):
                code = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(6))
                if code not in self.rooms:
                    break
            else:
                send_json(sock, {"error": "cannot allocate a room code"})
                sock.close()
                return
            room = Room(code, sock)
            self.rooms[code] = room
        send_json(sock, {"code": code})
        print(f"[RELAY] room {code} created")
        # The control channel stays open; any byte from the host is a keep-alive.
        try:
            sock.settimeout(HOST_TIMEOUT_S)
            while sock.recv(64):
                room.last_host_activity = time.monotonic()
        except (OSError, EOFError):
            pass
        finally:
            print(f"[RELAY] room {code} closed (host gone)")
            self._close_room(code)

    def _cmd_join(self, sock, ip, code):
        code = code.upper().strip()
        with self.lock:
            room = self.rooms.get(code)
            recent = [t for t in self._failed_joins.get(ip, []) if t > time.monotonic() - 60]
            if room is None:
                recent.append(time.monotonic())
            self._failed_joins[ip] = recent
            if len(recent) > MAX_FAILED_JOINS_PER_MINUTE:
                sock.close()
                return
        if room is None:
            send_json(sock, {"error": "room not found"})
            sock.close()
            return
        with room.cond:
            if len(room.slots) >= MAX_SLOTS_PER_ROOM:
                send_json(sock, {"error": "room is full"})
                sock.close()
                return
            slot_id = room.next_slot
            room.next_slot += 1
            room.slots[slot_id] = {"client": sock, "host_data": None}
        try:
            send_json(room.host_ctrl, {"event": "new_client", "slot": slot_id})
        except OSError:
            send_json(sock, {"error": "host disconnected"})
            sock.close()
            return
        deadline = time.monotonic() + BRIDGE_WAIT_S
        with room.cond:
            while room.slots.get(slot_id, {}).get("host_data") is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not room.cond.wait(remaining):
                    break
            host_sock = room.slots.get(slot_id, {}).get("host_data")
        if host_sock is None:
            send_json(sock, {"error": "the host did not answer"})
            sock.close()
            return
        send_json(sock, {"status": "bridged"})
        sock.settimeout(None)
        self._bridge(sock, host_sock, room, slot_id)

    def _cmd_data(self, sock, code, slot_id):
        with self.lock:
            room = self.rooms.get(code.upper().strip())
        if room is None or type(slot_id) is not int:
            send_json(sock, {"error": "room not found"})
            sock.close()
            return
        with room.cond:
            slot = room.slots.get(slot_id)
            if slot is None or slot["host_data"] is not None:
                send_json(sock, {"error": "invalid slot"})
                sock.close()
                return
            slot["host_data"] = sock
            room.cond.notify_all()
        send_json(sock, {"status": "bridged"})
        sock.settimeout(None)
        # The bridge itself runs in the thread of the joining client.

    # ------------------------------------------------------------------
    #  Bridging
    # ------------------------------------------------------------------

    def _bridge(self, client, host_data, room, slot_id):
        def forward(src, dst):
            try:
                while True:
                    data = src.recv(CHUNK)
                    if not data:
                        break
                    room.last_host_activity = time.monotonic()
                    dst.sendall(data)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        threads = [threading.Thread(target=forward, args=(client, host_data), daemon=True),
                   threading.Thread(target=forward, args=(host_data, client), daemon=True)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for s in (client, host_data):
            try:
                s.close()
            except OSError:
                pass
        with room.cond:
            room.slots.pop(slot_id, None)

    def _close_room(self, code):
        with self.lock:
            room = self.rooms.pop(code, None)
        if room is None:
            return
        socks = [room.host_ctrl]
        with room.cond:
            for slot in room.slots.values():
                socks += [slot.get("client"), slot.get("host_data")]
        for s in socks:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    def _cleanup_loop(self):
        while self._running:
            time.sleep(CLEANUP_INTERVAL_S)
            now = time.monotonic()
            with self.lock:
                stale = [c for c, r in self.rooms.items()
                         if now - r.last_host_activity > HOST_TIMEOUT_S]
            for code in stale:
                print(f"[RELAY] room {code} expired")
                self._close_room(code)


def main():
    port = 7777
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: python -m net.relay_server [port]")
            sys.exit(1)
    RelayServer(port).serve_forever()


if __name__ == "__main__":
    main()
