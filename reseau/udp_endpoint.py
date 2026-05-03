"""Wrapper autour d'un socket UDP non-bloquant.

Un seul `UdpEndpoint` partagé par tout le processus (hôte : 1 pour le serveur et
peut-être 1 pour le client loopback). Le dispatch vers les `ConnexionUDP` se
fait par `(ip, port)` dans les utilisateurs.

La méthode `pomper()` appelle `recvfrom` en boucle jusqu'à `BlockingIOError`
et renvoie la liste `[(raw_bytes, addr), ...]`. Aucune allocation de thread
n'est réalisée : on reste dans la boucle Pygame principale.
"""

import socket
import errno


class UdpEndpoint:
    def __init__(self, bind_host: str, bind_port: int = 0):
        # `bind_host` est requis : on évite de binder sur toutes les interfaces
        # par défaut (cf. CodeQL py/bind-socket-all-network-interfaces).
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Buffers un peu plus larges : on accepte des bursts de 1 MB max.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        except OSError:
            pass
        self.sock.bind((bind_host, bind_port))
        self.sock.setblocking(False)
        self.bind_host = bind_host
        self.bind_port = self.sock.getsockname()[1]

    def envoyer(self, data: bytes, addr: tuple) -> bool:
        try:
            self.sock.sendto(data, addr)
            return True
        except (BlockingIOError, InterruptedError):
            return False
        except OSError as exc:
            # Destination inatteignable : on log mais on ne tue pas la boucle.
            if exc.errno in (errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH):
                return False
            # Pour tout le reste on remonte.
            raise

    def pomper(self, max_paquets: int = 256):
        """Drain le socket. Retourne une liste de (bytes, addr)."""
        paquets = []
        for _ in range(max_paquets):
            try:
                data, addr = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            paquets.append((data, addr))
        return paquets

    def fermer(self):
        try:
            self.sock.close()
        except Exception:
            pass
