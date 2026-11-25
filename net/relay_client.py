"""Helpers to use a relay server (see ``net.relay_server``) from the host and from clients."""

import json
import socket
import threading

from net.relay_server import recv_line, send_json

CONNECT_TIMEOUT_S = 10.0
KEEPALIVE_S = 30.0


def _open(relay_host, relay_port):
    sock = socket.create_connection((relay_host, relay_port), timeout=CONNECT_TIMEOUT_S)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def _expect_ok(sock, expected_key):
    reply = json.loads(recv_line(sock))
    if not isinstance(reply, dict) or "error" in reply:
        sock.close()
        raise ConnectionError(f"Relay: {reply.get('error') if isinstance(reply, dict) else reply}")
    if expected_key not in reply:
        sock.close()
        raise ConnectionError(f"Relay: unexpected reply {reply}")
    return reply


def relay_create_room(relay_host, relay_port):
    """Create a room. Returns ``(control_socket, room_code)``.

    The control socket must stay open as long as the room should exist; a daemon
    thread sends keep-alive bytes on it."""
    ctrl = _open(relay_host, relay_port)
    send_json(ctrl, {"cmd": "host"})
    code = _expect_ok(ctrl, "code")["code"]
    ctrl.settimeout(None)
    stop = threading.Event()

    def keepalive():
        while not stop.wait(KEEPALIVE_S):
            try:
                ctrl.sendall(b'.')
            except OSError:
                return

    threading.Thread(target=keepalive, name="relay-keepalive", daemon=True).start()
    return ctrl, code


def relay_wait_client(ctrl_socket):
    """Block until a client joins; returns its slot id."""
    event = json.loads(recv_line(ctrl_socket))
    if event.get("event") != "new_client":
        raise ConnectionError(f"Relay: unexpected event {event}")
    return event["slot"]


def relay_open_channel_data(relay_host, relay_port, room_code, slot_id):
    """Open the host side of one client's bridge; returns a socket usable like
    a directly accepted client connection."""
    sock = _open(relay_host, relay_port)
    send_json(sock, {"cmd": "data", "code": room_code, "slot": slot_id})
    _expect_ok(sock, "status")
    sock.settimeout(None)
    return sock


def relay_join(relay_host, relay_port, room_code):
    """Join a room by code; returns a socket bridged to the host."""
    sock = _open(relay_host, relay_port)
    sock.settimeout(20.0)
    send_json(sock, {"cmd": "join", "code": room_code.upper().strip()})
    _expect_ok(sock, "status")
    sock.settimeout(None)
    return sock
