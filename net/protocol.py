"""Echo network protocol: constants, message types and binary layouts.

Two transports carry the *same* messages:

* TCP  - every message is a frame ``[type, payload_bytes]`` (see ``net.framing``).
* UDP  - every message is a datagram of that ``type`` (see ``net.udp``).

Server -> client
    T_SNAPSHOT  unreliable, ~60 Hz. Binary: positions/flags of players,
                enemies and boss, plus a per-client "owner block" holding the
                physics state used for client-side prediction.
    T_STATE     reliable "latest wins" streams (players detail, enemies detail,
                world objects). ``codec`` payload ``{"k": key, ...}``. Only sent
                when the content changed.
    T_EVENTS    reliable one-shot events (sounds, ...). ``codec`` list.

Client -> server
    T_INPUT     unreliable, 60 Hz. Last few inputs, redundantly (loss tolerant).
    T_ACTION    reliable one-shot actions (echo, interact, torch, profile...).
    T_PING      unreliable, ~2 Hz. Echoed as T_PONG (RTT + clock sync).

Control (UDP only; TCP uses its own connection state)
    T_HANDSHAKE / T_HANDSHAKE_ACK / T_HEARTBEAT / T_DISCONNECT
"""

import struct

PROTOCOL_VERSION = 2

# ---------------------------------------------------------------------------
#  Defaults (overridable from the game settings)
# ---------------------------------------------------------------------------
DEFAULT_TCP_PORT = 5555
DEFAULT_UDP_PORT = 5556
TICK_RATE = 60                      # simulation ticks per second (server AND client prediction)
TICK_MS = 16.667                    # simulation time advanced per tick (see core/clock notes)
SNAPSHOT_RATE = 60                  # snapshots per second
STATE_RATE = 20                     # max "latest state" sends per second per stream
STATE_REFRESH_MS = 500              # a stream is re-sent at least this often
HEARTBEAT_MS = 1000
UDP_TIMEOUT_MS = 4000
UDP_HANDSHAKE_TIMEOUT_MS = 3000
MAX_PLAYERS = 3

# ---------------------------------------------------------------------------
#  Message types
# ---------------------------------------------------------------------------
T_SNAPSHOT = 0x01
T_STATE = 0x02
T_EVENTS = 0x03
T_INPUT = 0x04
T_ACTION = 0x05
T_PING = 0x06
T_PONG = 0x07
T_HANDSHAKE = 0x20
T_HANDSHAKE_ACK = 0x21
T_HEARTBEAT = 0x22
T_DISCONNECT = 0x23

# Keys of the reliable "latest state" streams
KEY_PLAYERS = 1
KEY_ENEMIES = 2
KEY_WORLD = 3

# ---------------------------------------------------------------------------
#  Inputs
# ---------------------------------------------------------------------------
IN_LEFT = 1
IN_RIGHT = 2
IN_JUMP = 4
IN_ATTACK = 8
IN_DASH = 16

MAX_INPUTS_PER_PACKET = 8
_INPUT_HEAD = struct.Struct('!IB')


def pack_inputs(last_seq: int, bits: list) -> bytes:
    """``bits`` are the most recent inputs, oldest first; the last one has
    sequence number ``last_seq``."""
    bits = bits[-MAX_INPUTS_PER_PACKET:]
    return _INPUT_HEAD.pack(last_seq & 0xFFFFFFFF, len(bits)) + bytes(bits)


def unpack_inputs(data: bytes):
    """Returns ``[(seq, bits), ...]`` oldest first, or ``[]`` if malformed."""
    if len(data) < _INPUT_HEAD.size:
        return []
    last_seq, count = _INPUT_HEAD.unpack_from(data)
    if count == 0 or count > MAX_INPUTS_PER_PACKET or len(data) != _INPUT_HEAD.size + count:
        return []
    body = data[_INPUT_HEAD.size:]
    first = last_seq - count + 1
    return [((first + i) & 0xFFFFFFFF, body[i]) for i in range(count)]


# ---------------------------------------------------------------------------
#  Snapshot
# ---------------------------------------------------------------------------
# Player flags
PF_DASHING = 1
PF_ATTACKING = 2
PF_DEAD = 4
PF_FACING_RIGHT = 8
PF_ON_GROUND = 16
PF_MOVING = 32

# Enemy flags
EF_DEAD = 1
EF_BLINK = 2
EF_FACING_RIGHT = 4
EF_ATTACKING = 8
EF_MOVING = 16

_SNAP_HEAD = struct.Struct('!IB')            # t_ms, player count
_SNAP_PLAYER = struct.Struct('!BhhB')        # id, x, y, flags
_SNAP_ENEMY_COUNT = struct.Struct('!H')
_SNAP_ENEMY = struct.Struct('!HhhB')         # id, x, y, flags
_SNAP_BOSS = struct.Struct('!Bhh')           # present, x, y

# Owner block: physics state of the receiving player (client-side prediction)
# Timers are expressed in simulation ticks (see core.player export_physics).
OWNER = struct.Struct('!IiidBbBddBBBBBB')
OF_ON_GROUND = 1
OF_DOUBLE_JUMPED = 2
OF_DASHING = 4
OF_PREV_JUMP = 8
OF_JUMP_CUT = 16
OF_FACING_RIGHT = 32
OF_DEAD = 64
CAP_DOUBLE_JUMP = 1
CAP_DASH = 2


def _clamp16(v) -> int:
    return -32768 if v < -32768 else 32767 if v > 32767 else int(v)


def pack_snapshot_common(t_ms: int, players: list, enemies: list, boss) -> bytes:
    """``players``: ``[(id, x, y, flags)]``; ``enemies``: ``[(id, x, y, flags)]``;
    ``boss``: ``(x, y)`` or ``None``."""
    parts = [_SNAP_HEAD.pack(t_ms & 0xFFFFFFFF, len(players))]
    for pid, x, y, flags in players:
        parts.append(_SNAP_PLAYER.pack(pid, _clamp16(x), _clamp16(y), flags))
    parts.append(_SNAP_ENEMY_COUNT.pack(len(enemies)))
    for eid, x, y, flags in enemies:
        parts.append(_SNAP_ENEMY.pack(eid, _clamp16(x), _clamp16(y), flags))
    if boss is None:
        parts.append(_SNAP_BOSS.pack(0, 0, 0))
    else:
        parts.append(_SNAP_BOSS.pack(1, _clamp16(boss[0]), _clamp16(boss[1])))
    return b''.join(parts)


def pack_owner_block(ack_seq, x, y, vel_y, flags, dash_dir, air_dashes, dash_dist,
                     recoil_vx, caps, dash_left, dash_cd, coyote, jump_buf, recoil) -> bytes:
    return OWNER.pack(ack_seq & 0xFFFFFFFF, int(x), int(y), vel_y, flags, dash_dir,
                      air_dashes, dash_dist, recoil_vx, caps,
                      min(dash_left, 255), min(dash_cd, 255), min(coyote, 255),
                      min(jump_buf, 255), min(recoil, 255))


def unpack_snapshot(data: bytes):
    """Returns ``(t_ms, players, enemies, boss, owner)`` or raises ``ValueError``.

    ``players`` / ``enemies``: lists of tuples as given to ``pack_snapshot_common``;
    ``boss``: ``(x, y)`` or ``None``; ``owner``: dict or ``None``."""
    try:
        pos = 0
        t_ms, n_players = _SNAP_HEAD.unpack_from(data, pos)
        pos += _SNAP_HEAD.size
        players = []
        for _ in range(n_players):
            players.append(_SNAP_PLAYER.unpack_from(data, pos))
            pos += _SNAP_PLAYER.size
        (n_enemies,) = _SNAP_ENEMY_COUNT.unpack_from(data, pos)
        pos += _SNAP_ENEMY_COUNT.size
        enemies = []
        for _ in range(n_enemies):
            enemies.append(_SNAP_ENEMY.unpack_from(data, pos))
            pos += _SNAP_ENEMY.size
        present, bx, by = _SNAP_BOSS.unpack_from(data, pos)
        pos += _SNAP_BOSS.size
        boss = (bx, by) if present else None
        owner = None
        if len(data) - pos >= OWNER.size:
            (ack_seq, x, y, vel_y, flags, dash_dir, air_dashes, dash_dist, recoil_vx,
             caps, dash_left, dash_cd, coyote, jump_buf, recoil) = OWNER.unpack_from(data, pos)
            owner = {
                'ack_seq': ack_seq, 'x': x, 'y': y, 'vel_y': vel_y, 'flags': flags,
                'dash_dir': dash_dir, 'air_dashes': air_dashes, 'dash_dist': dash_dist,
                'recoil_vx': recoil_vx, 'caps': caps, 'dash_left': dash_left,
                'dash_cd': dash_cd, 'coyote': coyote, 'jump_buf': jump_buf,
                'recoil': recoil,
            }
        return t_ms, players, enemies, boss, owner
    except struct.error as exc:
        raise ValueError(f"malformed snapshot: {exc}") from exc
