"""Protocole UDP custom pour le netcode d'Écho.

Trois canaux :
  - UNRELIABLE (0) : snapshots de positions/vélocités ; drop si hors séquence.
  - RELIABLE   (1) : événements (livrés, ordonnés, retransmis jusqu'à ACK).
  - CONTROL    (2) : handshake UDP, heartbeat, disconnect.

Tous les paquets partagent le même header binaire de 12 octets :
    !IIHBB  ->  seq(uint32) ack(uint32) ack_bits(uint16) channel(uint8) type(uint8)

Le ``seq`` est incrémenté pour **chaque** paquet sortant (toutes canaux confondus).
``ack`` / ``ack_bits`` suivent la technique Glenn Fiedler (cf. gafferongames.com).
"""

import struct

# ---------------------------------------------------------------------------
#  Canaux
# ---------------------------------------------------------------------------
CANAL_UNRELIABLE = 0
CANAL_RELIABLE   = 1
CANAL_CONTROL    = 2

# ---------------------------------------------------------------------------
#  Types par canal
# ---------------------------------------------------------------------------
# UNRELIABLE
TYPE_SNAPSHOT        = 0x01   # serveur -> client : positions struct
TYPE_ETAT_DISCRET    = 0x02   # serveur -> client : reste de l'état (pickle, 10 Hz)
TYPE_INPUTS_CONTINUS = 0x03   # client  -> serveur : clavier continu (pickle court)

# RELIABLE
TYPE_INPUT_ONESHOT   = 0x10   # client  -> serveur : echo / torche / interagir
TYPE_VIS_MAP_FULL    = 0x11   # serveur -> client : vis_map complète (pickle)
TYPE_EVENT_SON       = 0x12   # serveur -> client : son à rejouer

# CONTROL
TYPE_HANDSHAKE_UDP   = 0x20   # client  -> serveur : token remis via TCP
TYPE_HANDSHAKE_ACK   = 0x21   # serveur -> client : confirme enregistrement
TYPE_HEARTBEAT       = 0x22   # bidirectionnel, 1 Hz
TYPE_DISCONNECT      = 0x23   # fermeture propre

# ---------------------------------------------------------------------------
#  Header
# ---------------------------------------------------------------------------
HEADER_FMT = '!IIHBB'
HEADER_TAILLE = struct.calcsize(HEADER_FMT)  # 12

MTU_SOFT = 1200  # on reste sous l'MTU ethernet typique pour éviter la fragmentation


def encoder_header(seq: int, ack: int, ack_bits: int, channel: int, type_: int) -> bytes:
    return struct.pack(HEADER_FMT, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF,
                       ack_bits & 0xFFFF, channel & 0xFF, type_ & 0xFF)


def decoder_header(data: bytes):
    if len(data) < HEADER_TAILLE:
        raise ValueError(f"Paquet trop court ({len(data)} < {HEADER_TAILLE})")
    seq, ack, ack_bits, channel, type_ = struct.unpack(HEADER_FMT, data[:HEADER_TAILLE])
    return seq, ack, ack_bits, channel, type_, data[HEADER_TAILLE:]


# ---------------------------------------------------------------------------
#  Flags joueur (snapshot)
# ---------------------------------------------------------------------------
JFLAG_EN_DASH        = 1 << 0
JFLAG_EN_ATTAQUE     = 1 << 1
JFLAG_EST_MORT       = 1 << 2
JFLAG_DIRECTION_DROITE = 1 << 3   # 1 = droite, 0 = gauche

EFLAG_EST_MORT   = 1 << 0
EFLAG_CLIGNOTE   = 1 << 1


# ---------------------------------------------------------------------------
#  Encodage snapshot (positions joueurs + ennemis)
# ---------------------------------------------------------------------------
# Snapshot body :
#   uint32 t_serveur_ms         (timestamp pour interpolation)
#   uint8  nb_joueurs
#     pour chaque :  int8 id | float32 x | float32 y | float32 vx | float32 vy | uint8 flags
#   uint8  nb_ennemis
#     pour chaque :  uint16 id | float32 x | float32 y | uint8 flags

_JOUEUR_FMT = '!bffffB'
_JOUEUR_TAILLE = struct.calcsize(_JOUEUR_FMT)

_ENNEMI_FMT = '!HffB'
_ENNEMI_TAILLE = struct.calcsize(_ENNEMI_FMT)


_BOSS_FMT = '!Bff'  # has_boss (uint8), x (float32), y (float32)
_BOSS_TAILLE = struct.calcsize(_BOSS_FMT)


def encoder_snapshot(t_serveur_ms: int, joueurs: list, ennemis: list, boss=None) -> bytes:
    """joueurs: liste de dict {id, x, y, vx, vy, flags}. ennemis idem sans vx/vy.
    boss: dict {x, y} ou None si défait/inexistant."""
    morceaux = [struct.pack('!IB', t_serveur_ms & 0xFFFFFFFF, len(joueurs))]
    for j in joueurs:
        morceaux.append(struct.pack(_JOUEUR_FMT,
                                    j['id'], j['x'], j['y'],
                                    j.get('vx', 0.0), j.get('vy', 0.0),
                                    j.get('flags', 0)))
    morceaux.append(struct.pack('!B', len(ennemis)))
    for e in ennemis:
        morceaux.append(struct.pack(_ENNEMI_FMT,
                                    e['id'], e['x'], e['y'],
                                    e.get('flags', 0)))
    has_boss = 1 if boss else 0
    bx = float(boss['x']) if boss else 0.0
    by = float(boss['y']) if boss else 0.0
    morceaux.append(struct.pack(_BOSS_FMT, has_boss, bx, by))
    return b''.join(morceaux)


def decoder_snapshot(payload: bytes) -> dict:
    off = 0
    t_serveur_ms, nb_j = struct.unpack_from('!IB', payload, off)
    off += 5
    joueurs = []
    for _ in range(nb_j):
        jid, x, y, vx, vy, flags = struct.unpack_from(_JOUEUR_FMT, payload, off)
        off += _JOUEUR_TAILLE
        joueurs.append({'id': jid, 'x': x, 'y': y, 'vx': vx, 'vy': vy, 'flags': flags})
    (nb_e,) = struct.unpack_from('!B', payload, off)
    off += 1
    ennemis = []
    for _ in range(nb_e):
        eid, x, y, flags = struct.unpack_from(_ENNEMI_FMT, payload, off)
        off += _ENNEMI_TAILLE
        ennemis.append({'id': eid, 'x': x, 'y': y, 'flags': flags})
    boss = None
    if off + _BOSS_TAILLE <= len(payload):
        has_boss, bx, by = struct.unpack_from(_BOSS_FMT, payload, off)
        if has_boss:
            boss = {'x': bx, 'y': by}
    return {'t': t_serveur_ms, 'joueurs': joueurs, 'ennemis': ennemis, 'boss': boss}


# ---------------------------------------------------------------------------
#  Utilitaires séquence
# ---------------------------------------------------------------------------
def seq_plus_recent(a: int, b: int) -> bool:
    """Compare deux seq uint32 en tenant compte du wrap-around."""
    MOITIE = 1 << 31
    diff = (a - b) & 0xFFFFFFFF
    return 0 < diff < MOITIE
