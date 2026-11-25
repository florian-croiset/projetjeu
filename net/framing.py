"""TCP framing shared by client, server and relay, plus local IP discovery.

Wire format of one TCP frame:

    [uint32 length of the rest][uint8 flags][body]

    flags bit 0 : body is zlib-compressed
    body        : message encoded with ``net.codec`` (never pickle)
"""

import socket
import struct
import zlib

from net import codec

MAX_FRAME_BYTES = 4 * 1024 * 1024   # bytes on the wire
COMPRESS_THRESHOLD = 512            # small messages are not compressed
FLAG_ZLIB = 0x01

_HEADER = struct.Struct('!IB')


def recv_exact(sock, n: int) -> bytes:
    """Read exactly ``n`` bytes (TCP may fragment). Raises EOFError on close."""
    buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        count = sock.recv_into(view[got:], n - got)
        if count == 0:
            raise EOFError("connection closed")
        got += count
    return bytes(buf)


def encode_frame(obj) -> bytes:
    """Encode ``obj`` into a complete TCP frame (header included)."""
    body = codec.encode(obj)
    flags = 0
    if len(body) >= COMPRESS_THRESHOLD:
        packed = zlib.compress(body, 1)
        if len(packed) < len(body):
            body = packed
            flags |= FLAG_ZLIB
    if len(body) + 1 > MAX_FRAME_BYTES:
        raise codec.CodecError("TCP message too large")
    return _HEADER.pack(len(body) + 1, flags) + body


def decode_body(flags: int, body: bytes):
    """Decode the body of a frame (bounded decompression included)."""
    if flags & FLAG_ZLIB:
        inflater = zlib.decompressobj()
        try:
            body = inflater.decompress(body, codec.MAX_BYTES)
        except zlib.error as exc:
            raise codec.CodecError("invalid zlib data") from exc
        if inflater.unconsumed_tail:
            raise codec.CodecError("decompressed message too large")
    return codec.decode(body)


def recv_message(sock, max_size: int = MAX_FRAME_BYTES):
    """Receive one message. Raises EOFError if the peer closed the connection
    and ValueError (including ``CodecError``) if the frame is invalid."""
    size = int.from_bytes(recv_exact(sock, 4), 'big')
    if size < 1 or size > max_size:
        raise ValueError(f"invalid TCP frame ({size} bytes)")
    flags = recv_exact(sock, 1)[0]
    body = recv_exact(sock, size - 1)
    return decode_body(flags, body)


def send_message(sock, obj):
    """Send one message (blocking)."""
    sock.sendall(encode_frame(obj))


# ---------------------------------------------------------------------------
#  IP addresses
# ---------------------------------------------------------------------------

def local_ip() -> str:
    """IP of this machine on the default route (LAN address)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))   # UDP connect: no packet is sent
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


def list_local_ips() -> list:
    """All non-loopback IPv4 addresses (LAN, Tailscale, Hamachi...).

    Useful to show the host which addresses to give to friends."""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    main = local_ip()
    if main not in ips and not main.startswith("127."):
        ips.insert(0, main)
    return ips
