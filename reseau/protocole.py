# reseau/protocole.py
# Fonctions réseau partagées entre le client et le serveur.
# Évite la duplication de code (_recvall, _recv_complet, _send_complet).

import socket
import pickle


def obtenir_ip_locale():
    """Retourne l'IP locale de la machine sur le réseau."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_locale = s.getsockname()[0]
        s.close()
        return ip_locale
    except Exception:
        return "127.0.0.1"


def obtenir_ip_hamachi():
    """Retourne l'IP Hamachi (VPN) si disponible."""
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in all_ips:
            if ip.startswith("25."):
                return ip
        return "Non connecté"
    except Exception:
        return "Non connecté"


def recvall(sock, n):
    """Lit exactement n octets depuis le socket (TCP peut fragmenter)."""
    data = b""
    while len(data) < n:
        paquet = sock.recv(n - len(data))
        if not paquet:
            raise EOFError("Connexion fermee")
        data += paquet
    return data


def recv_complet(sock):
    """Reçoit un paquet complet : 4 octets taille + payload pickle."""
    header = recvall(sock, 4)
    taille = int.from_bytes(header, 'big')
    if taille > 10_000_000:  # sécurité : max 10 MB
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in header)
        raise ValueError(
            f"Paquet suspect trop grand : {taille} octets "
            f"(bytes bruts: {header.hex()} / ASCII: '{ascii_repr}') "
            f"— probable proxy HTTP ou données corrompues"
        )
    return pickle.loads(recvall(sock, taille))


def send_complet(sock, obj):
    """Envoie un objet pickle précédé de 4 octets de taille."""
    data = pickle.dumps(obj)
    sock.sendall(len(data).to_bytes(4, 'big') + data)
