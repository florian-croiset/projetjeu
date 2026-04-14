# reseau/relay_server.py
# Serveur relay TCP standalone pour le multijoueur via room codes.
# Permet à deux joueurs de se connecter sans port forwarding ni VPN.
# Usage : python3 -m reseau.relay_server [port]

import socket
import threading
import json
import secrets
import string
import time
import sys


TAILLE_BUF = 8192
EXPIRATION_ROOM = 300       # 5 minutes sans activité
NETTOYAGE_INTERVAL = 30     # secondes entre chaque nettoyage


def _generer_code(longueur=6):
    """Génère un code room aléatoire (6 lettres majuscules)."""
    return ''.join(secrets.choice(string.ascii_uppercase) for _ in range(longueur))


def _recv_line(sock):
    """Lit une ligne JSON terminée par \\n depuis le socket."""
    buf = b""
    while True:
        octet = sock.recv(1)
        if not octet:
            raise EOFError("Connexion fermée")
        if octet == b'\n':
            return buf.decode('utf-8')
        buf += octet


def _send_json(sock, obj):
    """Envoie un objet JSON suivi de \\n."""
    sock.sendall(json.dumps(obj).encode('utf-8') + b'\n')


class Room:
    def __init__(self, code, host_ctrl):
        self.code = code
        self.host_ctrl = host_ctrl
        self.next_slot = 1
        # slot_id → {"client": socket_client, "host_data": socket_host_data | None}
        self.slots = {}
        self.derniere_activite = time.time()
        self.lock = threading.Lock()


class RelayServer:
    def __init__(self, port=7777):
        self.port = port
        self.rooms = {}          # code → Room
        self.lock = threading.Lock()

    def demarrer(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.port))
        sock.listen()
        print(f"[RELAY] Démarré sur le port {self.port}")

        # Thread de nettoyage des rooms expirées
        t = threading.Thread(target=self._nettoyer_boucle, daemon=True)
        t.start()

        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=self._gerer_connexion, args=(conn, addr), daemon=True)
            t.start()

    # ------------------------------------------------------------------
    #  Dispatch des connexions entrantes
    # ------------------------------------------------------------------

    def _gerer_connexion(self, sock, addr):
        try:
            ligne = _recv_line(sock)
            msg = json.loads(ligne)
            cmd = msg.get("cmd")

            if cmd == "host":
                self._cmd_host(sock, addr)
            elif cmd == "join":
                self._cmd_join(sock, addr, msg.get("code", ""))
            elif cmd == "data":
                self._cmd_data(sock, addr, msg.get("code", ""), msg.get("slot", 0))
            else:
                _send_json(sock, {"error": "commande inconnue"})
                sock.close()
        except (EOFError, ConnectionResetError, json.JSONDecodeError) as e:
            print(f"[RELAY] Erreur connexion {addr}: {e}")
            try:
                sock.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    #  Commande : host — créer une room
    # ------------------------------------------------------------------

    def _cmd_host(self, sock, addr):
        with self.lock:
            # Générer un code unique
            for _ in range(100):
                code = _generer_code()
                if code not in self.rooms:
                    break
            else:
                _send_json(sock, {"error": "impossible de générer un code"})
                sock.close()
                return

            room = Room(code, sock)
            self.rooms[code] = room

        _send_json(sock, {"code": code})
        print(f"[RELAY] Room {code} créée par {addr}")

        # Boucle de contrôle : garde la connexion ouverte pour recevoir les events
        # (la connexion reste active tant que le host est connecté)
        try:
            while True:
                # Le host ne devrait rien envoyer sur le canal contrôle
                # mais on garde la connexion vivante
                sock.settimeout(EXPIRATION_ROOM)
                data = sock.recv(1)
                if not data:
                    break
                # Mise à jour activité
                room.derniere_activite = time.time()
        except (socket.timeout, EOFError, ConnectionResetError, OSError):
            pass
        finally:
            print(f"[RELAY] Room {code} fermée (host déconnecté)")
            self._fermer_room(code)

    # ------------------------------------------------------------------
    #  Commande : join — un client rejoint une room
    # ------------------------------------------------------------------

    def _cmd_join(self, sock, addr, code):
        code = code.upper().strip()
        with self.lock:
            room = self.rooms.get(code)
            if not room:
                _send_json(sock, {"error": "room introuvable"})
                sock.close()
                return

        with room.lock:
            slot_id = room.next_slot
            room.next_slot += 1
            room.slots[slot_id] = {"client": sock, "host_data": None}
            room.derniere_activite = time.time()

        # Notifier le host qu'un nouveau client veut se connecter
        try:
            _send_json(room.host_ctrl, {"event": "new_client", "slot": slot_id})
        except (OSError, BrokenPipeError):
            _send_json(sock, {"error": "host déconnecté"})
            sock.close()
            return

        print(f"[RELAY] Client {addr} rejoint room {code} (slot {slot_id})")

        # Attendre que le host ouvre son canal data pour ce slot
        deadline = time.time() + 15  # 15s max
        while time.time() < deadline:
            with room.lock:
                slot_info = room.slots.get(slot_id)
                if slot_info and slot_info.get("host_data"):
                    break
            time.sleep(0.05)
        else:
            _send_json(sock, {"error": "timeout: host n'a pas répondu"})
            sock.close()
            return

        # Bridge prêt
        _send_json(sock, {"status": "bridged"})

        host_data_sock = slot_info["host_data"]
        print(f"[RELAY] Bridge actif : room {code} slot {slot_id}")

        # Lancer le bridge bidirectionnel
        self._bridge(sock, host_data_sock, code, slot_id)

    # ------------------------------------------------------------------
    #  Commande : data — le host ouvre un canal data pour un slot
    # ------------------------------------------------------------------

    def _cmd_data(self, sock, addr, code, slot_id):
        code = code.upper().strip()
        with self.lock:
            room = self.rooms.get(code)
            if not room:
                _send_json(sock, {"error": "room introuvable"})
                sock.close()
                return

        with room.lock:
            slot_info = room.slots.get(slot_id)
            if not slot_info:
                _send_json(sock, {"error": "slot invalide"})
                sock.close()
                return
            slot_info["host_data"] = sock
            room.derniere_activite = time.time()

        _send_json(sock, {"status": "bridged"})
        print(f"[RELAY] Canal data host ouvert : room {code} slot {slot_id}")

        # Le bridge sera géré par le thread du join (qui attend host_data)
        # Ce thread peut maintenant se terminer — le socket reste ouvert

    # ------------------------------------------------------------------
    #  Bridge bidirectionnel
    # ------------------------------------------------------------------

    def _bridge(self, sock_a, sock_b, code, slot_id):
        """Forward bidirectionnel entre deux sockets. Bloque jusqu'à déconnexion."""

        def _forward(src, dst, nom):
            try:
                while True:
                    data = src.recv(TAILLE_BUF)
                    if not data:
                        break
                    dst.sendall(data)
            except (OSError, BrokenPipeError, ConnectionResetError):
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t1 = threading.Thread(target=_forward, args=(sock_a, sock_b, "client→host"), daemon=True)
        t2 = threading.Thread(target=_forward, args=(sock_b, sock_a, "host→client"), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        print(f"[RELAY] Bridge terminé : room {code} slot {slot_id}")
        try:
            sock_a.close()
        except OSError:
            pass
        try:
            sock_b.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    #  Nettoyage
    # ------------------------------------------------------------------

    def _fermer_room(self, code):
        with self.lock:
            room = self.rooms.pop(code, None)
        if not room:
            return
        # Fermer toutes les connexions
        for sock in [room.host_ctrl]:
            try:
                sock.close()
            except OSError:
                pass
        for slot_info in room.slots.values():
            for sock in [slot_info.get("client"), slot_info.get("host_data")]:
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass

    def _nettoyer_boucle(self):
        while True:
            time.sleep(NETTOYAGE_INTERVAL)
            maintenant = time.time()
            codes_expires = []
            with self.lock:
                for code, room in self.rooms.items():
                    if maintenant - room.derniere_activite > EXPIRATION_ROOM:
                        codes_expires.append(code)
            for code in codes_expires:
                print(f"[RELAY] Room {code} expirée, nettoyage")
                self._fermer_room(code)


def main():
    port = 7777
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python3 -m reseau.relay_server [port]")
            sys.exit(1)

    serveur = RelayServer(port)
    try:
        serveur.demarrer()
    except KeyboardInterrupt:
        print("\n[RELAY] Arrêt.")


if __name__ == "__main__":
    main()
