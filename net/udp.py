"""UDP transport: non-blocking socket wrapper + per-peer reliability layer.

Every datagram starts with a fixed 14-byte header (``!IIIBB``)::

    seq       uint32  outgoing sequence number (all channels share it)
    ack       uint32  highest sequence number received from the peer
    ack_bits  uint32  bitfield of the 32 sequence numbers before ``ack``
    channel   uint8   0 = unreliable, 1 = reliable, 2 = control
    type      uint8   message type (see ``net.protocol``)

Reliability follows Glenn Fiedler's ack/ack-bits scheme
(https://gafferongames.com). Reliable messages are retransmitted until
acknowledged and delivered at most once. They are *not* ordered, but a message
may carry a ``key``: for the same key only the newest version is ever
delivered (stale retransmissions are dropped on both sides), which is exactly
what "latest state" streams need. Large reliable messages are fragmented.

``UdpConnection`` performs no I/O of its own: it hands datagrams to the
``UdpEndpoint`` it was given and receives raw datagrams through
:meth:`UdpConnection.receive_datagram`.
"""

import errno
import socket
import struct
import time

from net.protocol import T_HEARTBEAT

# ---------------------------------------------------------------------------
#  Header
# ---------------------------------------------------------------------------

CH_UNRELIABLE = 0
CH_RELIABLE = 1
CH_CONTROL = 2

HEADER = struct.Struct('!IIIBB')
HEADER_SIZE = HEADER.size

# Reliable payload prefix: key(u8) version(u16) frag_index(u8) frag_count(u8)
_RELIABLE_PREFIX = struct.Struct('!BHBB')
MAX_FRAGMENT_BYTES = 1000      # keeps datagrams under a typical 1200 B MTU budget
MAX_FRAGMENTS = 64
MAX_DATAGRAM = 65535
ACK_WINDOW = 32


def seq_newer(a: int, b: int) -> bool:
    """True if sequence ``a`` is more recent than ``b`` (uint32 wrap-around)."""
    diff = (a - b) & 0xFFFFFFFF
    return 0 < diff < 0x80000000


def version_newer(a: int, b: int) -> bool:
    """Same as :func:`seq_newer` for the 16-bit message versions."""
    diff = (a - b) & 0xFFFF
    return 0 < diff < 0x8000


def now_ms() -> int:
    return int(time.monotonic() * 1000)


# ---------------------------------------------------------------------------
#  Socket wrapper
# ---------------------------------------------------------------------------

class UdpEndpoint:
    """Non-blocking UDP socket. ``poll()`` drains everything that arrived."""

    def __init__(self, bind_host: str, bind_port: int = 0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        except OSError:
            pass
        self.sock.bind((bind_host, bind_port))
        self.sock.setblocking(False)
        if hasattr(socket, 'SIO_UDP_CONNRESET'):
            # Windows: do not let ICMP "port unreachable" raise WSAECONNRESET on recvfrom.
            try:
                self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (OSError, ValueError):
                pass
        self.bind_host = bind_host
        self.bind_port = self.sock.getsockname()[1]
        self.bytes_sent = 0
        self.bytes_received = 0

    def send(self, data: bytes, addr: tuple) -> bool:
        try:
            self.sock.sendto(data, addr)
            self.bytes_sent += len(data)
            return True
        except (BlockingIOError, InterruptedError):
            return False
        except OSError as exc:
            if exc.errno in (errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH,
                             errno.ENOBUFS, getattr(errno, 'WSAECONNRESET', -1)):
                return False
            raise

    def poll(self, max_packets: int = 512):
        """Drain the socket. Returns a list of ``(bytes, addr)``."""
        packets = []
        for _ in range(max_packets):
            try:
                data, addr = self.sock.recvfrom(MAX_DATAGRAM)
            except (BlockingIOError, InterruptedError):
                break
            except OSError as exc:
                if exc.errno == getattr(errno, 'WSAECONNRESET', -1):
                    continue
                break
            self.bytes_received += len(data)
            packets.append((data, addr))
        return packets

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
#  Per-peer reliability
# ---------------------------------------------------------------------------

class _InFlight:
    __slots__ = ('seq', 'type', 'payload', 'sent_ms', 'next_retry_ms', 'tries', 'key')

    def __init__(self, seq, type_, payload, sent_ms, key):
        self.seq = seq
        self.type = type_
        self.payload = payload
        self.sent_ms = sent_ms
        self.next_retry_ms = sent_ms + 100
        self.tries = 1
        self.key = key


class UdpConnection:
    """One remote peer (the server holds one per client, a client holds one)."""

    def __init__(self, endpoint: UdpEndpoint, addr: tuple,
                 heartbeat_ms: int = 1000, timeout_ms: int = 5000):
        self.endpoint = endpoint
        self.addr = addr
        self.heartbeat_ms = heartbeat_ms
        self.timeout_ms = timeout_ms

        # Sending
        self._out_seq = 0
        self._in_flight = {}              # seq -> _InFlight (reliable only)
        self._out_version = {}            # key -> next u16 version
        self._latest_seqs = {}            # key -> set of in-flight seqs

        # Receiving
        self._recv_max_seq = 0
        self._recv_bits = 0
        self._last_unreliable_seq = {}    # type -> seq
        self._reliable_seen = set()
        self._key_version = {}            # key -> newest delivered version
        self._fragments = {}              # (key, version) -> {index: bytes}

        self._inbox = []                  # [(type, bytes)]

        now = now_ms()
        self._last_send_ms = now
        self.last_recv_ms = now

        self.rtt_ms = 0.0
        self._rtt_samples = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.retransmissions = 0
        self.alive = True

    # -- sending ----------------------------------------------------------

    def _send_raw(self, channel: int, type_: int, payload: bytes, seq: int = None) -> int:
        if seq is None:
            self._out_seq = (self._out_seq + 1) & 0xFFFFFFFF or 1
            seq = self._out_seq
        header = HEADER.pack(seq, self._recv_max_seq, self._recv_bits, channel, type_)
        self.endpoint.send(header + payload, self.addr)
        self.packets_sent += 1
        self._last_send_ms = now_ms()
        return seq

    def send_unreliable(self, type_: int, payload: bytes):
        self._send_raw(CH_UNRELIABLE, type_, payload)

    def send_control(self, type_: int, payload: bytes = b''):
        self._send_raw(CH_CONTROL, type_, payload)

    def send_reliable(self, type_: int, payload: bytes, key: int = 0):
        """Send a reliable message.

        ``key`` != 0 marks a "latest state" stream: sending a new message with
        the same key abandons the retransmission of the previous one."""
        if key:
            version = (self._out_version.get(key, 0) + 1) & 0xFFFF
            self._out_version[key] = version
            for old in self._latest_seqs.pop(key, ()):
                self._in_flight.pop(old, None)
        else:
            version = 0
        chunks = [payload[i:i + MAX_FRAGMENT_BYTES]
                  for i in range(0, len(payload), MAX_FRAGMENT_BYTES)] or [b'']
        if len(chunks) > MAX_FRAGMENTS:
            raise ValueError("reliable message too large")
        sent_seqs = set()
        for index, chunk in enumerate(chunks):
            prefix = _RELIABLE_PREFIX.pack(key, version, index, len(chunks))
            data = prefix + chunk
            seq = self._send_raw(CH_RELIABLE, type_, data)
            self._in_flight[seq] = _InFlight(seq, type_, data, self._last_send_ms, key)
            sent_seqs.add(seq)
        if key:
            self._latest_seqs[key] = sent_seqs

    # -- receiving --------------------------------------------------------

    def receive_datagram(self, data: bytes):
        if len(data) < HEADER_SIZE:
            return
        seq, ack, ack_bits, channel, type_ = HEADER.unpack_from(data)
        payload = data[HEADER_SIZE:]
        self.last_recv_ms = now_ms()
        self.packets_received += 1

        self._note_received(seq)
        self._process_acks(ack, ack_bits)

        if channel == CH_UNRELIABLE:
            last = self._last_unreliable_seq.get(type_)
            if last is not None and not seq_newer(seq, last):
                return                       # stale or duplicate
            self._last_unreliable_seq[type_] = seq
            self._inbox.append((type_, payload))
        elif channel == CH_CONTROL:
            self._inbox.append((type_, payload))
        elif channel == CH_RELIABLE:
            self._receive_reliable(seq, type_, payload)

    def _receive_reliable(self, seq: int, type_: int, payload: bytes):
        if seq in self._reliable_seen:
            return                           # retransmission of a delivered packet
        if len(payload) < _RELIABLE_PREFIX.size:
            return
        self._reliable_seen.add(seq)
        if len(self._reliable_seen) > 4096:
            horizon = (self._recv_max_seq - 2048) & 0xFFFFFFFF
            self._reliable_seen = {s for s in self._reliable_seen
                                   if not seq_newer(horizon, s)}
        key, version, index, count = _RELIABLE_PREFIX.unpack_from(payload)
        body = payload[_RELIABLE_PREFIX.size:]
        if count == 0 or count > MAX_FRAGMENTS or index >= count:
            return
        if key:
            newest = self._key_version.get(key)
            if newest is not None and not version_newer(version, newest) and version != newest:
                return                       # older than what we already delivered
        if count == 1:
            self._deliver(type_, key, version, body)
            return
        parts = self._fragments.setdefault((key, version, type_), {})
        parts[index] = body
        if len(parts) == count:
            del self._fragments[(key, version, type_)]
            self._deliver(type_, key, version, b''.join(parts[i] for i in range(count)))
        elif len(self._fragments) > 64:
            # Bound memory: drop the oldest incomplete reassembly.
            self._fragments.pop(next(iter(self._fragments)))

    def _deliver(self, type_: int, key: int, version: int, body: bytes):
        if key:
            newest = self._key_version.get(key)
            if newest is not None and not version_newer(version, newest):
                return
            self._key_version[key] = version
            # Abandon reassemblies of older versions of the same key.
            for k in [k for k in self._fragments if k[0] == key and k[1] != version]:
                del self._fragments[k]
        self._inbox.append((type_, body))

    def _note_received(self, seq: int):
        """Update the (ack, ack_bits) we announce back to the peer."""
        if self._recv_max_seq == 0:
            self._recv_max_seq = seq
            self._recv_bits = 0
            return
        if seq_newer(seq, self._recv_max_seq):
            shift = (seq - self._recv_max_seq) & 0xFFFFFFFF
            if shift >= ACK_WINDOW + 1:
                self._recv_bits = 0
            else:
                self._recv_bits = ((self._recv_bits << shift)
                                   | (1 << (shift - 1))) & 0xFFFFFFFF
            self._recv_max_seq = seq
        else:
            diff = (self._recv_max_seq - seq) & 0xFFFFFFFF
            if 1 <= diff <= ACK_WINDOW:
                self._recv_bits |= 1 << (diff - 1)

    def _process_acks(self, ack: int, ack_bits: int):
        if ack == 0 or not self._in_flight:
            return
        now = now_ms()
        self._confirm(ack, now)
        if ack_bits:
            for i in range(ACK_WINDOW):
                if ack_bits & (1 << i):
                    seq = (ack - (i + 1)) & 0xFFFFFFFF
                    if seq:
                        self._confirm(seq, now)

    def _confirm(self, seq: int, now: int):
        pkt = self._in_flight.pop(seq, None)
        if pkt is None:
            return
        if pkt.key:
            seqs = self._latest_seqs.get(pkt.key)
            if seqs is not None:
                seqs.discard(seq)
        if pkt.tries == 1:                   # Karn: ignore ambiguous samples
            sample = max(0, now - pkt.sent_ms)
            if self._rtt_samples == 0:
                self.rtt_ms = float(sample)
            else:
                self.rtt_ms += 0.125 * (sample - self.rtt_ms)
            self._rtt_samples += 1

    # -- periodic work ----------------------------------------------------

    def tick(self, now: int = None):
        """Retransmissions, heartbeat and liveness check."""
        if now is None:
            now = now_ms()
        if self._in_flight:
            base = max(int(self.rtt_ms * 1.5), 60)
            for pkt in list(self._in_flight.values()):
                if now >= pkt.next_retry_ms:
                    header = HEADER.pack(pkt.seq, self._recv_max_seq, self._recv_bits,
                                         CH_RELIABLE, pkt.type)
                    self.endpoint.send(header + pkt.payload, self.addr)
                    pkt.tries += 1
                    pkt.next_retry_ms = now + min(base * pkt.tries, 1500)
                    self.retransmissions += 1
                    self._last_send_ms = now
        if now - self._last_send_ms >= self.heartbeat_ms:
            self.send_control(T_HEARTBEAT)
        if now - self.last_recv_ms >= self.timeout_ms:
            self.alive = False

    def drain(self):
        """Return and clear the received messages: ``[(type, bytes), ...]``."""
        out = self._inbox
        self._inbox = []
        return out
