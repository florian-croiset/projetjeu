"""Tests for TCP framing (net/framing.py)."""
import socket
import struct
import threading

import pytest

from net import framing
from net.codec import CodecError


@pytest.fixture
def pair():
    a, b = socket.socketpair()
    a.settimeout(5)
    b.settimeout(5)
    yield a, b
    a.close()
    b.close()


def test_small_and_large_messages(pair):
    a, b = pair
    small = {"k": 1}
    big = {"data": list(range(5000))}     # compressible and > threshold
    framing.send_message(a, small)
    framing.send_message(a, big)
    assert framing.recv_message(b) == small
    assert framing.recv_message(b) == big


def test_large_message_is_compressed():
    frame = framing.encode_frame({"x": "a" * 10_000})
    assert len(frame) < 1000
    assert frame[4] & framing.FLAG_ZLIB


def test_fragmented_delivery(pair):
    a, b = pair
    frame = framing.encode_frame({"hello": "world", "n": list(range(100))})

    def slow():
        for i in range(0, len(frame), 3):
            a.sendall(frame[i:i + 3])

    t = threading.Thread(target=slow)
    t.start()
    assert framing.recv_message(b)["hello"] == "world"
    t.join()


def test_rejects_oversized_frame(pair):
    a, b = pair
    a.sendall(struct.pack("!IB", 50_000_000, 0))
    with pytest.raises(ValueError):
        framing.recv_message(b)


def test_rejects_pickle_payload(pair):
    import pickle
    a, b = pair
    body = pickle.dumps({"x": 1})
    a.sendall(struct.pack("!IB", len(body) + 1, 0) + body)
    with pytest.raises(CodecError):
        framing.recv_message(b)


def test_rejects_zip_bomb(pair):
    import zlib
    a, b = pair
    bomb = zlib.compress(b"\x00" * (50 * 1024 * 1024), 9)
    a.sendall(struct.pack("!IB", len(bomb) + 1, framing.FLAG_ZLIB) + bomb)
    with pytest.raises(CodecError):
        framing.recv_message(b)


def test_eof(pair):
    a, b = pair
    a.close()
    with pytest.raises(EOFError):
        framing.recv_message(b)
