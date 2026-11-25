"""Client-side prediction and server reconciliation for the local player.

The client runs the *same* physics as the server (``Player.apply_physics``) at
the same fixed tick, immediately applying the player's own inputs so movement
feels instant regardless of latency. Every input gets a sequence number. Each
snapshot carries the physics state of the player *after* the server applied
input ``ack_seq``; when it disagrees with what the client predicted for that
same input, the client rewinds to the server state and replays the inputs the
server has not processed yet.
"""

import collections

from core.collisions import collision_rects_for
from net import protocol as P

TICK_MS = P.TICK_MS
HISTORY_TICKS = 300            # 5 s of inputs; beyond that we just resynchronise


def owner_to_physics(owner: dict) -> dict:
    """Convert the snapshot owner block into ``Player.import_physics`` input."""
    f = owner['flags']
    return {
        'x': owner['x'], 'y': owner['y'], 'vel_y': owner['vel_y'],
        'on_ground': bool(f & P.OF_ON_GROUND),
        'has_double_jumped': bool(f & P.OF_DOUBLE_JUMPED),
        'is_dashing': bool(f & P.OF_DASHING),
        'jump_previous': bool(f & P.OF_PREV_JUMP),
        'jump_cut': bool(f & P.OF_JUMP_CUT),
        'direction': 1 if f & P.OF_FACING_RIGHT else -1,
        'dash_direction': owner['dash_dir'],
        'dash_available_in_air': owner['air_dashes'],
        'dash_distance_remaining': owner['dash_dist'],
        'recoil_vx': owner['recoil_vx'],
        'dash_left': owner['dash_left'], 'dash_cd': owner['dash_cd'],
        'coyote': owner['coyote'], 'jump_buf': owner['jump_buf'],
        'recoil': owner['recoil'],
    }


class _Entry:
    __slots__ = ('seq', 'bits', 't', 'x', 'y', 'vel_y', 'on_ground', 'dashing')

    def __init__(self, seq, bits, t):
        self.seq, self.bits, self.t = seq, bits, t
        self.x = self.y = 0
        self.vel_y = 0.0
        self.on_ground = self.dashing = False

    def record(self, player):
        self.x, self.y = player.rect.x, player.rect.y
        self.vel_y = player.vel_y
        self.on_ground = player.on_ground
        self.dashing = player.is_dashing

    def matches(self, phys):
        return (self.x == phys['x'] and self.y == phys['y']
                and abs(self.vel_y - phys['vel_y']) < 1e-6
                and self.on_ground == phys['on_ground']
                and self.dashing == phys['is_dashing'])


class Predictor:
    def __init__(self, player, game_map, doors):
        """``doors`` is a callable returning the current iterable of doors."""
        self.player = player
        self.game_map = game_map
        self._doors = doors
        self.seq = 0
        self.tick = 0
        self.history = collections.deque()
        self.recent_bits = collections.deque(maxlen=P.MAX_INPUTS_PER_PACKET)
        self.synced = False
        self.corrections = 0          # statistics: how often the server disagreed
        self._replaying = False

    @property
    def time_ms(self):
        return self.tick * TICK_MS

    # -- simulation --------------------------------------------------------

    def _simulate(self, bits, t):
        player = self.player
        player.commands = {
            'left': bool(bits & P.IN_LEFT), 'right': bool(bits & P.IN_RIGHT),
            'jump': bool(bits & P.IN_JUMP), 'dash': bool(bits & P.IN_DASH),
            'attack': False,
        }
        rects = collision_rects_for(self.game_map, self._doors(), player.rect)
        player.apply_physics(rects, t)
        if self._replaying:
            player.sounds_to_play.clear()      # a replay must not replay sounds

    def step(self, bits):
        """Advance one tick with the player's current inputs; returns its seq."""
        self.seq += 1
        self.tick += 1
        t = self.time_ms
        if self.synced and self.player.hp > 0:
            self._simulate(bits, t)
        entry = _Entry(self.seq, bits, t)
        entry.record(self.player)
        self.history.append(entry)
        while len(self.history) > HISTORY_TICKS:
            self.history.popleft()
        self.recent_bits.append(bits)
        return self.seq

    # -- reconciliation ----------------------------------------------------

    def _adopt(self, phys, t):
        self.player.import_physics(phys, t, TICK_MS)

    def reconcile(self, owner: dict):
        """Apply the owner block of a snapshot."""
        phys = owner_to_physics(owner)
        player = self.player
        player.can_double_jump = bool(owner['caps'] & P.CAP_DOUBLE_JUMP)
        player.can_dash = bool(owner['caps'] & P.CAP_DASH)

        if owner['flags'] & P.OF_DEAD or not self.synced:
            # Dead players are not simulated; the first snapshot gives the spawn.
            self._adopt(phys, self.time_ms)
            self.history.clear()
            self.synced = True
            return

        ack = owner['ack_seq']
        while self.history and self.history[0].seq < ack:
            self.history.popleft()
        if ack == 0:
            return                              # the server has not consumed any input yet
        if not self.history or self.history[0].seq != ack:
            # Our record of that input is gone (long stall): hard resync.
            self._adopt(phys, self.time_ms)
            self.history.clear()
            self.corrections += 1
            return

        acked = self.history[0]
        if acked.matches(phys):
            return                              # prediction was exact

        # Misprediction: rewind to the server's state and replay what it has not seen.
        self.corrections += 1
        self._adopt(phys, acked.t)
        acked.record(player)
        self._replaying = True
        try:
            for entry in list(self.history)[1:]:
                self._simulate(entry.bits, entry.t)
                entry.record(player)
        finally:
            self._replaying = False
