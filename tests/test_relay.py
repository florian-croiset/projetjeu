"""Room-code play through the relay (TCP only)."""
import socket
import time

import pygame
import pytest

from net import relay_client
from net.client import NetClient
from net.relay_server import RelayServer
from net.server import Server


@pytest.fixture
def relay():
    r = RelayServer(0, bind_host="127.0.0.1")
    r.start()
    yield r
    r.stop()


@pytest.fixture
def hosted(relay):
    pygame.init()
    pygame.display.set_mode((64, 64))
    srv = Server(0, True, relay_host="127.0.0.1", relay_port=relay.port, tcp_port=0, udp_port=0,
                 bind_host="127.0.0.1", enable_pathfinding=False, save_enabled=False)
    srv.start()
    deadline = time.time() + 5
    while srv.room_code is None and time.time() < deadline:
        time.sleep(0.02)
    assert srv.room_code, "server did not obtain a room code"
    yield srv
    srv.stop()


def test_join_by_room_code_and_receive_snapshots(hosted, relay):
    sock = relay_client.relay_join("127.0.0.1", relay.port, hosted.room_code.lower())
    client = NetClient()
    client.adopt_socket(sock, "remote", 0, want_udp=False)
    try:
        assert not client.udp_active
        deadline = time.time() + 5
        got = []
        while time.time() < deadline and not got:
            got = [d for k, d in client.poll() if k == 'snapshot']
            time.sleep(0.01)
        assert got and got[-1][4] is not None
    finally:
        client.close()


def test_unknown_room_is_rejected(relay):
    with pytest.raises(ConnectionError):
        relay_client.relay_join("127.0.0.1", relay.port, "ZZZZZZ")


def test_relay_survives_garbage_and_oversized_commands(relay):
    for payload in (b"not json\n", b"x" * 5000 + b"\n", b'{"cmd": 1}\n', b'[1,2]\n', b'\n'):
        s = socket.create_connection(("127.0.0.1", relay.port), timeout=3)
        s.sendall(payload)
        s.settimeout(2)
        try:
            s.recv(100)
        except OSError:
            pass
        s.close()
    ctrl, code = relay_client.relay_create_room("127.0.0.1", relay.port)
    assert len(code) == 6
    ctrl.close()
