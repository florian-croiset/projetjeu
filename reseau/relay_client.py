# reseau/relay_client.py
# Helpers côté client/host pour se connecter au serveur relay.

import socket
import json


def _recv_line(sock):
    """Lit une ligne JSON terminée par \\n depuis le socket."""
    buf = b""
    while True:
        octet = sock.recv(1)
        if not octet:
            raise EOFError("Connexion relay fermée")
        if octet == b'\n':
            return buf.decode('utf-8')
        buf += octet


def _send_json(sock, obj):
    """Envoie un objet JSON suivi de \\n."""
    sock.sendall(json.dumps(obj).encode('utf-8') + b'\n')


def relay_creer_room(relay_host, relay_port):
    """Connecte au relay et crée une room.

    Retourne (ctrl_socket, code_room).
    Le ctrl_socket doit rester ouvert tant que la room existe.
    """
    print(f"[RELAY_CLIENT] Création room: connexion à {relay_host}:{relay_port}...")
    ctrl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ctrl.settimeout(10)
    ctrl.connect((relay_host, relay_port))
    print(f"[RELAY_CLIENT] Connecté au relay, envoi cmd 'host'...")
    _send_json(ctrl, {"cmd": "host"})
    reponse = json.loads(_recv_line(ctrl))
    print(f"[RELAY_CLIENT] Réponse relay: {reponse}")

    if "error" in reponse:
        ctrl.close()
        raise ConnectionError(f"Relay: {reponse['error']}")

    code = reponse["code"]
    # Passer en mode non-bloquant pour le canal contrôle
    # (sera lu dans un thread dédié)
    ctrl.settimeout(None)
    print(f"[RELAY_CLIENT] Room créée, code={code}")
    return ctrl, code


def relay_attendre_client(ctrl_socket, relay_host, relay_port):
    """Attend qu'un nouveau client rejoigne via le relay.

    Lit un event 'new_client' sur le canal contrôle,
    puis ouvre un canal data vers le relay pour ce slot.
    Retourne un socket TCP prêt à être utilisé comme un client direct.
    """
    # Lire l'event new_client sur le canal contrôle
    ligne = _recv_line(ctrl_socket)
    event = json.loads(ligne)

    if "error" in event:
        raise ConnectionError(f"Relay: {event['error']}")
    if event.get("event") != "new_client":
        raise ConnectionError(f"Relay: event inattendu: {event}")

    slot_id = event["slot"]
    code = event.get("code", "")

    # Ouvrir un canal data pour ce slot
    # On a besoin du code room — on le récupère depuis le ctrl
    # Le code n'est pas dans l'event, on doit le passer en paramètre
    # En fait le host connaît déjà son code. On le passe via le serveur.
    # Pour simplifier, on stocke le code dans l'event côté relay.
    # Mais le relay ne l'envoie pas encore. On va utiliser le code
    # que le host connaît déjà.

    return slot_id


def relay_ouvrir_canal_data(relay_host, relay_port, code_room, slot_id):
    """Ouvre un canal data sur le relay pour un slot donné.

    Retourne un socket TCP bridgé avec le client correspondant.
    """
    print(f"[RELAY_CLIENT] Ouverture canal data: {relay_host}:{relay_port} room={code_room} slot={slot_id}")
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.settimeout(15)
    data_sock.connect((relay_host, relay_port))
    _send_json(data_sock, {"cmd": "data", "code": code_room, "slot": slot_id})
    reponse = json.loads(_recv_line(data_sock))
    print(f"[RELAY_CLIENT] Réponse canal data: {reponse}")

    if "error" in reponse:
        data_sock.close()
        raise ConnectionError(f"Relay: {reponse['error']}")

    if reponse.get("status") != "bridged":
        data_sock.close()
        raise ConnectionError(f"Relay: réponse inattendue: {reponse}")

    # Le socket est maintenant bridgé avec le client
    data_sock.settimeout(None)
    print(f"[RELAY_CLIENT] Canal data bridgé pour slot {slot_id}")
    return data_sock


def relay_rejoindre(relay_host, relay_port, code_room):
    """Connecte au relay via un room code.

    Retourne un socket TCP bridgé avec le serveur hôte.
    Utilisable directement avec send_complet/recv_complet.
    """
    print(f"[RELAY_CLIENT] Rejoindre: connexion à {relay_host}:{relay_port} avec code '{code_room}'...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    try:
        sock.connect((relay_host, relay_port))
    except Exception as e:
        print(f"[RELAY_CLIENT] Échec connexion TCP au relay {relay_host}:{relay_port}: {type(e).__name__}: {e}")
        raise
    print(f"[RELAY_CLIENT] Connecté au relay, envoi cmd 'join' code='{code_room}'...")
    _send_json(sock, {"cmd": "join", "code": code_room.upper().strip()})
    print(f"[RELAY_CLIENT] Attente réponse du relay (bridge)...")
    reponse = json.loads(_recv_line(sock))
    print(f"[RELAY_CLIENT] Réponse relay: {reponse}")

    if "error" in reponse:
        sock.close()
        raise ConnectionError(f"Relay: {reponse['error']}")

    if reponse.get("status") != "bridged":
        sock.close()
        raise ConnectionError(f"Relay: réponse inattendue: {reponse}")

    # Le socket est maintenant bridgé avec le host
    sock.settimeout(None)
    print(f"[RELAY_CLIENT] Bridge établi avec le serveur hôte via relay")
    return sock
