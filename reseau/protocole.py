# reseau/protocole.py
# Fonctions réseau partagées entre le client et le serveur.
# Évite la duplication de code (_recvall, _recv_complet, _send_complet).

import socket
import pickle
import zlib


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


def obtenir_ip_vpn():
    """Retourne l'IP VPN (Tailscale ou Hamachi) si disponible."""
    import subprocess
    import sys
    # Essayer de récupérer l'IP Tailscale via la CLI (très très fiable sous Linux/Crostini)
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        output = subprocess.check_output(
            ["tailscale", "ip", "-4"],
            stderr=subprocess.DEVNULL,
            timeout=1,
            **kwargs
        ).decode('utf-8').strip()
        if output:
            return output.split('\\n')[0].strip()
    except Exception:
        pass

    # Fallback : vérifier les interfaces réseaux via Python (pour Windows surtout)
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]

        # IP Hamachi (commence par 25.)
        for ip in all_ips:
            if ip.startswith("25."):
                return ip

        # IP Tailscale sous Windows (100.x.x.x). Sous Linux/Crostini on utilise la commande en haut
        # car Crostini utilise aussi 100.x pour son IP locale.
        if sys.platform != "linux":
            for ip in all_ips:
                if ip.startswith("100."):
                    return ip
    except Exception:
        pass

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
    """Reçoit un paquet complet : 4 octets taille + payload pickle compressé zlib."""
    header = recvall(sock, 4)
    taille = int.from_bytes(header, 'big')
    if taille > 10_000_000:  # sécurité : max 10 MB
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in header)
        raise ValueError(
            f"Paquet suspect trop grand : {taille} octets "
            f"(bytes bruts: {header.hex()} / ASCII: '{ascii_repr}') "
            f"— probable proxy HTTP ou données corrompues"
        )
    return pickle.loads(zlib.decompress(recvall(sock, taille)))


def send_complet(sock, obj):
    """Envoie un objet pickle compressé zlib précédé de 4 octets de taille."""
    data = zlib.compress(pickle.dumps(obj), 1)
    sock.sendall(len(data).to_bytes(4, 'big') + data)
