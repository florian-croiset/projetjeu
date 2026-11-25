# core/enemy.py
# Unified enemy: every enemy is a tracker (listening + chase AI).
# The variants differ by max_hp in {1, 2, 3}, which also selects the sprite (e1/e2/e3).

import os
import sys
import pygame
from settings import *
from utils.cache import flip_h, TRACKER_HEARING_RADIUS_SQ

try:
    from core.demon_slime_boss import BossAnimator
except ImportError:
    from demon_slime_boss import BossAnimator


# -----------------------------------------------------------------------
# Lazy loading of the animators (main thread only)
# -----------------------------------------------------------------------
def _path_asset_enemy(name):
    base = sys._MEIPASS if getattr(sys, 'frozen', False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets', name)


_ANIMATORS_ENEMIES = {}
_OFFSET_X_FRAME = {}   # prefix -> horizontal offset of the character's center relative to the frame center


def _get_animator_enemy(prefix):
    """Return a cached BossAnimator for 'e1', 'e2' or 'e3'."""
    if prefix in _ANIMATORS_ENEMIES:
        return _ANIMATORS_ENEMIES[prefix]
    try:
        a = BossAnimator(_path_asset_enemy(f'{prefix}.json'),
                         _path_asset_enemy(f'{prefix}.png'))
        _ANIMATORS_ENEMIES[prefix] = a
        # Compute once and for all the horizontal offset of the character
        # inside its frame (most Aseprite sprites are not centered).
        _OFFSET_X_FRAME[prefix] = _compute_offset_x(a)
        return a
    except Exception as e:
        print(f"[Enemy] animator {prefix} unavailable: {e}")
        return None


def _compute_offset_x(animator):
    """Return the offset (in px) of the center of the non-transparent pixels
    relative to the frame center, measured on the first idle frame.
    A negative value means the character is left of the frame center.
    """
    try:
        # Take any idle animation
        for name, frames in animator.animations.items():
            if 'idle' in name and frames:
                surf, _ = frames[0]
                bbox = surf.get_bounding_rect()  # zone non transparente
                if bbox.width <= 0:
                    return 0
                char_cx = bbox.x + bbox.width / 2
                return char_cx - surf.get_width() / 2
        return 0
    except Exception:
        return 0


# -----------------------------------------------------------------------
# Configuration per max HP
# -----------------------------------------------------------------------
_CONFIG_PER_HP = {
    1: {'speed': 2.0,
        'width': TILE_SIZE - 12, 'height': TILE_SIZE - 8,
        'money': 8,                  'sprite': 'e1'},
    2: {'speed': ENEMY_SPEED,
        'width': TILE_SIZE - 8,  'height': TILE_SIZE - 4,
        'money': MONEY_PER_ENEMY,  'sprite': 'e2'},
    3: {'speed': 1.0,
        'width': TILE_SIZE,      'height': TILE_SIZE + 8,
        'money': 15,                 'sprite': 'e3'},
}

# Health bar colors depending on the remaining ratio
_COLOR_HP_FULL   = (220, 55,  55)
_COLOR_HP_HALF  = (230, 120, 30)
_COLOR_HP_BOTTOM     = (240, 200, 20)
_COLOR_HP_BACKGROUND    = (30,  15,  15)
_COLOR_HP_EDGE    = (80,  40,  40)
_COLOR_HEART_EMPTY = (55,  25,  25)

# Fallback color when the animator is unavailable
_COLOR_FALLBACK_PER_HP = {
    1: (210, 90, 90),
    2: COLOR_ENEMY,
    3: (140, 25, 25),
}

# -----------------------------------------------------------------------
# FSM states
# -----------------------------------------------------------------------
STATE_PATROL = 'patrol'
STATE_CHASE     = 'chase'
STATE_ATTACK    = 'attack'

# Number of frames of each attack animation (for the time -> frame mapping).
_N_FRAMES_ATTACK = {
    ('e1', 1): 9,
    ('e2', 1): 11,
    ('e3', 1): 14,
    ('e3', 2): 12,
}


class Enemy:
    """Unified enemy: tracker behaviour + attack FSM + animation."""

    def __init__(self, x, y, id, max_hp=2):
        self.id     = id
        self.max_hp = max_hp
        self.hp     = max_hp

        cfg = _CONFIG_PER_HP.get(max_hp, _CONFIG_PER_HP[2])
        self.speed_of_base = cfg['speed']
        self.money_drop     = cfg['money']
        self.sprite_prefix   = cfg['sprite']    # 'e1' | 'e2' | 'e3'
        self.color_base    = _COLOR_FALLBACK_PER_HP.get(max_hp, COLOR_ENEMY)
        self.color         = self.color_base

        self.rect = pygame.Rect(x, y, cfg['width'], cfg['height'])

        # Mouvement
        self.vel_y              = 0
        self.speed_patrol = self.speed_of_base
        self.on_ground         = False
        self.is_moving       = False
        self.direction          = 1     # 1 = right, -1 = left

        # Feedback visuel
        self.last_hit_received = 0
        self.blinking      = False

        # Sons
        self.sounds_to_play = []

        # Respawn
        self.x_start   = x
        self.y_start   = y
        self.is_dead   = False
        self.death_time = None

        # Tracker AI (always active)
        self.radius_hearing = TRACKER_HEARING_RADIUS
        self.duration_alert   = TRACKER_ALERT_DURATION
        self.speed_chase = TRACKER_CHASE_SPEED
        self.state           = STATE_PATROL
        self.target_x        = 0
        self.target_y        = 0
        self.end_alert     = 0

        # Pathfinding A* (chasse)
        # A path is cached and only re-planned at intervals
        # or when the target moved significantly (saves computation).
        self._path              = []     # liste de tuiles (tx, ty)
        self._path_index        = 0
        self._path_req_ms       = -1     # timestamp of the last consumed result
        self._last_replan_ms   = -10_000
        self._target_path_tile     = None   # (tx, ty) of the target at the time of the replan
        self._last_pos_tile   = None   # blockage detection (anti-stagnation)
        self._counter_blocking    = 0

        # FSM d'attaque
        self.last_attack_time  = -ENEMY_ATTACK_COOLDOWN
        self.is_attacking         = False
        self.attack_start_ms       = 0
        self.attack_num            = 1
        self._last_attack_num  = 1
        self.attack_already_hit       = set()

        # Animation state (sent over the network)
        self.state_anim = 'idle'  # 'idle' | 'run' | 'attack' | 'attack1' | 'attack2' | 'death'

        # Client animation (lazily loaded from draw())
        self.animator              = None
        self._anim_charge_attempted    = False
        self._anim_frames          = []
        self._anim_current        = f'{self.sprite_prefix}_idle'
        self._anim_frame_index     = 0
        self._anim_frame_timer_ms  = 0.0
        self._anim_last_time_ms = 0

    # ==================================================================
    # SERVER LOGIC
    # ==================================================================

    def alert(self, player_position, now):
        """Triggered by the server when a player emits an echo.
        Switches to CHASE if the source is within hearing radius.
        """
        px, py = player_position
        dx = self.rect.centerx - px
        dy = self.rect.centery - py
        if dx * dx + dy * dy <= TRACKER_HEARING_RADIUS_SQ:
            self.state       = STATE_CHASE
            self.target_x    = px
            self.target_y    = py
            self.end_alert = now + self.duration_alert
            return True
        return False

    def apply_logic(self, rects_collision, game_map, players, now,
                          pathfinding=None):
        """AI driving: patrol -> chase -> attack + physics.

        `pathfinding` (PathfindingService) is optional: when given, the chase
        uses A* to get around obstacles; otherwise it falls back to a straight
        line chase (historical behaviour).
        """
        # 0a. End of the damage blink (200 ms)
        if self.blinking and (now - self.last_hit_received) >= 200:
            self.blinking = False

        # 0. Fin d'alerte → retour patrouille
        if self.state == STATE_CHASE and now >= self.end_alert:
            self.state = STATE_PATROL
            self.speed_patrol = (
                self.speed_of_base if self.speed_patrol >= 0
                else -self.speed_of_base
            )
            # No longer chasing -> release the path memory
            if pathfinding is not None:
                pathfinding.forget(self.id)
            self._path = []
            self._path_index = 0
            self._target_path_tile = None

        # 1. Fin d'attaque
        if self.state == STATE_ATTACK and (
            now - self.attack_start_ms >= self._current_attack_duration()
        ):
            self.is_attacking = False
            self.attack_already_hit.clear()
            if now < self.end_alert:
                self.state = STATE_CHASE
            else:
                self.state = STATE_PATROL

        # 2. Attack trigger (from CHASE only)
        if (self.state == STATE_CHASE
                and (now - self.last_attack_time) >= ENEMY_ATTACK_COOLDOWN):
            target = self._player_to_range(players)
            if target is not None:
                self._trigger_attack(target, now)

        # 3. Choose dx depending on the state
        jump_path = False
        if self.state == STATE_ATTACK:
            dx = 0
            self.is_moving = False
            self.state_anim = self._name_state_anim_attack()
        elif self.state == STATE_CHASE:
            dx, jump_path = self._decision_chase(game_map, pathfinding, now)
            if dx != 0:
                self.speed_patrol = dx
                self.direction = 1 if dx > 0 else -1
            self.is_moving = dx != 0
            self.state_anim = 'run' if dx != 0 else 'idle'
        else:  # PATROUILLE
            if self.speed_patrol > 0:
                tile_x_check = (self.rect.right + 2) // TILE_SIZE
            else:
                tile_x_check = (self.rect.left - 2) // TILE_SIZE
            tile_y_check = (self.rect.bottom + 1) // TILE_SIZE
            if not game_map.is_solid(tile_x_check, tile_y_check):
                self.speed_patrol = -self.speed_patrol
            dx = self.speed_patrol
            if dx != 0:
                self.direction = 1 if dx > 0 else -1
            self.is_moving = dx != 0
            self.state_anim = 'run' if dx != 0 else 'idle'

        # 3b. Proactive jump if A* wants us to climb (and we are on the ground)
        if jump_path and self.on_ground and self.vel_y >= 0:
            self.vel_y = -TRACKER_JUMP_FORCE

        # 4. Physics (gravity always applies)
        was_ground = self.on_ground
        self.vel_y += GRAVITY
        if self.vel_y > 10:
            self.vel_y = 10
        dy = self.vel_y
        self.on_ground = False

        # Collisions X
        self.rect.x += dx
        wall_blocked = False
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                wall_blocked = True
                if dx > 0:
                    self.rect.right = wall.left
                    if self.state == STATE_PATROL:
                        self.speed_patrol = -self.speed_patrol
                elif dx < 0:
                    self.rect.left = wall.right
                    if self.state == STATE_PATROL:
                        self.speed_patrol = -self.speed_patrol

        # Reflex jump when chasing against a wall in front
        if (wall_blocked and was_ground
                and self.state == STATE_CHASE and self.vel_y >= 0):
            self.vel_y = -TRACKER_JUMP_FORCE
            dy = self.vel_y

        # Collisions Y
        self.rect.y += dy
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                if dy > 0:
                    self.rect.bottom = wall.top
                    self.vel_y      = 0
                    self.on_ground = True
                elif dy < 0:
                    self.rect.top = wall.bottom
                    self.vel_y    = 0

        # 5. Death (takes priority for the animation)
        if self.is_dead:
            self.state_anim = 'death'

    def take_damage(self, amount, now) -> bool:
        self.hp -= amount
        self.last_hit_received = now
        self.blinking      = True
        if self.hp <= 0:
            self.is_dead   = True
            self.death_time = now
            self.sounds_to_play.append('enemy_death')
            self.state_anim  = 'death'
            self.is_attacking = False
            self.attack_already_hit.clear()
            return True
        self.sounds_to_play.append('enemy_damage')
        return False

    def respawn(self):
        self.rect.topleft       = (self.x_start, self.y_start)
        self.hp                 = self.max_hp
        self.vel_y              = 0
        self.on_ground         = False
        self.is_dead           = False
        self.death_time         = None
        self.blinking       = False
        self.sounds_to_play       = []
        self.speed_patrol = self.speed_of_base
        self.state               = STATE_PATROL
        self.end_alert         = 0
        self.is_attacking     = False
        self.attack_already_hit.clear()
        self.attack_start_ms   = 0
        self.state_anim          = 'idle'
        # Reset pathfinding
        self._path            = []
        self._path_index      = 0
        self._path_req_ms     = -1
        self._last_replan_ms = -10_000
        self._target_path_tile   = None
        # Reset the client animation if present
        self._anim_current     = f'{self.sprite_prefix}_idle'
        self._anim_frame_index  = 0
        self._anim_frame_timer_ms = 0.0
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_current)
            except KeyError:
                self._anim_frames = []

    # ------------------------------------------------------------------
    #  Pathfinding A* (mode chasse)
    # ------------------------------------------------------------------

    def _decision_chase(self, game_map, pathfinding, now):
        """Return (dx, should_jump) for CHASE mode.

        Uses the A* path if `pathfinding` is given; otherwise a straight line
        (historical fallback). Updates the enemy's path buffer (consuming
        results, requesting a replan).
        """
        if pathfinding is None:
            return self._dx_line_right(), False

        # 1. Consume the latest A* result if newer than the previous one.
        res = pathfinding.fetch(self.id)
        if res is not None:
            ts, path = res
            if ts > self._path_req_ms:
                self._path = path
                self._path_index = 0
                self._path_req_ms = ts

        # 2. Replan if needed (stale, finished, or target moved).
        cur_tx = self.rect.centerx // TILE_SIZE
        cur_ty = self.rect.centery // TILE_SIZE
        goal_tx = int(self.target_x) // TILE_SIZE
        goal_ty = int(self.target_y) // TILE_SIZE

        stale       = (now - self._last_replan_ms) > 500
        without_path = (not self._path
                       or self._path_index >= len(self._path))
        target_moves = (self._target_path_tile is None
                       or abs(self._target_path_tile[0] - goal_tx) >= 2
                       or abs(self._target_path_tile[1] - goal_ty) >= 2)
        if stale or without_path or target_moves:
            pathfinding.request(
                self.id, (cur_tx, cur_ty), (goal_tx, goal_ty), now,
            )
            self._last_replan_ms = now
            self._target_path_tile = (goal_tx, goal_ty)

        # 3. Advance the path cursor to the next tile that is not
        # already occupied.
        while self._path_index < len(self._path):
            wx, wy = self._path[self._path_index]
            if (wx, wy) == (cur_tx, cur_ty):
                self._path_index += 1
            else:
                break

        if self._path_index >= len(self._path):
            # No usable path this frame -> straight line.
            return self._dx_line_right(), False

        # 4. Pick dx by looking at the next horizontally
        # significant tile (skip purely vertical steps).
        horiz_target = None
        end = min(len(self._path), self._path_index + 4)
        for k in range(self._path_index, end):
            wx, _wy = self._path[k]
            if wx != cur_tx:
                horiz_target = wx
                break

        if horiz_target is not None:
            target_cx = horiz_target * TILE_SIZE + TILE_SIZE // 2
            if target_cx > self.rect.centerx + 4:
                dx = self.speed_chase
            elif target_cx < self.rect.centerx - 4:
                dx = -self.speed_chase
            else:
                dx = 0
        else:
            dx = 0

        # 5. Jump if the next waypoint is above.
        wx, wy = self._path[self._path_index]
        should_jump = wy < cur_ty

        return dx, should_jump

    def _dx_line_right(self):
        """Historical chase: align dx with the target in a straight line."""
        dir_x = self.target_x - self.rect.centerx
        if dir_x > 4:
            return self.speed_chase
        if dir_x < -4:
            return -self.speed_chase
        return 0

    # ------------------------------------------------------------------
    #  Helpers d'attaque
    # ------------------------------------------------------------------

    def _player_to_range(self, players):
        """Closest living player inside the attack window, otherwise None."""
        candidates = []
        for j in players.values():
            if j.hp <= 0:
                continue
            dx = abs(j.rect.centerx - self.rect.centerx)
            dy = abs(j.rect.centery - self.rect.centery)
            if dx <= ENEMY_ATTACK_RANGE and dy <= ENEMY_ATTACK_RANGE_VERTICAL:
                candidates.append((dx * dx + dy * dy, j))
        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[0][1]

    def _trigger_attack(self, target, now):
        self.state = STATE_ATTACK
        self.is_attacking         = True
        self.attack_start_ms       = now
        self.last_attack_time  = now
        self.attack_already_hit.clear()
        # Direction locked towards the target when the attack starts
        self.direction = 1 if target.rect.centerx >= self.rect.centerx else -1
        # Alternate attack1/attack2 (e3 only)
        if self.sprite_prefix == 'e3':
            self._last_attack_num = 2 if self._last_attack_num == 1 else 1
            self.attack_num = self._last_attack_num
        else:
            self.attack_num = 1
        self.sounds_to_play.append('enemy_attack')

    def _name_state_anim_attack(self):
        if self.sprite_prefix == 'e3':
            return f'attack{self.attack_num}'
        return 'attack'

    def _current_attack_duration(self):
        if self.sprite_prefix == 'e1':
            return ENEMY_ATTACK_DURATION_E1
        if self.sprite_prefix == 'e2':
            return ENEMY_ATTACK_DURATION_E2
        return ENEMY_ATTACK_DURATION_E3_A1 if self.attack_num == 1 else ENEMY_ATTACK_DURATION_E3_A2

    def _window_hitbox_active(self):
        if self.sprite_prefix == 'e1':
            return HITBOX_FRAMES_E1
        if self.sprite_prefix == 'e2':
            return HITBOX_FRAMES_E2
        return HITBOX_FRAMES_E3_A1 if self.attack_num == 1 else HITBOX_FRAMES_E3_A2

    def hitbox_active(self, now):
        """True if the instant falls inside the active window of the current attack."""
        if not self.is_attacking:
            return False
        elapsed = now - self.attack_start_ms
        duration   = self._current_attack_duration()
        if duration <= 0:
            return False
        f0, f1 = self._window_hitbox_active()
        key = (self.sprite_prefix, self.attack_num if self.sprite_prefix == 'e3' else 1)
        n_frames = _N_FRAMES_ATTACK.get(key, 9)
        idx = min(n_frames - 1, int((elapsed / duration) * n_frames))
        return f0 <= idx <= f1

    def get_rect_hitbox_attack(self):
        p = ENEMY_ATTACK_RANGE
        if self.direction == 1:
            return pygame.Rect(self.rect.right, self.rect.y, p, self.rect.height)
        return pygame.Rect(self.rect.left - p, self.rect.y, p, self.rect.height)

    # ==================================================================
    # CLIENT ANIMATION
    # ==================================================================

    def _init_animator(self):
        if self._anim_charge_attempted:
            return
        self._anim_charge_attempted = True
        self.animator = _get_animator_enemy(self.sprite_prefix)
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_current)
            except KeyError:
                self.animator = None
                self._anim_frames = []

    def _determine_animation(self):
        p = self.sprite_prefix
        if self.is_dead or self.hp <= 0:
            return f'{p}_death'
        if self.is_attacking:
            if p == 'e3':
                return f'{p}_attack{self.attack_num}'
            return f'{p}_attack'
        if self.state_anim == 'run':
            return f'{p}_run'
        return f'{p}_idle'

    def _update_animation(self):
        time_ms = pygame.time.get_ticks()
        if self._anim_last_time_ms == 0:
            self._anim_last_time_ms = time_ms
            return
        dt_ms = min(time_ms - self._anim_last_time_ms, 100)
        self._anim_last_time_ms = time_ms

        anim_wanted = self._determine_animation()

        if anim_wanted != self._anim_current:
            is_attack_in_progress = '_attack' in self._anim_current
            high_priority       = anim_wanted.endswith('_death')
            attack_step_finished    = (is_attack_in_progress and self._anim_frames and
                                    self._anim_frame_index < len(self._anim_frames) - 1)
            if attack_step_finished and not high_priority:
                pass  # let the attack finish
            else:
                self._anim_current = anim_wanted
                self._anim_frame_index = 0
                self._anim_frame_timer_ms = 0.0
                try:
                    self._anim_frames = self.animator.get_animation(anim_wanted)
                except (KeyError, AttributeError):
                    fallback = f'{self.sprite_prefix}_idle'
                    try:
                        self._anim_frames = self.animator.get_animation(fallback)
                        self._anim_current = fallback
                    except Exception:
                        self._anim_frames = []
                        return

        if not self._anim_frames:
            return

        # Freeze on the last death frame
        is_death = self._anim_current.endswith('_death')
        if is_death and self._anim_frame_index >= len(self._anim_frames) - 1:
            return

        _, frame_duration = self._anim_frames[self._anim_frame_index]
        self._anim_frame_timer_ms += dt_ms
        if self._anim_frame_timer_ms >= frame_duration:
            self._anim_frame_timer_ms -= frame_duration
            next_idx = self._anim_frame_index + 1
            if next_idx >= len(self._anim_frames):
                # For _attack: let it replay (the exit comes from set_state / the server)
                self._anim_frame_index = 0
            else:
                self._anim_frame_index = next_idx

    # ==================================================================
    #  RENDU
    # ==================================================================

    def draw(self, surface, camera_offset=(0, 0)):
        """Draw the animated enemy. Hidden once dead and the death animation is finished."""
        if self.is_dead:
            # Let the death animation play once, then hide the enemy
            if self._anim_current and self._anim_current.endswith('_death') \
                    and self._anim_frames \
                    and self._anim_frame_index >= len(self._anim_frames) - 1:
                return
            if not self._anim_current or not self._anim_current.endswith('_death'):
                # Not switched to death yet - let it through to start it
                pass

        if not self._anim_charge_attempted:
            self._init_animator()

        # White flash when hit
        flash_active = False
        if self.blinking:
            if pygame.time.get_ticks() - self.last_hit_received < 200:
                flash_active = True
            else:
                self.blinking = False

        off_x, off_y = camera_offset
        rect_visual = pygame.Rect(
            self.rect.x - off_x, self.rect.y - off_y,
            self.rect.width, self.rect.height,
        )

        if self.animator and self._anim_frames:
            self._update_animation()
            frame_surf, _ = self._anim_frames[self._anim_frame_index]
            if self.direction == -1:
                frame_surf = flip_h(frame_surf)
            if flash_active:
                frame_surf = frame_surf.copy()
                frame_surf.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
            sw = frame_surf.get_width()
            sh = frame_surf.get_height()
            # Compensate the character's offset inside the Aseprite frame.
            # offset_in_frame is measured on an unflipped frame; the sign
            # is inverted when facing left.
            offset_in_frame = _OFFSET_X_FRAME.get(self.sprite_prefix, 0)
            adj_x = -offset_in_frame * self.direction
            draw_x = self.rect.centerx - off_x - sw // 2 + int(adj_x)
            draw_y = self.rect.centery - off_y - sh + 25
            surface.blit(frame_surf, (draw_x, draw_y))
        else:
            # Fallback: flat colored rect (animation unavailable)
            if self.is_dead:
                return
            color = COLOR_WHITE if flash_active else self.color_base
            pygame.draw.rect(surface, color, rect_visual)

        if DEV_MODE and not self.is_dead:
            pygame.draw.rect(surface, (255, 0, 0), rect_visual, 1)
            atk = self.get_rect_hitbox_attack()
            atk_visual = pygame.Rect(
                atk.x - off_x, atk.y - off_y, atk.width, atk.height,
            )
            pygame.draw.rect(surface, (255, 140, 0), atk_visual, 1)


    def _draw_hearts(self, surface, rect_visual):
        heart_w    = 7
        heart_h    = 6
        spacing = 3
        margin_bottom  = 4

        total_w = self.max_hp * heart_w + (self.max_hp - 1) * spacing

        if (not hasattr(self, '_cache_hp_val')
                or self._cache_hp_val != self.hp
                or self._cache_max_hp != self.max_hp):
            self._cache_hp_val = self.hp
            self._cache_max_hp = self.max_hp
            self._cache_bar_hp = pygame.Surface((total_w + 1, heart_h + 1), pygame.SRCALPHA)
            surf = self._cache_bar_hp

            ratio = self.hp / self.max_hp if self.max_hp > 0 else 0
            if ratio > 0.6:
                color_full = _COLOR_HP_FULL
            elif ratio > 0.35:
                color_full = _COLOR_HP_HALF
            else:
                color_full = _COLOR_HP_BOTTOM

            for i in range(self.max_hp):
                cx = i * (heart_w + spacing)
                pygame.draw.rect(surf, (8, 4, 4),
                                 pygame.Rect(cx + 1, 1, heart_w, heart_h), border_radius=2)
                pygame.draw.rect(surf, _COLOR_HP_BACKGROUND,
                                 pygame.Rect(cx, 0, heart_w, heart_h), border_radius=2)
                if i < self.hp:
                    pygame.draw.rect(surf, color_full,
                                     pygame.Rect(cx, 0, heart_w, heart_h), border_radius=2)
                    pygame.draw.rect(surf, (255, 200, 200),
                                     pygame.Rect(cx + 1, 1, heart_w - 2, 1))
                else:
                    pygame.draw.rect(surf, _COLOR_HEART_EMPTY,
                                     pygame.Rect(cx, 0, heart_w, heart_h), border_radius=2)
                pygame.draw.rect(surf, _COLOR_HP_EDGE,
                                 pygame.Rect(cx, 0, heart_w, heart_h), width=1, border_radius=2)

        bx = rect_visual.centerx - total_w // 2
        by = rect_visual.top - heart_h - margin_bottom
        surface.blit(self._cache_bar_hp, (bx, by))

    # ==================================================================
    # NETWORK
    # ==================================================================

    def get_state(self) -> dict:
        """Slowly-changing data for the reliable "enemies" stream.

        Position, facing and the dead/blink/attack/moving flags travel in the
        60 Hz snapshot instead (see ``apply_snapshot_flags``)."""
        return {
            'id':              self.id,
            'max_hp':          self.max_hp,
            'hp':              self.hp,
            'is_dead':         self.is_dead,
            'blinking':        self.blinking,
            'state_anim':      self.state_anim,
            'attack_num':      self.attack_num,
            'attack_start_ms': self.attack_start_ms,
        }

    def set_state(self, data: dict):
        """Apply a dict produced by ``get_state`` (client side)."""
        self.hp = data['hp']
        self.max_hp = data.get('max_hp', self.max_hp)
        self.is_dead = data.get('is_dead', False)
        self.blinking = data.get('blinking', False)

        new_state_anim = data.get('state_anim', 'idle')
        new_attack_num = data.get('attack_num', 1)
        new_start = data.get('attack_start_ms', 0)
        # A new attack started when the server's start timestamp changed.
        if new_state_anim.startswith('attack') and new_start != self.attack_start_ms:
            self.attack_start_ms = new_start
            self.is_attacking = True
        elif not new_state_anim.startswith('attack'):
            self.is_attacking = False
        self.state_anim = new_state_anim
        self.attack_num = new_attack_num

        if self.blinking:
            self.last_hit_received = pygame.time.get_ticks()

    def apply_snapshot_flags(self, flags):
        """Apply the flags carried by every snapshot."""
        from net import protocol as P
        self.direction = 1 if flags & P.EF_FACING_RIGHT else -1
        self.is_moving = bool(flags & P.EF_MOVING)
        if flags & P.EF_DEAD:
            self.is_dead = True


# -----------------------------------------------------------------------
# Backward-compatible alias: every enemy is a tracker.
# -----------------------------------------------------------------------
EnemyTracker = Enemy
