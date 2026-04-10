# reseau/transport.py
# Couche de transport UDP avec fiabilite, fragmentation et suivi de connexion.
# Remplace les sockets TCP bruts pour permettre la connectivite WAN sans Hamachi.

import socket
import struct
import threading
import time
import zlib
from collections import defaultdict

# ======================================================================
#  CONSTANTES PROTOCOLE
# ======================================================================

HEADER_FORMAT = "!BBHHH"  # type(1) flags(1) seq(2) ack(2) size(2)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 8 octets

# Types de paquets
PKT_CONNECT_REQ  = 0x01
PKT_CONNECT_ACK  = 0x02
PKT_CONNECT_REJ  = 0x03
PKT_DISCONNECT   = 0x04
PKT_INPUT        = 0x05
PKT_STATE        = 0x06
PKT_ACK          = 0x07
PKT_PING         = 0x08
PKT_PONG         = 0x09
PKT_PUNCH_REQ    = 0x0A
PKT_PUNCH_PEER   = 0x0B
PKT_FRAGMENT     = 0x0C
PKT_VIS_MAP      = 0x0D

# Flags
FLAG_RELIABLE    = 0x01
FLAG_COMPRESSED  = 0x02
FLAG_FRAGMENTED  = 0x04

# Limites
MAX_PACKET_SIZE  = 1200          # Safe MTU pour eviter fragmentation IP
MAX_PAYLOAD      = MAX_PACKET_SIZE - HEADER_SIZE
FRAGMENT_PAYLOAD = MAX_PAYLOAD - 4  # 4 octets header fragment (frag_id, index, total)
MAX_SEQ          = 0xFFFF
CONNECT_TIMEOUT  = 5.0
RELIABLE_TIMEOUT = 0.15          # Retransmission apres 150ms
MAX_RETRIES      = 15
PING_INTERVAL    = 1.0
DISCONNECT_TIMEOUT = 10.0

# ======================================================================
#  UTILITAIRES SEQUENCE
# ======================================================================

def seq_gt(a, b):
    """Retourne True si le numero de sequence a est 'plus recent' que b (wrap-around)."""
    return ((a > b) and (a - b <= MAX_SEQ // 2)) or \
           ((a < b) and (b - a >  MAX_SEQ // 2))


def seq_diff(a, b):
    """Difference signee entre deux numeros de sequence."""
    diff = a - b
    if diff > MAX_SEQ // 2:
        diff -= (MAX_SEQ + 1)
    elif diff < -(MAX_SEQ // 2):
        diff += (MAX_SEQ + 1)
    return diff

# ======================================================================
#  PAQUET
# ======================================================================

class Packet:
    """Represente un paquet reseau avec header et payload."""

    __slots__ = ('pkt_type', 'flags', 'seq', 'ack', 'payload')

    def __init__(self, pkt_type, flags=0, seq=0, ack=0, payload=b''):
        self.pkt_type = pkt_type
        self.flags = flags
        self.seq = seq
        self.ack = ack
        self.payload = payload

    def encode(self):
        """Serialise le paquet en bytes."""
        header = struct.pack(HEADER_FORMAT,
                             self.pkt_type, self.flags,
                             self.seq, self.ack,
                             len(self.payload))
        return header + self.payload

    @staticmethod
    def decode(data):
        """Deserialise un paquet depuis des bytes bruts."""
        if len(data) < HEADER_SIZE:
            return None
        pkt_type, flags, seq, ack, size = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:HEADER_SIZE + size]
        if len(payload) != size:
            return None
        return Packet(pkt_type, flags, seq, ack, payload)

    @property
    def is_reliable(self):
        return bool(self.flags & FLAG_RELIABLE)

    @property
    def is_compressed(self):
        return bool(self.flags & FLAG_COMPRESSED)

# ======================================================================
#  CONNEXION PEER
# ======================================================================

class PeerConnection:
    """Etat de connexion pour un peer distant."""

    def __init__(self, addr):
        self.addr = addr
        self.connected = False
        self.player_id = -1

        # Sequences
        self.local_seq = 0          # Prochain seq a envoyer
        self.remote_seq = 0         # Dernier seq recu du peer
        self.last_ack_sent = 0      # Dernier ack envoye

        # Fiabilite
        self.pending_reliable = {}  # seq -> (packet, send_time, retries)
        self.received_reliable = set()  # seq deja recus (pour dedup)

        # Fragmentation
        self.fragment_buffers = {}  # frag_id -> {index: data, ...}
        self.fragment_totals = {}   # frag_id -> total fragments

        # RTT / Ping
        self.rtt = 0.05             # 50ms par defaut
        self.rtt_smoothed = 0.05
        self.last_ping_time = 0
        self.last_ping_seq = 0
        self.last_recv_time = time.time()
        self.last_send_time = 0

        # Stats
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    def next_seq(self):
        """Retourne le prochain numero de sequence et l'incremente."""
        seq = self.local_seq
        self.local_seq = (self.local_seq + 1) & MAX_SEQ
        return seq

    def update_remote_seq(self, seq):
        """Met a jour le dernier seq recu si plus recent."""
        if seq_gt(seq, self.remote_seq) or self.remote_seq == 0:
            self.remote_seq = seq

    def ack_reliable(self, ack_seq):
        """Confirme la reception d'un paquet fiable."""
        to_remove = [s for s in self.pending_reliable if not seq_gt(s, ack_seq)]
        for s in to_remove:
            if s in self.pending_reliable:
                _, send_time, _ = self.pending_reliable.pop(s)
                # Mise a jour RTT
                sample = time.time() - send_time
                self.rtt_smoothed = 0.875 * self.rtt_smoothed + 0.125 * sample
                self.rtt = self.rtt_smoothed

    def is_duplicate_reliable(self, seq):
        """Verifie si ce paquet fiable a deja ete recu."""
        if seq in self.received_reliable:
            return True
        self.received_reliable.add(seq)
        # Nettoyer les vieux seq (garder 1000 derniers)
        if len(self.received_reliable) > 1000:
            min_valid = (self.remote_seq - 500) & MAX_SEQ
            self.received_reliable = {s for s in self.received_reliable
                                       if not seq_gt(min_valid, s)}
        return False

# ======================================================================
#  TRANSPORT UDP
# ======================================================================

class UDPTransport:
    """Transport UDP avec fiabilite optionnelle et fragmentation automatique."""

    def __init__(self, bind_addr=('0.0.0.0', 0)):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Augmenter les buffers socket
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
        except (OSError, socket.error):
            pass
        self.sock.bind(bind_addr)
        self.sock.setblocking(False)

        self.local_addr = self.sock.getsockname()
        self.peers = {}  # addr -> PeerConnection
        self.lock = threading.Lock()

        self._running = True
        self._next_frag_id = 0
        self._recv_buffer = []
        self._callbacks = {}  # pkt_type -> callback(packet, addr)

        # Thread de maintenance (retransmissions, pings, timeouts)
        self._maint_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
        self._maint_thread.start()

    @property
    def port(self):
        return self.local_addr[1]

    def close(self):
        """Ferme le transport proprement."""
        self._running = False
        # Envoyer DISCONNECT a tous les peers
        with self.lock:
            for addr, peer in list(self.peers.items()):
                if peer.connected:
                    try:
                        pkt = Packet(PKT_DISCONNECT, 0, peer.next_seq(), peer.remote_seq)
                        self.sock.sendto(pkt.encode(), addr)
                    except (OSError, socket.error):
                        pass
            self.peers.clear()
        try:
            self.sock.close()
        except (OSError, socket.error):
            pass

    def on(self, pkt_type, callback):
        """Enregistre un callback pour un type de paquet."""
        self._callbacks[pkt_type] = callback

    def get_peer(self, addr):
        """Retourne ou cree un PeerConnection pour cette adresse."""
        if addr not in self.peers:
            self.peers[addr] = PeerConnection(addr)
        return self.peers[addr]

    def remove_peer(self, addr):
        """Supprime un peer."""
        self.peers.pop(addr, None)

    # ------------------------------------------------------------------
    #  ENVOI
    # ------------------------------------------------------------------

    def send(self, pkt_type, payload, addr, reliable=False, compress=False):
        """Envoie un paquet a un peer. Fragmente automatiquement si necessaire."""
        with self.lock:
            peer = self.get_peer(addr)
            flags = 0
            if reliable:
                flags |= FLAG_RELIABLE

            # Compression optionnelle
            if compress and len(payload) > 100:
                compressed = zlib.compress(payload, 1)
                if len(compressed) < len(payload):
                    payload = compressed
                    flags |= FLAG_COMPRESSED

            # Fragmentation si le payload depasse la taille max
            if len(payload) > MAX_PAYLOAD:
                self._send_fragmented(peer, pkt_type, flags, payload, addr)
                return

            seq = peer.next_seq()
            pkt = Packet(pkt_type, flags, seq, peer.remote_seq, payload)
            raw = pkt.encode()

            try:
                self.sock.sendto(raw, addr)
                peer.packets_sent += 1
                peer.bytes_sent += len(raw)
                peer.last_send_time = time.time()

                if reliable:
                    peer.pending_reliable[seq] = (raw, time.time(), 0)
            except (OSError, socket.error) as e:
                print(f"[UDP] Erreur envoi vers {addr}: {e}")

    def send_raw(self, data, addr):
        """Envoi brut sans tracking (pour rendezvous/punch)."""
        try:
            self.sock.sendto(data, addr)
        except (OSError, socket.error):
            pass

    def _send_fragmented(self, peer, pkt_type, base_flags, payload, addr):
        """Decoupe un gros payload en fragments."""
        frag_id = self._next_frag_id
        self._next_frag_id = (self._next_frag_id + 1) & 0xFF

        total = (len(payload) + FRAGMENT_PAYLOAD - 1) // FRAGMENT_PAYLOAD
        flags = base_flags | FLAG_FRAGMENTED

        for i in range(total):
            chunk = payload[i * FRAGMENT_PAYLOAD:(i + 1) * FRAGMENT_PAYLOAD]
            # Header fragment: frag_id(1) + index(1) + total(1) + original_type(1)
            frag_header = struct.pack("!BBBB", frag_id, i, total, pkt_type)
            frag_payload = frag_header + chunk

            seq = peer.next_seq()
            pkt = Packet(PKT_FRAGMENT, flags, seq, peer.remote_seq, frag_payload)
            raw = pkt.encode()

            try:
                self.sock.sendto(raw, addr)
                peer.packets_sent += 1
                peer.bytes_sent += len(raw)

                if base_flags & FLAG_RELIABLE:
                    peer.pending_reliable[seq] = (raw, time.time(), 0)
            except (OSError, socket.error):
                pass

        peer.last_send_time = time.time()

    # ------------------------------------------------------------------
    #  RECEPTION
    # ------------------------------------------------------------------

    def poll(self, max_events=100):
        """Recoit et traite les paquets en attente. Non-bloquant. Retourne les paquets traites."""
        events = []
        callbacks_to_call = []
        for _ in range(max_events):
            try:
                data, addr = self.sock.recvfrom(65535)
            except (BlockingIOError, socket.error):
                break

            pkt = Packet.decode(data)
            if pkt is None:
                continue

            with self.lock:
                peer = self.get_peer(addr)
                peer.packets_received += 1
                peer.bytes_received += len(data)
                peer.last_recv_time = time.time()
                peer.update_remote_seq(pkt.seq)

                # Traiter les ACKs pour les paquets fiables
                if pkt.ack:
                    peer.ack_reliable(pkt.ack)

                # ACK explicite
                if pkt.pkt_type == PKT_ACK:
                    continue

                # Dedup paquets fiables
                if pkt.is_reliable and peer.is_duplicate_reliable(pkt.seq):
                    # Renvoyer l'ACK quand meme
                    ack_pkt = Packet(PKT_ACK, 0, 0, pkt.seq)
                    try:
                        self.sock.sendto(ack_pkt.encode(), addr)
                    except (OSError, socket.error):
                        pass
                    continue

                # Envoyer ACK pour paquets fiables
                if pkt.is_reliable:
                    ack_pkt = Packet(PKT_ACK, 0, 0, pkt.seq)
                    try:
                        self.sock.sendto(ack_pkt.encode(), addr)
                    except (OSError, socket.error):
                        pass

                # Gestion des fragments
                if pkt.pkt_type == PKT_FRAGMENT:
                    result = self._handle_fragment(peer, pkt)
                    if result is not None:
                        orig_type, reassembled_payload = result
                        # Decompresser si necessaire
                        if pkt.flags & FLAG_COMPRESSED:
                            try:
                                reassembled_payload = zlib.decompress(reassembled_payload)
                            except zlib.error:
                                continue
                        reassembled = Packet(orig_type, pkt.flags & ~FLAG_FRAGMENTED,
                                             pkt.seq, pkt.ack, reassembled_payload)
                        events.append((reassembled, addr))
                        if orig_type in self._callbacks:
                            callbacks_to_call.append((self._callbacks[orig_type], reassembled, addr))
                    continue

                # Decompresser
                if pkt.is_compressed:
                    try:
                        pkt.payload = zlib.decompress(pkt.payload)
                        pkt.flags &= ~FLAG_COMPRESSED
                    except zlib.error:
                        continue

                # PING/PONG
                if pkt.pkt_type == PKT_PING:
                    pong = Packet(PKT_PONG, 0, peer.next_seq(), peer.remote_seq, pkt.payload)
                    try:
                        self.sock.sendto(pong.encode(), addr)
                    except (OSError, socket.error):
                        pass
                    continue

                if pkt.pkt_type == PKT_PONG:
                    if pkt.payload and len(pkt.payload) == 8:
                        sent_time = struct.unpack("!d", pkt.payload)[0]
                        sample = time.time() - sent_time
                        peer.rtt_smoothed = 0.875 * peer.rtt_smoothed + 0.125 * sample
                        peer.rtt = peer.rtt_smoothed
                    continue

                events.append((pkt, addr))
                if pkt.pkt_type in self._callbacks:
                    callbacks_to_call.append((self._callbacks[pkt.pkt_type], pkt, addr))

        for cb, p, a in callbacks_to_call:
            cb(p, a)

        return events

    def _handle_fragment(self, peer, pkt):
        """Reassemble les fragments. Retourne (orig_type, payload) si complet, sinon None."""
        if len(pkt.payload) < 4:
            return None
        frag_id, index, total, orig_type = struct.unpack("!BBBB", pkt.payload[:4])
        chunk = pkt.payload[4:]

        key = frag_id
        if key not in peer.fragment_buffers:
            peer.fragment_buffers[key] = {}
            peer.fragment_totals[key] = total

        peer.fragment_buffers[key][index] = chunk

        if len(peer.fragment_buffers[key]) == total:
            # Reassembler dans l'ordre
            reassembled = b''.join(peer.fragment_buffers[key][i] for i in range(total))
            del peer.fragment_buffers[key]
            del peer.fragment_totals[key]
            return (orig_type, reassembled)

        return None

    # ------------------------------------------------------------------
    #  MAINTENANCE (thread daemon)
    # ------------------------------------------------------------------

    def _maintenance_loop(self):
        """Boucle de maintenance: retransmissions, pings, detection timeouts."""
        while self._running:
            now = time.time()
            callbacks_to_call = []
            with self.lock:
                dead_peers = []
                for addr, peer in list(self.peers.items()):
                    if not peer.connected:
                        continue

                    # Timeout deconnexion
                    if now - peer.last_recv_time > DISCONNECT_TIMEOUT:
                        dead_peers.append(addr)
                        continue

                    # Retransmissions
                    for seq, (raw, send_time, retries) in list(peer.pending_reliable.items()):
                        timeout = max(RELIABLE_TIMEOUT, peer.rtt * 2.5)
                        if now - send_time > timeout:
                            if retries >= MAX_RETRIES:
                                dead_peers.append(addr)
                                break
                            try:
                                self.sock.sendto(raw, addr)
                                peer.pending_reliable[seq] = (raw, now, retries + 1)
                            except (OSError, socket.error):
                                pass

                    # Ping periodique
                    if now - peer.last_ping_time > PING_INTERVAL:
                        peer.last_ping_time = now
                        ping_payload = struct.pack("!d", now)
                        ping_seq = peer.next_seq()
                        ping_pkt = Packet(PKT_PING, 0, ping_seq, peer.remote_seq, ping_payload)
                        try:
                            self.sock.sendto(ping_pkt.encode(), addr)
                        except (OSError, socket.error):
                            pass

                for addr in dead_peers:
                    peer = self.peers.get(addr)
                    if peer:
                        print(f"[UDP] Peer {addr} timeout (joueur {peer.player_id})")
                        peer.connected = False
                        if PKT_DISCONNECT in self._callbacks:
                            callbacks_to_call.append((self._callbacks[PKT_DISCONNECT], Packet(PKT_DISCONNECT, 0, 0, 0), addr))

            for cb, pkt, addr in callbacks_to_call:
                cb(pkt, addr)

            time.sleep(0.02)  # 50 Hz maintenance


# ======================================================================
#  HELPER : Obtenir l'IP locale et publique
# ======================================================================

def obtenir_ip_locale():
    """Retourne l'IP locale de la machine sur le reseau."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def obtenir_ip_publique():
    """Tente de recuperer l'IP publique via un service STUN simplifie."""
    try:
        import urllib.request
        response = urllib.request.urlopen("https://api.ipify.org", timeout=3)
        return response.read().decode('utf-8').strip()
    except Exception:
        return None
