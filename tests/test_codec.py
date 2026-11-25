"""Tests for the safe network codec (net/codec.py)."""
import os
import pickle
import random

import pytest

from net import codec
from net.codec import CodecError, decode, encode


@pytest.mark.parametrize("value", [
    None, True, False, 0, 1, -1, 63, 64, -64, -65, 2**31, -2**31, 2**63 - 1, -2**63,
    0.0, 1.5, -3.25e300, float("inf"), "", "é✦漢", b"", b"\x00\xff" * 10,
    [], [1, [2, [3]]], (1, 2), {"a": 1, 2: [None, True]}, {},
])
def test_round_trip(value):
    assert decode(encode(value)) == value


def test_types_are_preserved():
    r = decode(encode({"t": (1, 2), "l": [1, 2], "b": True, "i": 1}))
    assert isinstance(r["t"], tuple) and isinstance(r["l"], list)
    assert r["b"] is True and type(r["i"]) is int


def test_set_becomes_list():
    assert sorted(decode(encode({3, 1, 2}))) == [1, 2, 3]


def test_random_round_trip():
    rnd = random.Random(1234)

    def gen(depth=0):
        c = rnd.randrange(8 if depth < 4 else 5)
        if c == 0: return None
        if c == 1: return rnd.random() < .5
        if c == 2: return rnd.randrange(-2**63, 2**63)
        if c == 3: return rnd.uniform(-1e6, 1e6)
        if c == 4: return "".join(chr(rnd.randrange(32, 0x2FFF)) for _ in range(rnd.randrange(10)))
        if c == 5: return [gen(depth + 1) for _ in range(rnd.randrange(5))]
        if c == 6: return tuple(gen(depth + 1) for _ in range(rnd.randrange(5)))
        return {rnd.choice(["a", "b", "c", 1, 2]): gen(depth + 1) for _ in range(rnd.randrange(5))}

    for _ in range(500):
        v = gen()
        assert decode(encode(v)) == v


def test_malicious_pickle_is_rejected():
    class Trap:
        def __reduce__(self):
            return (os.system, ("echo pwned",))
    with pytest.raises(CodecError):
        decode(pickle.dumps(Trap()))


def test_unsupported_types_fail_at_encoding():
    with pytest.raises(CodecError):
        encode(object())
    with pytest.raises(CodecError):
        encode({(1, 2): 3})
    with pytest.raises(CodecError):
        encode(2**70)


def test_depth_is_bounded():
    v = []
    for _ in range(codec.MAX_DEPTH + 5):
        v = [v]
    with pytest.raises(CodecError):
        encode(v)
    with pytest.raises(CodecError):
        decode(b"\x07\x01" * 5000 + b"\x00")


def test_giant_declared_container_is_rejected():
    with pytest.raises(CodecError):
        decode(b"\x07\x80\xc2\xd7\x2f\x00")   # list announcing 100M items
    with pytest.raises(CodecError):
        decode(b"\x06\xff\xff\xff\x7f")        # 268 MB of bytes announced


def test_fuzz_only_raises_codec_error():
    rnd = random.Random(99)
    for _ in range(3000):
        data = bytes(rnd.randrange(256) for _ in range(rnd.randrange(0, 40)))
        try:
            decode(data)
        except CodecError:
            pass


def test_trailing_and_truncated_bytes():
    good = encode({"a": [1, 2, 3]})
    with pytest.raises(CodecError):
        decode(good + b"\x00")
    with pytest.raises(CodecError):
        decode(good[:-1])
