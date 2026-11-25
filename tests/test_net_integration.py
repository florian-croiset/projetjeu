"""End-to-end tests: real Server + NetClient over loopback (UDP and TCP-only)."""
import pickle
import socket
import struct
import time

import pygame
import pytest

from net import framing, protocol as P
from net.client import ConnectError, NetClient
from net.server import Server


@pytest.fixture
def server(tmp_path, monkeypatch):
    from storage import saves
    monkeypatch.setattr(saves, "get_folder_save", lambda: str(tmp_path))
    pygame.init()
    pygame.display.set_mode((64, 64))
    srv = Server(0, True, tcp_port=0, udp_port=0, bind_host="127.0.0.1",
                 enable_pathfinding=False, save_enabled=False)
    srv.start()
    yield srv
    srv.stop()


def wait_for(client, predicate, timeout=5.0):
    """Poll the client until ``predicate(messages_so_far)`` holds."""
    seen = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        seen += client.poll()
        if predicate(seen):
            return seen
        time.sleep(0.005)
    return seen


def wait_until(condition, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline and not condition():
        time.sleep(0.01)
    return condition()


def snapshots(msgs):
    return [d for kind, d in msgs if kind == 'snapshot']


def connect(server, want_udp):
    client = NetClient()
    client.connect("127.0.0.1", server.tcp_port, "tester", 0, want_udp=want_udp)
    return client


@pytest.mark.parametrize("want_udp", [True, False])
def test_snapshots_and_inputs(server, want_udp):
    client = connect(server, want_udp)
    try:
        assert client.my_id == 0
        assert client.udp_active == want_udp
        msgs = wait_for(client, lambda m: snapshots(m))
        assert snapshots(msgs), "no snapshot received"
        t, players, enemies, boss, owner = snapshots(msgs)[-1]
        assert owner is not None and len(players) == 1
        x0 = owner['x']

        # hold "right" for ~0.5 s of ticks: the server must move the player
        seq = 0
        end = time.time() + 0.6
        last = None
        while time.time() < end:
            seq += 1
            client.send_inputs(seq, [P.IN_RIGHT])
            for kind, data in client.poll():
                if kind == 'snapshot' and data[4]:
                    last = data[4]
            time.sleep(1 / 60)
        assert last is not None and last['x'] > x0 + 50
        assert 0 < last['ack_seq'] <= seq
    finally:
        client.close()


def test_state_streams_and_events(server):
    client = connect(server, True)
    try:
        def complete(msgs):
            keys = {d['k'] for kind, d in msgs if kind == 'state'}
            events = [e['e'] for kind, d in msgs if kind == 'events' for e in d]
            return keys == {P.KEY_PLAYERS, P.KEY_ENEMIES, P.KEY_WORLD} and 'vis_full' in events

        msgs = wait_for(client, complete, timeout=8.0)
        assert complete(msgs)
    finally:
        client.close()


def test_two_clients_see_each_other(server):
    a, b = connect(server, True), connect(server, False)
    try:
        assert {a.my_id, b.my_id} == {0, 1}
        msgs = wait_for(a, lambda m: any(len(s[1]) == 2 for s in snapshots(m)))
        assert any(len(s[1]) == 2 for s in snapshots(msgs))
    finally:
        a.close()
        b.close()


def test_server_full(server):
    clients = [connect(server, False) for _ in range(P.MAX_PLAYERS)]
    try:
        with pytest.raises(ConnectError) as err:
            connect(server, False)
        assert err.value.code == "full"
    finally:
        for c in clients:
            c.close()


def test_player_slot_is_released_on_disconnect(server):
    c = connect(server, False)
    c.close()
    deadline = time.time() + 3
    while time.time() < deadline and len(server._free_ids) < P.MAX_PLAYERS:
        time.sleep(0.02)
    assert not server.world.players
    c2 = connect(server, False)
    assert c2.my_id == 0
    c2.close()


def _raw_hello(server):
    sock = socket.create_connection(("127.0.0.1", server.tcp_port), timeout=3)
    info = framing.recv_message(sock)
    assert info['proto'] == P.PROTOCOL_VERSION
    return sock


def test_malicious_pickle_cannot_execute_and_server_survives(server, tmp_path):
    marker = tmp_path / "pwned"

    class Evil:
        def __reduce__(self):
            return (open, (str(marker), "w"))

    sock = _raw_hello(server)
    body = pickle.dumps(Evil())
    sock.sendall(struct.pack("!IB", len(body) + 1, 0) + body)
    time.sleep(0.3)
    assert not marker.exists()
    sock.close()
    c = connect(server, False)        # server still accepts clients
    assert snapshots(wait_for(c, lambda m: snapshots(m)))
    c.close()


def test_garbage_drops_only_the_offender(server):
    bad, good = connect(server, False), connect(server, False)
    try:
        wait_until(lambda: {bad.my_id, good.my_id} <= set(server.world.players))
        junk = bytes([255]) * 50
        bad.sock.sendall(struct.pack("!IB", len(junk) + 1, 0) + junk)
        wait_until(lambda: bad.my_id not in server.world.players)
        assert bad.my_id not in server.world.players        # offender removed
        assert good.my_id in server.world.players           # everybody else unaffected
        assert snapshots(wait_for(good, lambda m: snapshots(m)))
    finally:
        bad.close()
        good.close()


def test_unknown_message_types_are_ignored(server):
    c = connect(server, False)
    try:
        wait_until(lambda: c.my_id in server.world.players)
        c._send_tcp(0x7e, b"whatever")
        c._send_tcp(P.T_ACTION, bytes([255, 255]))             # not a valid codec payload
        c.send_action({'a': 'does-not-exist'})
        c.send_action({'a': 'interact', 'item': {'nested': 'junk'}})
        assert snapshots(wait_for(c, lambda m: snapshots(m)))
        time.sleep(0.2)
        assert c.my_id in server.world.players
    finally:
        c.close()


def test_oversized_client_frame_is_rejected(server):
    sock = _raw_hello(server)
    sock.sendall(struct.pack("!IB", 50_000_000, 0))
    sock.settimeout(2)
    with pytest.raises((EOFError, OSError, ValueError)):
        while True:
            framing.recv_message(sock)
    sock.close()
