"""Tests for the UDP reliability layer (net/udp.py) and binary layouts (net/protocol.py)."""
import random

import pytest

from net import protocol as P
from net import udp


class LossyLink:
    """Fake endpoint pair that drops / duplicates / reorders datagrams."""

    def __init__(self, loss=0.0, dup=0.0, seed=1):
        self.rnd = random.Random(seed)
        self.loss, self.dup = loss, dup
        self.queue = []          # (dest, data)

    def endpoint(self, name):
        link = self

        class EP:
            def send(self, data, addr):
                if link.rnd.random() < link.loss:
                    return True
                link.queue.append((addr, data))
                if link.rnd.random() < link.dup:
                    link.queue.append((addr, data))
                return True
        return EP()

    def deliver(self, conns):
        q, self.queue = self.queue, []
        self.rnd.shuffle(q)      # reordering
        for dest, data in q:
            conns[dest].receive_datagram(data)


def make_pair(loss=0.0, dup=0.0):
    link = LossyLink(loss, dup)
    a = udp.UdpConnection(link.endpoint('a'), 'B')
    b = udp.UdpConnection(link.endpoint('b'), 'A')
    return link, a, b, {'A': a, 'B': b}


def pump(link, conns, a, b, rounds=60):
    for _ in range(rounds):
        link.deliver(conns)
        a.tick(udp.now_ms() + 10_000 * 0)  # real time is fine
        b.tick()


def test_reliable_delivered_once_under_loss_and_duplication():
    link, a, b, conns = make_pair(loss=0.4, dup=0.3)
    for i in range(50):
        a.send_reliable(P.T_EVENTS, f"msg{i}".encode())
    received = []
    deadline = udp.now_ms() + 5000
    while len(received) < 50 and udp.now_ms() < deadline:
        link.deliver(conns)
        a.tick(); b.tick()
        received += [d for t, d in b.drain() if t == P.T_EVENTS]
        # the peer must send something so that acks flow back
        b.send_unreliable(P.T_PONG, b'x')
        udp.time.sleep(0.005)
    assert sorted(received) == sorted(f"msg{i}".encode() for i in range(50))


def test_keyed_stream_never_delivers_stale_version():
    link, a, b, conns = make_pair()
    a.send_reliable(P.T_STATE, b'v1', key=1)
    a.send_reliable(P.T_STATE, b'v2', key=1)
    a.send_reliable(P.T_STATE, b'v3', key=1)
    # deliver in reverse order
    q = list(reversed(link.queue)); link.queue.clear()
    for dest, data in q:
        conns[dest].receive_datagram(data)
    got = [d for t, d in b.drain()]
    assert got[0] == b'v3' and b'v1' not in got and b'v2' not in got


def test_fragmentation_reassembly():
    link, a, b, conns = make_pair(loss=0.2)
    big = bytes(random.Random(5).randrange(256) for _ in range(5000))
    a.send_reliable(P.T_STATE, big, key=3)
    out = []
    deadline = udp.now_ms() + 5000
    while not out and udp.now_ms() < deadline:
        link.deliver(conns)
        a.tick(); b.tick()
        b.send_unreliable(P.T_PONG, b'x')
        out += [d for t, d in b.drain() if t == P.T_STATE]
        udp.time.sleep(0.005)
    assert out == [big]


def test_unreliable_drops_out_of_order():
    link, a, b, conns = make_pair()
    for i in range(5):
        a.send_unreliable(P.T_SNAPSHOT, bytes([i]))
    q = list(reversed(link.queue)); link.queue.clear()
    for dest, data in q:
        conns[dest].receive_datagram(data)
    got = [d[0] for t, d in b.drain()]
    assert got == [4]            # older ones arrive after the newest and are dropped


def test_rtt_is_measured():
    link, a, b, conns = make_pair()
    a.send_reliable(P.T_EVENTS, b'hi')
    udp.time.sleep(0.03)
    link.deliver(conns)
    b.send_unreliable(P.T_PONG, b'')   # carries the ack
    link.deliver(conns)
    assert a.rtt_ms >= 25


def test_garbage_datagrams_are_ignored():
    link, a, b, conns = make_pair()
    rnd = random.Random(7)
    for _ in range(500):
        b.receive_datagram(bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 60))))
    b.drain()


def test_inputs_pack_unpack():
    data = P.pack_inputs(1000, [1, 2, 3])
    assert P.unpack_inputs(data) == [(998, 1), (999, 2), (1000, 3)]
    assert P.unpack_inputs(b'') == []
    assert P.unpack_inputs(data + b'\x00') == []


def test_snapshot_round_trip():
    common = P.pack_snapshot_common(12345, [(0, 100, 200, 5), (1, -3, 40000, 8)],
                                    [(7, 1, 2, 3)], (500, 600))
    owner = P.pack_owner_block(42, 10, 20, 1.5, 3, -1, 1, 2.5, -4.0, 3, 1, 2, 3, 4, 5)
    t, players, enemies, boss, own = P.unpack_snapshot(common + owner)
    assert t == 12345 and players[0] == (0, 100, 200, 5)
    assert players[1][2] == 32767            # clamped
    assert enemies == [(7, 1, 2, 3)] and boss == (500, 600)
    assert own['ack_seq'] == 42 and own['vel_y'] == 1.5 and own['recoil'] == 5
    t, players, enemies, boss, own = P.unpack_snapshot(common)
    assert own is None
    with pytest.raises(ValueError):
        P.unpack_snapshot(common[:5])
