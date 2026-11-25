"""Authoritative game simulation.

``World`` owns every piece of game state (players, enemies, items, doors, boss,
...) and advances it one fixed tick at a time with :meth:`World.step`. It knows
nothing about sockets or threads: the network layer feeds it inputs/actions and
reads snapshots from it. That makes the whole game logic testable headless.

Threading: a ``World`` is meant to be used from ONE thread (the server loop).

Time: ``World.time_ms`` is the simulation clock, advanced by ``TICK_MS`` per
tick. Never use ``pygame.time.get_ticks()`` in simulation code.
"""

import collections
import json
import os
import random

import pygame

from core import level
from core.free_soul import FreeSoul
from core.loot_soul import LootSoul
from core.lost_soul import LostSoul
from core.boss_room import BossRoom
from core.collisions import collision_rects_for
from core.game_map import GameMap
from core.key_item import KeyItem
from core.enemy import Enemy, STATE_CHASE
from core.player import Player
from core.lever import Lever
from core.paid_wall import PaidWall
from core.ability_orb import AbilityOrb
from core.lore_sign import LoreSign
from core.pathfinding import PathfindingService
from core.door import Door
from core.potion import PotionManager
from core.save_writer import SaveWriter
from net import protocol as P
from settings import (
    COOLDOWN_ECHO, COOLDOWN_ECHO_DIR, ENEMY_ATTACK_DAMAGE,
    PLAYER_DAMAGE, LEVER_COOP_WINDOW, ECHO_REVEAL_DURATION, DEV_MODE, ECHO_RANGE,
    ECHO_DIR_RANGE, TORCH_ECHO_RANGE, TORCH_INTERACTION_RANGE, TILE_SIZE,
    ENEMY_RESPAWN_TIME_MS,
)
from storage import saves, checkpoints

TICK_MS = P.TICK_MS
RESPAWN_DELAY_MS = 3000
SOUL_ABSORB_INTERVAL_MS = 50
SOUL_ABSORB_RADIUS_SQ = 64 * 64
ATTACK_BUFFER_MS = 120          # an attack pressed slightly early is not lost
MAX_QUEUED_INPUTS = 3           # beyond this the oldest inputs are dropped (lag catch-up)
ALLOWED_ACTIONS = ('echo', 'echo_dir', 'torch', 'interact')
SHOP_ITEMS = ('damage', 'max_hp', 'echo_dir')
LOOT_POTION_CHANCE = 0.2
QUEST_REWARD_MONEY = 100
SNAPSHOT_ENEMY_RADIUS = 900     # px: enemies farther than this from a player are not sent to them


class _InputSlot:
    """Per-player buffer of received inputs."""
    __slots__ = ('queue', 'last_seq', 'ack_seq', 'last_bits', 'attack_until')

    def __init__(self):
        self.queue = collections.deque()
        self.last_seq = None        # highest sequence number accepted so far
        self.ack_seq = 0            # last sequence number actually simulated
        self.last_bits = 0
        self.attack_until = -1.0


def _seq_after(a, b):
    return 0 < ((a - b) & 0xFFFFFFFF) < 0x80000000


class World:
    def __init__(self, base_dir, slot_id, new_game, enable_pathfinding=True,
                 save_enabled=True):
        self.base_dir = base_dir
        self.slot_id = slot_id
        self.time_ms = 0.0
        self.tick = 0
        self.events = []                 # [(target_pid or None, event dict)]

        # --- map ---------------------------------------------------------
        self.game_map = GameMap(os.path.join(base_dir, "assets", "MapS2.tmx"), graphics=False)
        self.game_map.build_grid_collision()
        self.checkpoint_rects = self._scan_checkpoints()

        # --- save data ---------------------------------------------------
        self._saver = SaveWriter(saves.save_game) if save_enabled else None
        if new_game:
            self.save_data = saves.create_save_blank()
            self._write_save()
        else:
            self.save_data = saves.load_game(slot_id)
            if self.save_data is None:
                self.save_data = saves.create_save_blank()
                self._write_save()
        self.spawn_point = checkpoints.get_coords_per_id(
            self.save_data["id_last_checkpoint"])

        # --- players -----------------------------------------------------
        self.players = {}                # id -> Player
        self.slots = {}                  # id -> _InputSlot
        self.vis = {}                    # id -> list[list[bool]]
        self.vis_delta = {}              # id -> set[(x, y)] newly (re)revealed tiles
        self.vis_full_pending = set()    # ids that need the whole visibility map
        self.active_echoes = []

        # --- entities ----------------------------------------------------
        self.enemies = {}
        self.free_souls = {}
        self.loot_souls = {}
        self.lost_souls = {}
        self.orbs = {}
        self.signs = {}
        self.doors = {}
        self.levers = {}
        self.potions = PotionManager()
        self.key = None
        self.secret_passage_open = False
        self.paid_wall = PaidWall(*level.PAID_WALL_SIGN_TILE, level.PAID_WALL_COST,
                                   level.PAID_WALL_MESSAGE)
        self.paid_wall_open = False
        self.key_wall_destroyed = False
        self.torch_on = False
        self._lever_hits = {}
        self._torch_just_lit_by = None
        self._quest_reward_given = False

        self._load_entities()
        self.rects_collision = self.game_map.get_rects_collisions()
        self.pathfinding = PathfindingService(self.game_map) if enable_pathfinding else None
        self.boss_room = BossRoom(
            room_rect=pygame.Rect(*level.BOSS_ROOM_RECT),
            boss_x=level.BOSS_SPAWN[0], boss_y=level.BOSS_SPAWN[1],
            json_path=os.path.join(base_dir, "assets", "demon_slime.json"),
            png_path=os.path.join(base_dir, "assets", "demon_slime.png"),
            rects_collision=self.rects_collision,
        )

        self._players_cache = []
        self._players_cache_tick = -1

    # ------------------------------------------------------------------
    #  Setup
    # ------------------------------------------------------------------

    def _scan_checkpoints(self):
        points = {}
        for y, row in enumerate(self.game_map.map_data):
            for x, tile in enumerate(row):
                if tile == 3:
                    points[f"{x}_{y}"] = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE,
                                                    TILE_SIZE, TILE_SIZE)
        return points

    def _read_json(self, name):
        try:
            with open(os.path.join(self.base_dir, "assets", name), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _load_entities(self):
        for eid, cfg in enumerate(self._read_json('enemies.json')):
            self.enemies[eid] = Enemy(x=cfg['x'], y=cfg['y'], id=eid, max_hp=cfg['max_hp'])
        for cfg in self._read_json('souls.json'):
            soul = FreeSoul(cfg['x'], cfg['y'])
            self.free_souls[soul.id] = soul
        for x, y, capability in level.ORBS:
            orb = AbilityOrb(x, y, capability)
            self.orbs[orb.id] = orb
        for i, (x, y) in enumerate(level.DOORS):
            self.doors[i] = Door(x=x, y=y)
        for i, (tx, ty) in enumerate(level.LEVERS_TILES):
            self.levers[i] = Lever(tx, ty)
        for i, (x, y, kind) in enumerate(level.SIGNS):
            sign = LoreSign(x, y)
            sign.type_sign = kind
            sign.is_unlocked = kind in level.SIGNS_ALWAYS_UNLOCKED
            self.signs[i] = sign

    def close(self):
        if self.pathfinding is not None:
            self.pathfinding.stop()
        if self._saver is not None:
            self._saver.flush_and_stop()

    # ------------------------------------------------------------------
    #  Players
    # ------------------------------------------------------------------

    def add_player(self, pid):
        spawn = self.spawn_point if pid == 0 else checkpoints.get_start_point()[1]
        player = Player(spawn[0], spawn[1], pid)
        if pid == 0:
            player.money = self.save_data.get("money", 0)
        upgrades = self.save_data.get("upgrades", {})
        player.can_double_jump = upgrades.get("double_jump", False)
        player.can_dash = upgrades.get("dash", False)
        player.can_echo_dir = upgrades.get("echo_dir", False)
        if DEV_MODE:
            player.can_double_jump = player.can_dash = player.can_echo_dir = True
        self.players[pid] = player
        self.slots[pid] = _InputSlot()

        saved = None
        if pid == 0:
            saved = saves.decode_vis_map(self.save_data.get("vis_map"),
                                         self.game_map.width_map, self.game_map.height_map)
        self.vis[pid] = saved or self.game_map.create_blank_visibility_map()
        self.vis_delta[pid] = set()
        self.vis_full_pending.add(pid)
        return player

    def remove_player(self, pid):
        self.players.pop(pid, None)
        self.slots.pop(pid, None)
        self.vis.pop(pid, None)
        self.vis_delta.pop(pid, None)
        self.vis_full_pending.discard(pid)
        self._lever_hits.pop(pid, None)
        self.active_echoes = [e for e in self.active_echoes if e['pid'] != pid]

    # ------------------------------------------------------------------
    #  Inbound data (already decoded and bounded by the network layer)
    # ------------------------------------------------------------------

    def push_inputs(self, pid, inputs):
        """``inputs``: ``[(seq, bits), ...]`` oldest first (redundant resends allowed)."""
        slot = self.slots.get(pid)
        if slot is None:
            return
        for seq, bits in inputs:
            if slot.last_seq is not None and not _seq_after(seq, slot.last_seq):
                continue                      # already received (redundancy / reorder)
            slot.last_seq = seq
            slot.queue.append((seq, bits & 0x1F))

    def set_profile(self, pid, nickname, skin):
        player = self.players.get(pid)
        if player is None:
            return
        if isinstance(nickname, str):
            player.nickname = nickname[:20]
        if isinstance(skin, int) and not isinstance(skin, bool):
            skin = max(0, min(skin, 2))
            if skin != player.skin:
                player.skin = skin
                player._apply_skin(skin)

    def handle_action(self, pid, action):
        """One-shot action from a client: ``{"a": name, ...}``."""
        player = self.players.get(pid)
        if player is None or not isinstance(action, dict) or player.hp <= 0:
            return
        name = action.get('a')
        if name not in ALLOWED_ACTIONS:
            return
        if name == 'echo':
            self._start_echo(player, directional=False)
        elif name == 'echo_dir':
            self._start_echo(player, directional=True)
        elif name == 'torch':
            self._toggle_torch(player)
        elif name == 'interact':
            item = action.get('item')
            self._interact(player, item if item in SHOP_ITEMS else None)

    # ------------------------------------------------------------------
    #  Actions
    # ------------------------------------------------------------------

    def _start_echo(self, player, directional):
        now = self.time_ms
        if directional:
            if not player.can_echo_dir or now - player.last_echo_dir_time <= COOLDOWN_ECHO_DIR:
                return
            player.last_echo_dir_time = now
            echo = {'pid': player.id, 'cx': player.rect.centerx, 'cy': player.rect.centery,
                    'start': now, 'prev_radius': 0, 'kind': 'dir',
                    'range': ECHO_DIR_RANGE, 'direction': player.direction}
        else:
            if now - player.last_echo_time <= COOLDOWN_ECHO:
                return
            player.last_echo_time = now
            echo = {'pid': player.id, 'cx': player.rect.centerx, 'cy': player.rect.centery,
                    'start': now, 'prev_radius': 0, 'kind': 'normal', 'range': ECHO_RANGE}
        self.active_echoes.append(echo)
        position = (player.rect.centerx, player.rect.centery)
        for enemy in self.enemies.values():
            if not enemy.is_dead:
                enemy.alert(position, now)

    def _toggle_torch(self, player):
        tx, ty = level.TORCH_POS
        dx = player.rect.centerx - (tx + TILE_SIZE // 2)
        dy = player.rect.centery - (ty + TILE_SIZE)
        if (dx * dx + dy * dy) ** 0.5 > TORCH_INTERACTION_RANGE:
            return
        self.torch_on = not self.torch_on
        if self.torch_on:
            self._torch_just_lit_by = player.id
            if player.id == 0:
                self._save_checkpoint(player, f"{player.rect.x // TILE_SIZE}_{player.rect.y // TILE_SIZE}")

    def _interact(self, player, shop_item):
        for sign in self.signs.values():
            dx = player.rect.centerx - sign.rect.centerx
            dy = player.rect.centery - sign.rect.centery
            if (dx * dx + dy * dy) ** 0.5 <= LoreSign.RANGE_INTERACTION:
                kind = getattr(sign, 'type_sign', 'lore')
                if not sign.is_unlocked or kind == 'shop_upgrades':
                    sign.try_pay(player, shop_item=shop_item)
                break
        if not self.paid_wall_open:
            wall = self.paid_wall
            dx = player.rect.centerx - (wall.x + TILE_SIZE // 2)
            dy = player.rect.centery - (wall.y + TILE_SIZE // 2)
            if dx * dx + dy * dy <= PaidWall.RANGE_INTERACTION ** 2:
                if wall.try_pay(player) == 'unlocked':
                    self._destroy_tiles(level.PAID_WALL_TILES)
                    self.paid_wall_open = True

    def _destroy_tiles(self, tiles):
        for tx, ty in tiles:
            if (0 <= tx < self.game_map.width_map and 0 <= ty < self.game_map.height_map
                    and self.game_map.map_data[ty][tx] == 1):
                self.game_map.map_data[ty][tx] = 0
        self.game_map.build_grid_collision()
        self.rects_collision = self.game_map.get_rects_collisions()
        self.boss_room.rects_collision = self.rects_collision

    # ------------------------------------------------------------------
    #  Collision helper shared with client-side prediction
    # ------------------------------------------------------------------

    def collision_rects_for(self, rect):
        return collision_rects_for(self.game_map, self.doors.values(), rect)

    # ------------------------------------------------------------------
    #  Saving
    # ------------------------------------------------------------------

    def _write_save(self):
        if self._saver is not None:
            self._saver.save(self.slot_id, self.save_data)

    def _save_checkpoint(self, player, checkpoint_id):
        data = self.save_data
        data["id_last_checkpoint"] = checkpoint_id
        data["vis_map"] = saves.encode_vis_map(self.vis[player.id])
        data["money"] = player.money
        data["upgrades"]["double_jump"] = player.can_double_jump
        data["upgrades"]["dash"] = player.can_dash
        data["upgrades"]["echo_dir"] = player.can_echo_dir
        self._write_save()

    # ------------------------------------------------------------------
    #  Events
    # ------------------------------------------------------------------

    def _emit(self, event, target=None):
        self.events.append((target, event))

    def _emit_sound(self, name, source_pid=None, pos=None):
        self._emit({'e': 'sound', 'n': name, 'p': source_pid,
                    'x': None if pos is None else int(pos[0]),
                    'y': None if pos is None else int(pos[1])})

    def pop_events(self):
        events, self.events = self.events, []
        return events

    # ------------------------------------------------------------------
    #  Simulation tick
    # ------------------------------------------------------------------

    def step(self):
        self.tick += 1
        self.time_ms += TICK_MS
        now = self.time_ms

        self._consume_inputs(now)
        self._update_echoes(now)
        self._update_pickups(now)
        self._update_doors(now)
        self._update_enemies(now)
        self._update_boss(now)
        self._update_players(now)
        self.potions.update(TICK_MS, list(self.players.values()))
        self._collect_sounds()

    # -- inputs ----------------------------------------------------------

    def _consume_inputs(self, now):
        for pid, player in self.players.items():
            slot = self.slots[pid]
            while len(slot.queue) > MAX_QUEUED_INPUTS:
                slot.queue.popleft()          # too much backlog: skip ahead
            if slot.queue:
                seq, bits = slot.queue.popleft()
                slot.ack_seq = seq
                slot.last_bits = bits & ~(P.IN_ATTACK | P.IN_DASH)
            else:
                bits = slot.last_bits         # starved: repeat held keys only
            if player.hp <= 0:
                bits = 0
            if bits & P.IN_ATTACK:
                slot.attack_until = now + ATTACK_BUFFER_MS
            player.commands = {
                'left': bool(bits & P.IN_LEFT),
                'right': bool(bits & P.IN_RIGHT),
                'jump': bool(bits & P.IN_JUMP),
                'dash': bool(bits & P.IN_DASH),
                'attack': now < slot.attack_until and player.hp > 0,
            }

    # -- echoes ----------------------------------------------------------

    def _update_echoes(self, now):
        remaining = []
        for echo in self.active_echoes:
            pid = echo['pid']
            elapsed = now - echo['start']
            if elapsed > ECHO_REVEAL_DURATION or pid not in self.vis:
                continue
            radius = int(elapsed / ECHO_REVEAL_DURATION * echo['range'])
            if radius > echo['prev_radius']:
                delta = self.vis_delta[pid]
                if echo['kind'] == 'dir':
                    self.game_map.reveal_per_echo_dir_partial(
                        echo['cx'], echo['cy'], radius, self.vis[pid],
                        echo['direction'], delta_set=delta)
                else:
                    self.game_map.reveal_per_echo_partial(
                        echo['cx'], echo['cy'], radius, self.vis[pid], delta_set=delta)
                echo['prev_radius'] = radius
            remaining.append(echo)
        self.active_echoes = remaining

        if self._torch_just_lit_by is not None:
            pid, self._torch_just_lit_by = self._torch_just_lit_by, None
            if pid in self.vis:
                tx, ty = level.TORCH_POS
                self.active_echoes.append({
                    'pid': pid, 'cx': tx + TILE_SIZE // 2, 'cy': ty + TILE_SIZE,
                    'start': now, 'prev_radius': 0, 'kind': 'torch',
                    'range': TORCH_ECHO_RANGE})

    # -- pickups -----------------------------------------------------------

    def _update_pickups(self, now):
        players = self.players
        for sid, soul in list(self.free_souls.items()):
            for player in players.values():
                if player.rect.colliderect(soul.rect):
                    player.money += soul.value
                    del self.free_souls[sid]
                    break

        for sid, soul in list(self.loot_souls.items()):
            soul.update(now, self.game_map.get_nearby_rects(soul.rect))
            if soul.is_expired(now):
                del self.loot_souls[sid]
                continue
            for player in players.values():
                if player.rect.colliderect(soul.rect):
                    player.money += soul.value
                    del self.loot_souls[sid]
                    break

        # Lost souls are absorbed progressively by their owner (1 soul / 50 ms)
        for pid, player in players.items():
            if player.death_time is not None:
                continue
            for sid, soul in list(self.lost_souls.items()):
                if soul.player_id != pid:
                    continue
                dx = player.rect.centerx - soul.rect.centerx
                dy = player.rect.centery - soul.rect.centery
                if dx * dx + dy * dy <= SOUL_ABSORB_RADIUS_SQ:
                    last = getattr(soul, '_t_last_absorption', -1e9)
                    if now - last >= SOUL_ABSORB_INTERVAL_MS:
                        player.money += 1
                        soul.money -= 1
                        soul._t_last_absorption = now
                        if soul.money <= 0:
                            player.lost_soul = None
                            del self.lost_souls[sid]

        for player in players.values():
            for orb in self.orbs.values():
                if not orb.is_picked_up and player.rect.colliderect(orb.rect):
                    if orb.try_collect(player) and player.id == 0:
                        self.save_data['upgrades'][orb.ability] = True
                        self._write_save()

        if self.key and not self.key.is_picked_up:
            for player in players.values():
                if player.rect.colliderect(self.key.rect):
                    self.key.is_picked_up = True
                    player.have_key = True

    # -- doors -------------------------------------------------------------

    def _update_doors(self, now):
        for door_id, door in self.doors.items():
            if not door.is_open:
                door.update(now)
                if not door.is_opening:
                    zone = pygame.Rect(door.x - 8, door.y, door.WIDTH + 16, door.HEIGHT)
                    for player in self.players.values():
                        if player.rect.colliderect(zone):
                            door.try_opening(player, now)
            # Opening the main exit door completes the quests: one-time reward for everyone.
            if (door_id == 0 and (door.is_opening or door.is_open)
                    and not self._quest_reward_given):
                self._quest_reward_given = True
                for player in self.players.values():
                    player.money += QUEST_REWARD_MONEY
                self._emit({'e': 'quest_reward', 'money': QUEST_REWARD_MONEY})

    # -- enemies -----------------------------------------------------------

    def _update_enemies(self, now):
        for enemy_id, enemy in self.enemies.items():
            if enemy.is_dead:
                if now - enemy.death_time >= ENEMY_RESPAWN_TIME_MS:
                    enemy.respawn()
                continue
            if enemy.state == STATE_CHASE and self.players:
                target = min(self.players.values(), key=lambda p: (
                    (enemy.rect.centerx - p.rect.centerx) ** 2
                    + (enemy.rect.centery - p.rect.centery) ** 2))
                enemy.target_x = target.rect.centerx
                enemy.target_y = target.rect.centery
            enemy.apply_logic(self.game_map.get_nearby_rects(enemy.rect), self.game_map,
                                    self.players, now, pathfinding=self.pathfinding)

    # -- boss --------------------------------------------------------------

    def _update_boss(self, now):
        room = self.boss_room
        if room.boss_defeated:
            return
        room.update(TICK_MS, self.players, now)
        if room.boss_defeated:
            boss = room.boss
            self.key = KeyItem(boss.pos.x + boss.sprite_w // 2, boss.pos.y + boss.sprite_h // 2)

    # -- players -----------------------------------------------------------

    def _update_players(self, now):
        doors_closed = [d.rect_collision for d in self.doors.values() if not d.is_open]
        for pid, player in list(self.players.items()):
            rects = self.collision_rects_for(player.rect)
            player.apply_physics(rects, now)

            if player.handle_attack(now):
                self.slots[pid].attack_until = -1.0
            if player.is_attacking and player.attack_rect:
                self._resolve_player_attack(player, now)
            else:
                self._lever_hits.pop(pid, None)

            if not self.secret_passage_open:
                for lever in self.levers.values():
                    if lever.active and now - lever.time_activation > LEVER_COOP_WINDOW:
                        lever.reset()

            self._enemy_hits_on(player, now)
            self._handle_death(player, now)
            if pid == 0:
                for cp_id, rect in self.checkpoint_rects.items():
                    if (player.rect.colliderect(rect)
                            and self.save_data["id_last_checkpoint"] != cp_id):
                        self._save_checkpoint(player, cp_id)
        del doors_closed

    def _resolve_player_attack(self, player, now):
        damage = PLAYER_DAMAGE * (2 if player.damage_bonus >= 1 else 1)
        for eid, enemy in self.enemies.items():
            if (enemy.is_dead or eid in player.hit_enemies
                    or not player.attack_rect.colliderect(enemy.rect)):
                continue
            player.hit_enemies.add(eid)
            if enemy.take_damage(damage, now):
                cx, cy = enemy.rect.centerx, enemy.rect.centery
                soul = LootSoul(cx, cy, value=enemy.money_drop)
                soul.creation_time = now
                soul.num_visuals = enemy.money_drop
                self.loot_souls[soul.id] = soul
                if random.random() < LOOT_POTION_CHANCE:
                    self.potions.drop(cx, cy, 'large' if enemy.max_hp >= 3 else 'small')
        self.boss_room.receive_attack_player(player.attack_rect, damage)

        if not self.secret_passage_open:
            hit = self._lever_hits.setdefault(player.id, set())
            for lever_id, lever in self.levers.items():
                if lever_id not in hit and player.attack_rect.colliderect(lever.rect):
                    hit.add(lever_id)
                    lever.activate(now)
                    if all(l.active and now - l.time_activation <= LEVER_COOP_WINDOW
                           for l in self.levers.values()):
                        self.secret_passage_open = True
                        self._destroy_tiles(level.SECRET_PASSAGE_TILES)

        if player.have_key and not self.key_wall_destroyed:
            for tx, ty in level.KEY_WALL_TILES:
                rect = pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if player.attack_rect.colliderect(rect):
                    self._destroy_tiles(level.KEY_WALL_TILES)
                    self.key_wall_destroyed = True
                    break

    def _enemy_hits_on(self, player, now):
        for enemy in self.enemies.values():
            if (enemy.is_dead or not enemy.is_attacking or not enemy.hitbox_active(now)
                    or player.id in enemy.attack_already_hit):
                continue
            if enemy.get_rect_hitbox_attack().colliderect(player.rect):
                if player.take_damage(ENEMY_ATTACK_DAMAGE, now, source_x=enemy.rect.centerx):
                    enemy.attack_already_hit.add(player.id)

    def _handle_death(self, player, now):
        if player.hp > 0:
            return
        if player.death_time is None:
            player.death_time = now
            if player.lost_soul and player.lost_soul.id in self.lost_souls:
                del self.lost_souls[player.lost_soul.id]
            room = self.boss_room
            if room.fight_started and not room.boss_defeated:
                pos = level.BOSS_FIGHT_SOUL_POS
                room.reset_boss()
            else:
                pos = (player.rect.centerx, player.rect.centery)
            soul = LostSoul(pos[0], pos[1], player.id, player.money)
            self.lost_souls[soul.id] = soul
            player.lost_soul = soul
            player.money = 0
        elif now - player.death_time >= RESPAWN_DELAY_MS:
            checkpoint = (self.save_data["id_last_checkpoint"] if player.id == 0
                          else checkpoints.get_start_point()[0])
            player.respawn(checkpoints.get_coords_per_id(checkpoint))
            player.death_time = None

    # -- sounds ------------------------------------------------------------

    def _collect_sounds(self):
        for pid, player in self.players.items():
            for name in player.sounds_to_play:
                self._emit_sound(name, source_pid=pid,
                                 pos=(player.rect.centerx, player.rect.centery))
            player.sounds_to_play.clear()
        for enemy in self.enemies.values():
            for name in enemy.sounds_to_play:
                self._emit_sound(name, pos=(enemy.rect.centerx, enemy.rect.centery))
            enemy.sounds_to_play.clear()

    # ------------------------------------------------------------------
    #  Outbound views
    # ------------------------------------------------------------------

    def _player_flags(self, p):
        flags = 0
        if p.is_dashing:
            flags |= P.PF_DASHING
        if p.is_attacking:
            flags |= P.PF_ATTACKING
        if p.hp <= 0:
            flags |= P.PF_DEAD
        if p.direction > 0:
            flags |= P.PF_FACING_RIGHT
        if p.on_ground:
            flags |= P.PF_ON_GROUND
        if p.is_moving:
            flags |= P.PF_MOVING
        return flags

    def _enemy_flags(self, e):
        flags = 0
        if e.is_dead:
            flags |= P.EF_DEAD
        if e.blinking:
            flags |= P.EF_BLINK
        if e.direction > 0:
            flags |= P.EF_FACING_RIGHT
        if e.is_attacking:
            flags |= P.EF_ATTACKING
        if e.is_moving:
            flags |= P.EF_MOVING
        return flags

    def _boss_position(self):
        room = self.boss_room
        if not room.boss_defeated and room.boss is not None:
            return room.boss.pos.x, room.boss.pos.y
        return None

    def snapshot_common(self):
        """Snapshot containing EVERY enemy (bytes). See ``snapshot_for`` for the real thing."""
        players = [(p.id, p.rect.x, p.rect.y, self._player_flags(p))
                   for p in self.players.values()]
        enemies = [(e.id, e.rect.x, e.rect.y, self._enemy_flags(e))
                   for e in self.enemies.values()]
        return P.pack_snapshot_common(int(self.time_ms), players, enemies, self._boss_position())

    def snapshot_for(self, pid):
        """Complete snapshot for one client: every player, only the enemies close to this
        client's player (interest management: enemies are only visible near the player), plus
        the owner block used for client-side prediction."""
        if self._players_cache_tick != self.tick:
            self._players_cache = [(p.id, p.rect.x, p.rect.y, self._player_flags(p))
                                   for p in self.players.values()]
            self._players_cache_tick = self.tick
        me = self.players.get(pid)
        enemies = []
        if me is not None:
            cx, cy = me.rect.centerx, me.rect.centery
            limit = SNAPSHOT_ENEMY_RADIUS ** 2
            for e in self.enemies.values():
                dx, dy = e.rect.centerx - cx, e.rect.centery - cy
                if dx * dx + dy * dy <= limit:
                    enemies.append((e.id, e.rect.x, e.rect.y, self._enemy_flags(e)))
        common = P.pack_snapshot_common(int(self.time_ms), self._players_cache, enemies,
                                        self._boss_position())
        return common + self.owner_block(pid)

    def owner_block(self, pid):
        """Physics state of one player, for client-side prediction (bytes)."""
        player = self.players.get(pid)
        if player is None:
            return b''
        d = player.export_physics(self.time_ms, TICK_MS)
        flags = 0
        if d['on_ground']:
            flags |= P.OF_ON_GROUND
        if d['has_double_jumped']:
            flags |= P.OF_DOUBLE_JUMPED
        if d['is_dashing']:
            flags |= P.OF_DASHING
        if d['jump_previous']:
            flags |= P.OF_PREV_JUMP
        if d['jump_cut']:
            flags |= P.OF_JUMP_CUT
        if d['direction'] > 0:
            flags |= P.OF_FACING_RIGHT
        if player.hp <= 0:
            flags |= P.OF_DEAD
        caps = (P.CAP_DOUBLE_JUMP if player.can_double_jump else 0) | \
               (P.CAP_DASH if player.can_dash else 0)
        return P.pack_owner_block(
            self.slots[pid].ack_seq, d['x'], d['y'], d['vel_y'], flags,
            d['dash_direction'], d['dash_available_in_air'], d['dash_distance_remaining'],
            d['recoil_vx'], caps, d['dash_left'], d['dash_cd'], d['coyote'],
            d['jump_buf'], d['recoil'])

    def state_players(self):
        return {'t': int(self.time_ms // 50 * 50),
                'p': [p.get_detail(self.time_ms) for p in self.players.values()]}

    def state_enemies(self):
        return {'e': [e.get_state() for e in self.enemies.values()]}

    def state_world(self):
        return {
            'lost_souls': [a.get_state() for a in self.lost_souls.values()],
            'free_souls': [a.get_state() for a in self.free_souls.values()],
            'loot_souls': [a.get_state() for a in self.loot_souls.values()],
            'orbs': [o.get_state() for o in self.orbs.values()],
            'signs': [s.get_state(id_sign=i) for i, s in self.signs.items()],
            'key_item': self.key.get_state() if self.key else None,
            'doors': [d.get_state() for d in self.doors.values()],
            'levers': [l.get_state() for l in self.levers.values()],
            'passage_open': self.secret_passage_open,
            'paid_wall': self.paid_wall.get_state(),
            'key_wall_destroyed': self.key_wall_destroyed,
            'torch_lit': self.torch_on,
            'boss_room': self.boss_room.get_state(),
            'potions': self.potions.get_state(),
        }

    # -- visibility --------------------------------------------------------

    def vis_full_bits(self, pid):
        """Whole visibility map as a bit-packed ``bytes`` (row-major)."""
        grid = self.vis[pid]
        width = self.game_map.width_map
        bits = bytearray((width * self.game_map.height_map + 7) // 8)
        i = 0
        for row in grid:
            for value in row:
                if value:
                    bits[i >> 3] |= 1 << (i & 7)
                i += 1
        return bytes(bits)

    def pop_vis_delta(self, pid):
        """Flat tile indices (``y * width + x``) revealed since the last call."""
        delta = self.vis_delta.get(pid)
        if not delta:
            return []
        width = self.game_map.width_map
        out = [y * width + x for x, y in delta]
        delta.clear()
        return out
