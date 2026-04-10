# reseau/rendezvous.py
# Serveur de rendez-vous pour le NAT Hole Punching UDP.
#
# Architecture :
#   1. L'hote cree une "room" sur le serveur de rendez-vous (code 6 caracteres)
#   2. Le serveur note l'IP:port publics de l'hote
#   3. Un client rejoint avec le code room
#   4. Le serveur envoie a chacun l'adresse publique de l'autre
#   5. Les deux peers s'envoient des paquets UDP simultanes (hole punch)
#   6. Une fois le premier paquet recu des deux cotes, la connexion directe est etablie
#
# Ce serveur peut tourner sur n'importe quel VPS accessible publiquement.
# En l'absence de serveur de rendez-vous, la connexion directe IP:port reste possible.

import socket
import struct
import threading
import time
import random
import string

# ======================================================================
#  PROTOCOLE RENDEZVOUS
# ======================================================================

# Messages client -> rendez-vous
RDV_CREATE_ROOM  = 0x01  # Creer une room (hote)
RDV_JOIN_ROOM    = 0x02  # Rejoindre une room (client)
RDV_KEEPALIVE    = 0x03  # Garder la room ouverte

# Messages rendez-vous -> client
RDV_ROOM_CREATED = 0x11  # Room creee, voici le code
RDV_PEER_INFO    = 0x12  # Voici l'adresse de ton peer
RDV_ERROR        = 0x13  # Erreur (room introuvable, pleine, etc.)
RDV_PUNCH_NOW    = 0x14  # Les deux peers sont la, commencez le hole punch

# Format header rendez-vous : type(1) + payload
RDV_HEADER = "!B"


def _generate_room_code(length=6):
    """Genere un code room aleatoire (lettres majuscules + chiffres)."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


# ======================================================================
#  ENCODAGE / DECODAGE
# ======================================================================

def encode_create_room(game_port):
    """Hote -> Rendez-vous : demande de creation de room."""
    return struct.pack("!BH", RDV_CREATE_ROOM, game_port)


def encode_join_room(room_code, game_port):
    """Client -> Rendez-vous : demande de rejoindre."""
    code_bytes = room_code.encode('ascii')[:6].ljust(6, b'\x00')
    return struct.pack("!B6sH", RDV_JOIN_ROOM, code_bytes, game_port)


def encode_keepalive(room_code):
    """Keepalive pour garder la room ouverte."""
    code_bytes = room_code.encode('ascii')[:6].ljust(6, b'\x00')
    return struct.pack("!B6s", RDV_KEEPALIVE, code_bytes)


def encode_room_created(room_code):
    """Rendez-vous -> Hote : room creee."""
    code_bytes = room_code.encode('ascii')[:6].ljust(6, b'\x00')
    return struct.pack("!B6s", RDV_ROOM_CREATED, code_bytes)


def encode_peer_info(peer_ip, peer_port, game_port):
    """Rendez-vous -> Client : info du peer pour hole punch."""
    ip_bytes = socket.inet_aton(peer_ip)
    return struct.pack("!B4sHH", RDV_PEER_INFO, ip_bytes, peer_port, game_port)


def decode_peer_info(data):
    """Decode les infos du peer. Retourne (ip, port, game_port)."""
    if len(data) < 9:
        return None
    _, ip_bytes, port, game_port = struct.unpack("!B4sHH", data[:9])
    ip = socket.inet_ntoa(ip_bytes)
    return ip, port, game_port


def encode_error(message):
    """Rendez-vous -> Client : erreur."""
    msg_bytes = message.encode('utf-8')[:128]
    return struct.pack("!BB", RDV_ERROR, len(msg_bytes)) + msg_bytes


def encode_punch_now(peer_ip, peer_port, game_port):
    """Rendez-vous -> Les deux peers : commencez le hole punch."""
    ip_bytes = socket.inet_aton(peer_ip)
    return struct.pack("!B4sHH", RDV_PUNCH_NOW, ip_bytes, peer_port, game_port)


def decode_punch_now(data):
    """Decode la commande punch. Retourne (ip, port, game_port)."""
    if len(data) < 9:
        return None
    _, ip_bytes, port, game_port = struct.unpack("!B4sHH", data[:9])
    ip = socket.inet_ntoa(ip_bytes)
    return ip, port, game_port


# ======================================================================
#  SERVEUR DE RENDEZ-VOUS
# ======================================================================

class Room:
    """Une room en attente de joueurs."""

    def __init__(self, code, host_addr, host_game_port):
        self.code = code
        self.host_addr = host_addr       # (ip, port) UDP public de l'hote
        self.host_game_port = host_game_port
        self.clients = []                # Liste de (addr, game_port)
        self.created_at = time.time()
        self.last_keepalive = time.time()

    @property
    def is_expired(self):
        return time.time() - self.last_keepalive > 120  # 2 minutes sans keepalive


class RendezvousServer:
    """Serveur UDP de rendez-vous pour faciliter le NAT hole punching."""

    def __init__(self, bind_addr=('0.0.0.0', 7777)):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(bind_addr)
        self.rooms = {}  # code -> Room
        self.lock = threading.Lock()
        self._running = True
        print(f"[RENDEZVOUS] Serveur demarre sur {bind_addr}")

    def run(self):
        """Boucle principale du serveur de rendez-vous."""
        # Thread nettoyage
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        while self._running:
            try:
                self.sock.settimeout(1.0)
                data, addr = self.sock.recvfrom(1024)
                if not data:
                    continue

                msg_type = data[0]
                self._handle_message(msg_type, data, addr)

            except socket.timeout:
                continue
            except (OSError, socket.error) as e:
                if self._running:
                    print(f"[RENDEZVOUS] Erreur: {e}")

    def _handle_message(self, msg_type, data, addr):
        """Traite un message entrant."""
        with self.lock:
            if msg_type == RDV_CREATE_ROOM:
                self._handle_create(data, addr)
            elif msg_type == RDV_JOIN_ROOM:
                self._handle_join(data, addr)
            elif msg_type == RDV_KEEPALIVE:
                self._handle_keepalive(data, addr)

    def _handle_create(self, data, addr):
        """L'hote cree une room."""
        if len(data) < 3:
            return
        _, game_port = struct.unpack("!BH", data[:3])

        # Generer un code unique
        for _ in range(100):
            code = _generate_room_code()
            if code not in self.rooms:
                break
        else:
            self.sock.sendto(encode_error("Impossible de creer la room"), addr)
            return

        room = Room(code, addr, game_port)
        self.rooms[code] = room

        print(f"[RENDEZVOUS] Room {code} creee par {addr} (game port: {game_port})")
        self.sock.sendto(encode_room_created(code), addr)

    def _handle_join(self, data, addr):
        """Un client rejoint une room."""
        if len(data) < 9:
            return
        _, code_bytes, game_port = struct.unpack("!B6sH", data[:9])
        code = code_bytes.decode('ascii').rstrip('\x00').upper()

        if code not in self.rooms:
            self.sock.sendto(encode_error("Room introuvable"), addr)
            return

        room = self.rooms[code]

        if len(room.clients) >= 2:
            self.sock.sendto(encode_error("Room pleine"), addr)
            return

        room.clients.append((addr, game_port))
        print(f"[RENDEZVOUS] {addr} rejoint room {code}")

        # Envoyer les infos de l'hote au client
        host_ip = room.host_addr[0]
        host_udp_port = room.host_addr[1]
        self.sock.sendto(
            encode_punch_now(host_ip, host_udp_port, room.host_game_port),
            addr
        )

        # Envoyer les infos du client a l'hote
        client_ip = addr[0]
        client_udp_port = addr[1]
        self.sock.sendto(
            encode_punch_now(client_ip, client_udp_port, game_port),
            room.host_addr
        )

        print(f"[RENDEZVOUS] Hole punch initie: {room.host_addr} <-> {addr}")

    def _handle_keepalive(self, data, addr):
        """Maintient la room active."""
        if len(data) < 7:
            return
        _, code_bytes = struct.unpack("!B6s", data[:7])
        code = code_bytes.decode('ascii').rstrip('\x00').upper()
        if code in self.rooms:
            self.rooms[code].last_keepalive = time.time()

    def _cleanup_loop(self):
        """Nettoie les rooms expirees."""
        while self._running:
            with self.lock:
                expired = [code for code, room in self.rooms.items() if room.is_expired]
                for code in expired:
                    print(f"[RENDEZVOUS] Room {code} expiree")
                    del self.rooms[code]
            time.sleep(10)

    def stop(self):
        self._running = False
        try:
            self.sock.close()
        except (OSError, socket.error):
            pass


# ======================================================================
#  CLIENT DE NAT HOLE PUNCHING
# ======================================================================

class HolePuncher:
    """Effectue le NAT hole punching cote client/hote.

    Usage:
        puncher = HolePuncher(local_transport)
        # En tant qu'hote:
        room_code = puncher.create_room(rendezvous_addr, game_port)
        # En tant que client:
        puncher.join_room(rendezvous_addr, room_code, game_port)
        # Attendre la connexion:
        peer_addr = puncher.wait_for_punch(timeout=10)
    """

    PUNCH_MAGIC = b'ECHO_PUNCH'

    def __init__(self, udp_socket):
        self.sock = udp_socket
        self.peer_addr = None
        self.room_code = None
        self._punch_target = None
        self._punch_event = threading.Event()

    def create_room(self, rendezvous_addr, game_port):
        """Cree une room sur le serveur de rendez-vous. Retourne le code room."""
        msg = encode_create_room(game_port)
        self.sock.sendto(msg, rendezvous_addr)

        # Attendre la reponse
        self.sock.settimeout(5.0)
        try:
            data, addr = self.sock.recvfrom(1024)
            if data[0] == RDV_ROOM_CREATED:
                _, code_bytes = struct.unpack("!B6s", data[:7])
                self.room_code = code_bytes.decode('ascii').rstrip('\x00')
                return self.room_code
            elif data[0] == RDV_ERROR:
                return None
        except socket.timeout:
            return None
        finally:
            self.sock.settimeout(None)

        return None

    def join_room(self, rendezvous_addr, room_code, game_port):
        """Rejoint une room et initie le hole punch."""
        msg = encode_join_room(room_code, game_port)
        self.sock.sendto(msg, rendezvous_addr)

    def process_rendezvous_message(self, data, addr):
        """Traite un message du serveur de rendez-vous."""
        if not data:
            return False

        msg_type = data[0]
        if msg_type == RDV_PUNCH_NOW:
            result = decode_punch_now(data)
            if result:
                peer_ip, peer_port, game_port = result
                self._punch_target = (peer_ip, peer_port)
                print(f"[PUNCH] Cible recue: {self._punch_target}")
                self._start_punching()
                return True
        elif msg_type == RDV_PEER_INFO:
            result = decode_peer_info(data)
            if result:
                peer_ip, peer_port, game_port = result
                self._punch_target = (peer_ip, peer_port)
                print(f"[PUNCH] Peer info: {self._punch_target}")
                self._start_punching()
                return True

        return False

    def _start_punching(self):
        """Envoie des paquets de punch en boucle dans un thread."""
        def punch_loop():
            for _ in range(50):  # 50 tentatives sur ~5 secondes
                if self._punch_event.is_set():
                    break
                try:
                    self.sock.sendto(self.PUNCH_MAGIC, self._punch_target)
                except (OSError, socket.error):
                    pass
                time.sleep(0.1)

        t = threading.Thread(target=punch_loop, daemon=True)
        t.start()

    def check_punch_packet(self, data, addr):
        """Verifie si un paquet recu est un punch reussi."""
        if data == self.PUNCH_MAGIC:
            self.peer_addr = addr
            self._punch_event.set()
            print(f"[PUNCH] Connexion etablie avec {addr}")
            return True
        return False

    def wait_for_punch(self, timeout=10):
        """Attend que le hole punch reussisse. Retourne l'adresse du peer ou None."""
        if self._punch_event.wait(timeout):
            return self.peer_addr
        return None

    @property
    def is_punched(self):
        return self._punch_event.is_set()


# ======================================================================
#  POINT D'ENTREE (pour lancer le serveur rendezvous standalone)
# ======================================================================

def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7777
    server = RendezvousServer(('0.0.0.0', port))
    try:
        server.run()
    except KeyboardInterrupt:
        server.stop()
        print("\n[RENDEZVOUS] Arrete.")


if __name__ == '__main__':
    main()
