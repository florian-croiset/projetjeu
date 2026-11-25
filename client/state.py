"""Applying what the server sends to the client-side entities.

``ClientStateMixin`` is mixed into ``Client``. It turns the three kinds of
network messages (snapshots, state streams, events) into updates of the local
entity dictionaries that the renderer and the HUD read.
"""

import time

import pygame
from utils.paths import asset_path

from core.ability_orb import AbilityOrb
from core.demon_slime_boss import DemonSlimeBoss
from core.door import Door
from core.enemy import Enemy
from core.free_soul import FreeSoul
from core.key_item import KeyItem
from core.lever import Lever
from core.lore_sign import LoreSign
from utils.i18n import get_text
from core.loot_soul import LootSoul
from core.lost_soul import LostSoul
from core.paid_wall import PaidWall
from core.player import Player
from core.prediction import Predictor
from net import protocol as P
from net.sync import PositionBuffer, ServerClock
from settings import INTERP_DELAY_MS, TILE_SIZE
from utils import music
from core import level

SOUND_HEARING_RANGE = 700          # px: farther sound events are not played
PREDICTED_SOUNDS = ('jump', 'dash')   # played locally by the prediction already


class ClientStateMixin:
    # ------------------------------------------------------------------
    #  Per-connection client state
    # ------------------------------------------------------------------

    def _reset_net_state(self):
        self.server_clock = ServerClock()
        self.predictor = None
        self._pos_buffers = {}            # ('p'|'e'|'b', id) -> PositionBuffer
        self._last_positions = {}         # ('p'|'e', id) -> (x, y) from the newest snapshot
        self._latched_bits = 0
        self._tick_accumulator = 0.0
        self._last_frame_time = None

    # ------------------------------------------------------------------
    #  Dispatch
    # ------------------------------------------------------------------

    def _apply_net_messages(self, messages):
        now_ms = time.monotonic() * 1000.0
        for kind, data in messages:
            if kind == 'snapshot':
                self._on_snapshot(data, now_ms)
            elif kind == 'state':
                self._on_state(data)
            elif kind == 'events':
                self._on_events(data)

    # ------------------------------------------------------------------
    #  Snapshots (60 Hz): positions + flags + own physics state
    # ------------------------------------------------------------------

    def _on_snapshot(self, snap, now_ms):
        t_ms, players, enemies, boss, owner = snap
        self.server_clock.add_sample(t_ms, now_ms)

        seen = set()
        for pid, x, y, flags in players:
            seen.add(pid)
            player = self.local_players.get(pid)
            if player is None:
                player = Player(x, y, pid)
                self.local_players[pid] = player
            if pid == self.my_id:
                self._on_own_snapshot(player, flags, owner)
            else:
                self._buffer('p', pid).push(t_ms, x, y)
                self._last_positions[('p', pid)] = (x, y)
                player.apply_snapshot_flags(flags)
        for pid in [p for p in self.local_players if p not in seen]:
            del self.local_players[pid]
            self._pos_buffers.pop(('p', pid), None)

        for eid, x, y, flags in enemies:
            self._buffer('e', eid).push(t_ms, x, y)
            self._last_positions[('e', eid)] = (x, y)
            enemy = self.local_enemies.get(eid)
            if enemy is not None:
                enemy.apply_snapshot_flags(flags)

        if boss is not None:
            self._buffer('b', 0).push(t_ms, boss[0], boss[1])

    def _buffer(self, kind, ident):
        key = (kind, ident)
        buf = self._pos_buffers.get(key)
        if buf is None:
            buf = self._pos_buffers[key] = PositionBuffer()
        return buf

    def _on_own_snapshot(self, player, flags, owner):
        player.is_attacking = bool(flags & P.PF_ATTACKING)
        if owner is None:
            return
        if self.predictor is None:
            self.predictor = Predictor(player, self.game_map,
                                       lambda: self.local_doors.values())
        self.predictor.reconcile(owner)

    # ------------------------------------------------------------------
    #  Interpolation of everything that is not the local player
    # ------------------------------------------------------------------

    def _update_interpolation(self):
        server_now = self.server_clock.server_time_at(time.monotonic() * 1000.0)
        if server_now is None:
            return
        # Render a little further in the past when packets arrive with a lot of jitter.
        delay = max(INTERP_DELAY_MS, min(200.0, 2.0 * self.server_clock.jitter_ms() + 20.0))
        t_render = server_now - delay
        for (kind, ident), buf in self._pos_buffers.items():
            pos = buf.sample(t_render)
            if pos is None:
                continue
            x, y = int(pos[0]), int(pos[1])
            if kind == 'p':
                target = self.local_players.get(ident)
            elif kind == 'e':
                target = self.local_enemies.get(ident)
            else:
                target = self.boss_local
                if target is not None:
                    target.pos.x, target.pos.y = x, y
                continue
            if target is not None:
                target.rect.x, target.rect.y = x, y

    # ------------------------------------------------------------------
    #  State streams
    # ------------------------------------------------------------------

    def _on_state(self, state):
        key = state.get('k')
        if key == P.KEY_PLAYERS:
            self._apply_players_state(state.get('p', []))
        elif key == P.KEY_ENEMIES:
            self._apply_enemies_state(state.get('e', []))
        elif key == P.KEY_WORLD:
            self._apply_world_state(state)

    def _apply_players_state(self, details):
        for detail in details:
            player = self.local_players.get(detail['id'])
            if player is None:
                continue                 # created by the next snapshot
            was_echo_dir = player.can_echo_dir
            player.apply_detail(detail)
            if detail['id'] != self.my_id:
                continue
            if not was_echo_dir and player.can_echo_dir and self.notif_ability:
                key_name = self.settings.get('controls', {}).get('echo_dir', 'E')
                self.notif_ability.notify('echo_dir', key_name)
            previous = self._money_player_previous
            if previous is not None and player.money > previous:
                self._souls_harvested_total += player.money - previous
            self._money_player_previous = player.money

    def _apply_enemies_state(self, details):
        ids = {d['id'] for d in details}
        for eid in [e for e in self.local_enemies if e not in ids]:
            del self.local_enemies[eid]
            self._pos_buffers.pop(('e', eid), None)
        for detail in details:
            eid = detail['id']
            enemy = self.local_enemies.get(eid)
            if enemy is None:
                x, y = self._last_positions.get(('e', eid), (0, 0))
                enemy = self.local_enemies[eid] = Enemy(x, y, eid, max_hp=detail.get('max_hp', 2))
            enemy.set_state(detail)
            if detail.get('is_dead') and eid not in self._enemies_dead_counted:
                self._enemies_dead_counted.add(eid)
                self._enemies_killed_total += 1

    def _sync_dict(self, local, remote_list, create, key='id'):
        """Keep ``local`` (id -> entity) equal to ``remote_list`` (dicts with an id)."""
        ids = {d[key] for d in remote_list}
        for ident in [i for i in local if i not in ids]:
            del local[ident]
        for data in remote_list:
            entity = local.get(data[key])
            if entity is None:
                entity = local[data[key]] = create(data)
            yield entity, data

    def _apply_world_state(self, w):
        for soul, data in self._sync_dict(
                self.local_lost_souls, w.get('lost_souls', []),
                lambda d: LostSoul(d['x'], d['y'], d['id_player'], d.get('money', 0))):
            if not hasattr(soul, '_money_max'):
                soul._money_max = data.get('money', 0)
            soul.set_state(data)
        for soul, data in self._sync_dict(
                self.local_free_souls, w.get('free_souls', []),
                lambda d: FreeSoul(d['x'], d['y'], d.get('value'))):
            soul.set_state(data)
        for soul, data in self._sync_dict(
                self.local_loot_souls, w.get('loot_souls', []),
                lambda d: LootSoul(d['x'], d['y'], d.get('value', 1))):
            soul.set_state(data)

        for orb, data in self._sync_dict(
                self.local_ability_orbs, w.get('orbs', []),
                lambda d: AbilityOrb(d['x'], d['y'], d['ability'])):
            was = getattr(orb, '_was_picked_up', False)
            orb.set_state(data)
            if not was and orb.is_picked_up and data.get('ability') == 'double_jump' \
                    and self.notif_ability:
                key_name = self.settings.get('controls', {}).get('jump', 'SPACE')
                self.notif_ability.notify('double_jump', key_name)
            orb._was_picked_up = orb.is_picked_up

        for sign_data in w.get('signs', []):
            idx = sign_data.get('id', 0)
            sign = self.local_lore_signs.get(idx)
            if sign is None:
                sign = self.local_lore_signs[idx] = LoreSign(sign_data['x'], sign_data['y'])
            was_unlocked = sign.is_unlocked
            sign.set_state(sign_data)
            if (not was_unlocked and sign.is_unlocked
                    and self._sign_active_id == idx):
                self._on_sign_unlocked(sign_data)
                self._sign_active_id = None

        self._apply_doors(w.get('doors', []))
        self._apply_boss(w.get('boss_room'))

        key_data = w.get('key_item')
        if key_data:
            if self.local_key_item is None:
                self.local_key_item = KeyItem(key_data['x'], key_data['y'])
            was_picked_up = self.local_key_item.is_picked_up
            self.local_key_item.set_state(key_data)
            if not was_picked_up and self.local_key_item.is_picked_up and self.notif_ability:
                self.notif_ability.notify('key_item', '')

        lit = w.get('torch_lit', False)
        if lit != self.torch.lit:
            self.torch.lit = lit
            if lit:
                self.torch.particles = []

        for i, data in enumerate(w.get('levers', [])):
            if i not in self.local_levers:
                self.local_levers[i] = Lever(data['x'] // TILE_SIZE, data['y'] // TILE_SIZE)
            self.local_levers[i].set_state(data)

        passage = w.get('passage_open', False)
        if passage and not self.passage_open:
            self._erase_tiles_local(level.SECRET_PASSAGE_TILES)
            music.play_sfx('gate_opening')
        self.passage_open = passage

        wall = w.get('paid_wall')
        if wall is not None:
            if self.local_paid_wall is None:
                self.local_paid_wall = PaidWall(*level.PAID_WALL_SIGN_TILE, level.PAID_WALL_COST,
                                                level.PAID_WALL_MESSAGE)
            self.local_paid_wall.set_state(wall)
            if wall.get('unlocked') and not self.paid_wall_unlocked:
                self._erase_tiles_local(level.PAID_WALL_TILES)
                music.play_sfx('boss_gate_open')
            self.paid_wall_unlocked = wall.get('unlocked', False)

        key_wall = w.get('key_wall_destroyed', False)
        if key_wall and not self.key_wall_destroyed:
            self._erase_tiles_local(level.KEY_WALL_TILES)
            music.play_sfx('boss_gate_break')
        self.key_wall_destroyed = key_wall

        if self.potions is not None:
            self.potions.set_state(w.get('potions', []))

    def _on_sign_unlocked(self, data):
        kind = data.get('type_sign', 'lore')
        if kind == 'shop_dash':
            self.bubble_lore.open(get_text("lore_stele_dash"))
            if self.notif_ability:
                self.notif_ability.notify('dash', self.settings.get('controls', {}).get('dash', 'LSHIFT'))
        elif kind == 'lore_lever':
            self.bubble_lore.open_multi([
                {'text': get_text("lore_lever"), 'title': get_text("lore_title_fragment"),
                 'sub_title': get_text("lore_sub_sector7")},
                {'text': get_text("lore_stele"), 'title': get_text("lore_title_inscription"),
                 'sub_title': get_text("lore_sub_inscription")},
            ])
        else:
            self.bubble_lore.open()

    def _apply_doors(self, doors):
        for i, door_data in enumerate(doors):
            if i not in self.local_doors:
                self.local_doors[i] = Door(door_data['x'], door_data['y'])
            door = self.local_doors[i]
            door.set_state(door_data)
            if door.is_opening and not self._doors_were_opening.get(i, False):
                music.play_sfx('door')
            self._doors_were_opening[i] = door.is_opening
            for tracker in (self.widget_quest, self.journal_quest):
                if tracker:
                    tracker.update(self.local_key_item, door, self.boss_local,
                                   enemies_killed=self._enemies_killed_total,
                                   souls=self._souls_harvested_total)

    def _apply_boss(self, data):
        if not data or data.get('boss_defeated'):
            self._last_data_boss = data
            return
        if self.boss_local is None:
            self.boss_local = DemonSlimeBoss(
                x=0, y=0, json_path=asset_path("demon_slime.json"),
                png_path=asset_path("demon_slime.png"))
        self.boss_local.set_state(data['boss'])
        state = data['boss']['state']
        frame = data['boss'].get('frame_index', 0)
        if (state == 'CLEAVE' and self._boss_frame_previous < DemonSlimeBoss.CLEAVE_ACTIVE_FRAME_START
                <= frame):
            music.play_sfx('slash_boss')
        self._boss_state_previous = state
        self._boss_frame_previous = frame if state == 'CLEAVE' else 0
        self._last_data_boss = data

    # ------------------------------------------------------------------
    #  Events
    # ------------------------------------------------------------------

    def _on_events(self, events):
        for event in events:
            if not isinstance(event, dict):
                continue
            kind = event.get('e')
            if kind == 'sound':
                self._play_sound_event(event)
            elif kind == 'vis_full':
                self._apply_vis_full(event)
            elif kind == 'vis':
                self._apply_vis_delta(event.get('t', []))
            elif kind == 'quest_reward' and self.notif_ability:
                self.notif_ability.queue_custom('__end__', get_text("quest_reward_title"),
                                                get_text("quest_reward_sub").format(money=event.get('money', 0)))
                music.play_sfx('checkpoint')

    def _play_sound_event(self, event):
        name = event.get('n')
        if not isinstance(name, str):
            return
        if event.get('p') == self.my_id and name in PREDICTED_SOUNDS:
            return
        x, y = event.get('x'), event.get('y')
        me = self.local_players.get(self.my_id)
        if x is not None and me is not None:
            dx, dy = x - me.rect.centerx, y - me.rect.centery
            if dx * dx + dy * dy > SOUND_HEARING_RANGE ** 2:
                return
        music.play_sfx(name)

    # -- visibility ------------------------------------------------------

    def _apply_vis_full(self, event):
        width, height, bits = event['w'], event['h'], event['b']
        grid = [[bool(bits[(y * width + x) >> 3] & (1 << ((y * width + x) & 7)))
                 for x in range(width)] for y in range(height)]
        self.vis_map_local = grid
        if self.game_map:
            self.game_map._vis_map_dirty = True

    def _apply_vis_delta(self, indices):
        if not self.vis_map_local or not self.game_map:
            return
        width = self.game_map.width_map
        now_fade = pygame.time.get_ticks()
        tiles = []
        for idx in indices:
            x, y = idx % width, idx // width
            if not (0 <= y < self.game_map.height_map):
                continue
            self.vis_map_local[y][x] = True
            self.echo_fade_times[(x, y)] = now_fade
            if self._fade_surface is not None:
                self._fade_surface.fill((0, 0, 0, 0), pygame.Rect(
                    x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
            tiles.append((x, y))
        self.game_map._tiles_to_reveal.extend(tiles)
        self.game_map._vis_map_dirty = True

    # ------------------------------------------------------------------
    #  Destroyed walls (visual + collision mirror of the server's map)
    # ------------------------------------------------------------------

    def _erase_tiles_local(self, tiles):
        game_map = self.game_map
        if not game_map:
            return
        layers = getattr(game_map, 'layers_gids', [])
        names = getattr(game_map, 'layers_names', [])
        for tx, ty in tiles:
            if 0 <= tx < game_map.width_map and 0 <= ty < game_map.height_map:
                game_map.map_data[ty][tx] = 0
                for i, layer in enumerate(layers):
                    if i < len(names) and names[i] == level.DESTRUCTIBLE_LAYER:
                        layer[ty][tx] = 0
        game_map._vis_map_dirty = True
        game_map.build_grid_collision()
