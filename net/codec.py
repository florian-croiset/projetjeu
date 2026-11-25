"""Safe binary codec for Echo network messages.

Replaces ``pickle`` everywhere on the wire. A pickle decoder can execute
arbitrary code (even a "restricted" one stays open to CPU/memory abuse), whereas
this format can only represent inert data:

    None, bool, int, float, str, bytes, list, tuple, dict (str or int keys)

``set`` / ``frozenset`` are encoded as lists.

Format: one tag byte followed by the payload.

    0x00 None            0x01 False         0x02 True
    0x03 int             zigzag varint (up to 64 bits)
    0x04 float           big-endian float64
    0x05 str             varint length + UTF-8
    0x06 bytes           varint length + raw bytes
    0x07 list            varint n + n values
    0x08 dict            varint n + n * (key, value)
    0x09 tuple           varint n + n values

The decoder bounds everything (depth, element count, total size) and raises
``CodecError`` (a ``ValueError`` subclass) on any invalid input, never anything
else.
"""

import struct

MAX_DEPTH = 24
MAX_ELEMENTS = 200_000          # per container
MAX_BYTES = 8 * 1024 * 1024     # total size of an encoded message

_T_NONE, _T_FALSE, _T_TRUE, _T_INT, _T_FLOAT, _T_STR, _T_BYTES, _T_LIST, _T_DICT, _T_TUPLE = range(10)

_FLOAT = struct.Struct('>d')


class CodecError(ValueError):
    """Malformed, oversized or unrepresentable message."""


# ---------------------------------------------------------------------------
#  Encoding
# ---------------------------------------------------------------------------

def _write_varint(out: bytearray, n: int):
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)


def _encode(obj, out: bytearray, depth: int):
    if depth > MAX_DEPTH:
        raise CodecError("maximum depth exceeded")
    t = type(obj)
    if obj is None:
        out.append(_T_NONE)
    elif t is bool:
        out.append(_T_TRUE if obj else _T_FALSE)
    elif t is int:
        if not -(1 << 63) <= obj < (1 << 63):
            raise CodecError("integer out of 64-bit range")
        out.append(_T_INT)
        _write_varint(out, obj << 1 if obj >= 0 else ((-obj) << 1) - 1)
    elif t is float:
        out.append(_T_FLOAT)
        out += _FLOAT.pack(obj)
    elif t is str:
        data = obj.encode('utf-8')
        out.append(_T_STR)
        _write_varint(out, len(data))
        out += data
    elif t is bytes or t is bytearray:
        out.append(_T_BYTES)
        _write_varint(out, len(obj))
        out += obj
    elif t is list or t is set or t is frozenset:
        out.append(_T_LIST)
        _write_varint(out, len(obj))
        for v in obj:
            _encode(v, out, depth + 1)
    elif t is tuple:
        out.append(_T_TUPLE)
        _write_varint(out, len(obj))
        for v in obj:
            _encode(v, out, depth + 1)
    elif t is dict:
        out.append(_T_DICT)
        _write_varint(out, len(obj))
        for k, v in obj.items():
            if type(k) is not str and type(k) is not int:
                raise CodecError(f"unsupported dict key: {type(k).__name__}")
            _encode(k, out, depth + 1)
            _encode(v, out, depth + 1)
    elif isinstance(obj, bool):
        out.append(_T_TRUE if obj else _T_FALSE)
    elif isinstance(obj, int):
        _encode(int(obj), out, depth)
    elif isinstance(obj, float):
        _encode(float(obj), out, depth)
    else:
        raise CodecError(f"unsupported type: {t.__name__}")


def encode(obj) -> bytes:
    """Serialize ``obj`` to bytes."""
    out = bytearray()
    _encode(obj, out, 0)
    if len(out) > MAX_BYTES:
        raise CodecError("message too large")
    return bytes(out)


# ---------------------------------------------------------------------------
#  Decoding
# ---------------------------------------------------------------------------

class _Reader:
    __slots__ = ('data', 'pos', 'end')

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.end = len(data)

    def byte(self) -> int:
        if self.pos >= self.end:
            raise CodecError("unexpected end of message")
        b = self.data[self.pos]
        self.pos += 1
        return b

    def varint(self) -> int:
        n = 0
        shift = 0
        while True:
            b = self.byte()
            n |= (b & 0x7F) << shift
            if not b & 0x80:
                return n
            shift += 7
            if shift > 70:
                raise CodecError("varint too long")

    def read(self, n: int):
        if n < 0 or self.pos + n > self.end:
            raise CodecError("invalid length")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk


def _decode(r: _Reader, depth: int):
    if depth > MAX_DEPTH:
        raise CodecError("maximum depth exceeded")
    tag = r.byte()
    if tag == _T_NONE:
        return None
    if tag == _T_FALSE:
        return False
    if tag == _T_TRUE:
        return True
    if tag == _T_INT:
        z = r.varint()
        if z >= 1 << 64:
            raise CodecError("integer out of range")
        return (z >> 1) ^ -(z & 1)
    if tag == _T_FLOAT:
        return _FLOAT.unpack(r.read(8))[0]
    if tag == _T_STR:
        try:
            return bytes(r.read(r.varint())).decode('utf-8')
        except UnicodeDecodeError as exc:
            raise CodecError("invalid UTF-8") from exc
    if tag == _T_BYTES:
        return bytes(r.read(r.varint()))
    if tag == _T_LIST or tag == _T_TUPLE:
        n = r.varint()
        # Every element takes at least one byte: natural allocation bound.
        if n > MAX_ELEMENTS or n > r.end - r.pos:
            raise CodecError("container too large")
        items = [_decode(r, depth + 1) for _ in range(n)]
        return tuple(items) if tag == _T_TUPLE else items
    if tag == _T_DICT:
        n = r.varint()
        if n > MAX_ELEMENTS or 2 * n > r.end - r.pos:
            raise CodecError("dict too large")
        d = {}
        for _ in range(n):
            key = _decode(r, depth + 1)
            if type(key) is not str and type(key) is not int:
                raise CodecError("invalid dict key")
            d[key] = _decode(r, depth + 1)
        return d
    raise CodecError(f"unknown tag: {tag}")


def decode(data):
    """Deserialize bytes produced by :func:`encode`.

    Raises ``CodecError`` if ``data`` is not a valid message.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise CodecError("bytes expected")
    if len(data) > MAX_BYTES:
        raise CodecError("message too large")
    r = _Reader(data)
    try:
        value = _decode(r, 0)
    except RecursionError as exc:
        raise CodecError("excessive recursion") from exc
    if r.pos != r.end:
        raise CodecError("trailing bytes after message")
    return value
