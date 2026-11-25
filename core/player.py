# player.py
# Player class: physics, abilities and combat, plus client-side rendering.

import math
import pygame
import sys
import os

from settings import *
from utils.cache import flip_h, render_text, get_font_nickname

# BossAnimator is reused so that every sprite uses the same animation system
try:
    from core.demon_slime_boss import BossAnimator
    _ANIMATOR_AVAILABLE = True
except ImportError:
    try:
        from demon_slime_boss import BossAnimator
        _ANIMATOR_AVAILABLE = True
    except ImportError:
        _ANIMATOR_AVAILABLE = False
        BossAnimator = None


def _path_asset(name_file):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'assets', name_file)


# Global cache (only successful loads, from the main thread)
_ANIMATORS_CACHE = {}


def _get_animator(prefix):
    """Load and return a cached BossAnimator for p1 or p2.
    Only successful loads are cached so that failures can be retried.
    """
    if prefix in _ANIMATORS_CACHE:
        return _ANIMATORS_CACHE[prefix]
    if not _ANIMATOR_AVAILABLE:
        return None
    try:
        animator = BossAnimator(
            _path_asset(f'{prefix}.json'),
            _path_asset(f'{prefix}.png')
        )
        _ANIMATORS_CACHE[prefix] = animator
        return animator
    except Exception as e:
        print(f"[Player] animation {prefix} unavailable: {e}")
        return None


# Fallback sprite of the player (used when the animator fails)
def load_sprite(name_file):
    try:
        path = _path_asset(name_file)
        sprite = pygame.image.load(path)
        return pygame.transform.scale(sprite, (25, 58))
    except Exception as e:
        print(f"[Player] cannot load sprite {name_file}: {e}")
        return None

SPRITES_PLAYERS = [
    load_sprite('sprite_perso1.png'),
    load_sprite('sprite_perso2.png'),
    load_sprite('sprite_perso3.png'),
]

_SKINS = {
    0: ('p1', 0),   # animations p1 + sprite_perso1
    1: ('p2', 1),   # animations p2 + sprite_perso2
}
NUM_SKINS = len(_SKINS)

class Player:
    def __init__(self, x, y, id, color=COLOR_PLAYER):
        self.id = id
        self.rect = pygame.Rect(x, y, 25, 58)
        self.color = color
        self.sprite = SPRITES_PLAYERS[self.id % 3]

        # Mouvement
        self.vel_y = 0
        self.on_ground = False
        self.direction = 1  # 1 = right, -1 = left
        self.is_moving = False

        # Health and money
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.money = STARTING_MONEY
        self.damage_bonus  = 0   # 0 or 1 (doubled strike force)
        self.max_hp_bonus  = 0   # 0-5 (extra max HP)
        self.last_damage_time = 0     # 0 = never damaged
        self.is_hurt = False

        # Sounds - events produced during this tick (turned into network events by the world)
        self.sounds_to_play = []

        # Mechanics
        self.last_echo_time = -10**9          # "never": cooldowns start ready
        self.last_echo_dir_time = -10**9
        self.can_echo_dir = False
        self.lost_soul = None
        self.have_key = False
        self.death_time = None

        # Combat
        self.last_attack_time = -10**9
        self.is_attacking = False
        self.attack_rect = None
        # Hit registry: ids of the enemies already hit by the current attack.
        self.hit_enemies: set = set()

        # Abilities
        self.can_double_jump = False
        self.can_dash = False
        self.has_double_jumped = False
        self.dash_available_in_air = MAX_AIR_DASHES
        self.last_dash_time = -10**9
        self.is_dashing = False
        self.dash_direction = 0
        self.dash_distance_remaining = 0
        self.dash_start_time = 0

        # Commandes
        self.commands = {'left': False, 'right': False, 'jump': False, 'attack': False, 'dash': False}
        self.jump_previous = False

        # Game feel: assisted jumps (coyote time / jump buffer / variable jump)
        self.coyote_until = 0       # time until which a coyote jump is still allowed
        self.jump_buffer_until = 0  # time until which a remembered jump press is valid
        self.jump_cut = False       # variable jump: True once the cut has been applied for this jump

        # Game feel: knockback on damage
        self.recoil_vx = 0.0
        self.recoil_until = 0        # end time of the knockback (horizontal input is disabled until then)

        self.sounds_to_play = []
        self.sounds = {
            'jump':        True,
            'double_jump': True,
            'dash':        True,
            'attack':     True,
            'damage':       True,
        }

        # ── Animations ──────────────────────────────────────────────────────
        # Even players (0, 2) → p1 ; odd players (1) → p2
        self.skin = 0
        self.nickname = ""
        self._apply_skin(0)

        # Lazy loading: the animator stays None until the first draw()
        # (avoids calling pygame.image.load from the server thread)
        self.animator = None
        self._anim_charge_attempted = False
        self._anim_frames = []
        self._anim_current = f'{self._anim_prefix}_idle'
        self._anim_frame_index = 0
        self._anim_frame_timer_ms = 0.0
        self._anim_last_time_ms = 0
        # Alternance attack1 / attack2
        self._last_attack_num = 1
        self._attack_was_active = False
        # Client prediction: local time at which the last attack was triggered
        self._attack_local_start_ms = -ATTACK_DURATION

    def _apply_skin(self, skin):
        prefix, sprite_idx = _SKINS.get(skin, ('p1', 0))
        self._anim_prefix = prefix
        self.sprite = SPRITES_PLAYERS[sprite_idx % len(SPRITES_PLAYERS)]
        self._anim_current = f'{prefix}_idle'
        self._anim_charge_attempted = False
        self.animator = None
        self._anim_frames = []
        self._anim_frame_index = 0
        self._anim_frame_timer_ms = 0.0
        self._attack_was_active = False

    # ──────────────────────────────────────────────────────────────────────
    #  PHYSIQUE
    # ──────────────────────────────────────────────────────────────────────

    def apply_physics(self, rects_collision, now=None):
        """Apply gravity, movement and collisions.

        ``now`` is the simulation clock (ms). The server and the client prediction
        advance it by a fixed step per tick, which makes the physics replayable
        identically on both sides.
        """
        dx = 0
        dy = 0

        if now is None:
            now = pygame.time.get_ticks()

        if self.is_dashing:
            if now - self.dash_start_time >= DASH_DURATION or self.dash_distance_remaining <= 0:
                self.is_dashing = False
                self.dash_distance_remaining = 0
            else:
                speed_dash = DASH_DISTANCE / (DASH_DURATION / 1000 * FPS)
                movement_dash = min(speed_dash, self.dash_distance_remaining)
                dx = movement_dash * self.dash_direction
                self.dash_distance_remaining -= abs(movement_dash)
                self.vel_y += GRAVITY * 0.3
                if self.vel_y > 10:
                    self.vel_y = 10
                dy = self.vel_y
        else:
            # 1. Dash activation
            if self.commands.get('dash', False) and self.can_dash:
                can_dasher = self.on_ground or self.dash_available_in_air > 0

                if can_dasher and (now - self.last_dash_time >= COOLDOWN_DASH):
                    if self.commands['right']:
                        self.dash_direction = 1
                    elif self.commands['left']:
                        self.dash_direction = -1
                    else:
                        self.dash_direction = self.direction

                    self.is_dashing = True
                    self.dash_start_time = now
                    self.last_dash_time = now
                    self.dash_distance_remaining = DASH_DISTANCE

                    if not self.on_ground:
                        self.dash_available_in_air -= 1

                    self.commands['dash'] = False
                    self.sounds_to_play.append('dash')

            # 2. Horizontal movement - disabled during knockback
            in_recoil = now < self.recoil_until
            if in_recoil:
                dx = self.recoil_vx
                # The facing direction is left unchanged during recoil
            else:
                if self.commands['left']:
                    dx = -PLAYER_SPEED
                    self.direction = -1
                if self.commands['right']:
                    dx = PLAYER_SPEED
                    self.direction = 1

            # 3. Saut, Double Saut, Coyote, Jump Buffer, Variable Jump Height
            jump_current = self.commands.get('jump', False)
            edge_jump = jump_current and not self.jump_previous

            # Jump eligibility from the ground (real ground OR active coyote time)
            coyote_active = now < self.coyote_until

            jump_triggered = False
            if edge_jump:
                if self.on_ground or coyote_active:
                    self.vel_y = -JUMP_FORCE
                    self.on_ground = False
                    self.has_double_jumped = False
                    jump_triggered = True
                elif self.can_double_jump and not self.has_double_jumped:
                    self.vel_y = -DOUBLE_JUMP_FORCE
                    self.has_double_jumped = True
                    jump_triggered = True
                else:
                    # No jump possible: remember the press for the landing
                    self.jump_buffer_until = now + JUMP_BUFFER_MS

            if jump_triggered:
                self.coyote_until = 0
                self.jump_buffer_until = 0
                self.jump_cut = False

            self.jump_previous = jump_current

            # Variable jump height: if the player releases the key while rising, cut the velocity once
            if (not jump_current) and self.vel_y < 0 and not self.jump_cut:
                self.vel_y *= JUMP_CUT_FACTOR
                self.jump_cut = True

            self.vel_y += GRAVITY
            if self.vel_y > 10:
                self.vel_y = 10
            dy = self.vel_y

        # Track horizontal movement for the animation
        self.is_moving = dx != 0

        old_on_ground = self.on_ground
        self.on_ground = False

        # Axe X
        self.rect.x += dx
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                    if self.is_dashing:
                        self.is_dashing = False
                        self.dash_distance_remaining = 0
                elif dx < 0:
                    self.rect.left = wall.right
                    if self.is_dashing:
                        self.is_dashing = False
                        self.dash_distance_remaining = 0

        # Axe Y
        self.rect.y += dy
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                if dy > 0:
                    self.rect.bottom = wall.top
                    self.vel_y = 0
                    self.on_ground = True
                elif dy < 0:
                    self.rect.top = wall.bottom
                    self.vel_y = 0

        if self.on_ground and not old_on_ground:
            self.dash_available_in_air = MAX_AIR_DASHES
            if self.sounds.get('jump'):
                self.sounds_to_play.append('jump')
            # Jump buffer: a remembered press triggers an immediate jump on landing
            if now < self.jump_buffer_until and not self.is_dashing:
                self.vel_y = -JUMP_FORCE
                self.on_ground = False
                self.has_double_jumped = False
                self.jump_buffer_until = 0
                self.coyote_until = 0
                self.jump_cut = False

        # Coyote time: we just left the ground without jumping (natural fall)
        elif old_on_ground and not self.on_ground and self.vel_y >= 0:
            self.coyote_until = now + COYOTE_TIME_MS

    def handle_attack(self, now):
        """Handle the attack logic (hitbox creation, cooldown)."""
        if self.commands['attack'] and (now - self.last_attack_time > ATTACK_COOLDOWN):
            self.is_attacking = True
            self.last_attack_time = now
            self.commands['attack'] = False
            return True

        if self.is_attacking:
            if now - self.last_attack_time > ATTACK_DURATION:
                self.is_attacking = False
                self.attack_rect = None
                self.hit_enemies.clear()

        if self.is_attacking:
            if self.direction == 1:
                self.attack_rect = pygame.Rect(self.rect.right, self.rect.y, ATTACK_RANGE, self.rect.height)
            else:
                self.attack_rect = pygame.Rect(self.rect.left - ATTACK_RANGE, self.rect.y, ATTACK_RANGE, self.rect.height)

        return False

    def take_damage(self, amount, now, source_x=None):
        """Try to damage the player.
        If source_x is given, knock the player back away from the source.
        """
        if now - self.last_damage_time > INVINCIBILITY_TIME_MS:
            self.hp -= amount
            self.last_damage_time = now
            if self.hp <= 0:
                self.sounds_to_play.append('dead')
            else:
                self.sounds_to_play.append('damage')
            # Knockback: not during a dash (it would break the defensive mechanic)
            if source_x is not None and not self.is_dashing:
                direction = 1 if self.rect.centerx >= source_x else -1
                self.recoil_vx = direction * RECOIL_VX
                self.vel_y = RECOIL_VY
                self.recoil_until = now + RECOIL_DURATION_MS
                self.on_ground = False
            return True
        return False

    def respawn(self, coords_spawn):
        """Reset the player."""
        self.hp = self.max_hp
        self.rect.topleft = coords_spawn
        self.vel_y = 0
        self.on_ground = False
        # Reset the animation to leave the death state
        self._anim_current = f'{self._anim_prefix}_idle'
        self._anim_frame_index = 0
        self._anim_frame_timer_ms = 0.0
        self._attack_was_active = False
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_current)
            except KeyError:
                pass

    # ──────────────────────────────────────────────────────────────────────
    # PHYSICS STATE (client-side prediction / server reconciliation)
    # ──────────────────────────────────────────────────────────────────────
    #
    # Timers are exchanged as a number of simulation *ticks* left, not as
    # milliseconds: deadlines are tick-aligned, so converting them to ticks and
    # back (with a half-tick margin) reproduces exactly the same decisions on
    # both sides, with no rounding ties.

    @staticmethod
    def _ticks_until(deadline, now, tick_ms):
        """Ticks left before ``now < deadline`` becomes false (0 if elapsed)."""
        if deadline <= now:
            return 0
        return max(0, math.ceil((deadline - now) / tick_ms - 1e-6))

    @staticmethod
    def _deadline_in(ticks, now, tick_ms):
        """Inverse of ``_ticks_until`` (0 means "no deadline")."""
        return now + (ticks - 0.5) * tick_ms if ticks > 0 else 0

    def export_physics(self, now, tick_ms):
        """Everything ``appliquer_physique`` depends on, as plain values."""
        cd_dash = self._ticks_until(self.last_dash_time + COOLDOWN_DASH, now, tick_ms)
        dash_left = (self._ticks_until(self.dash_start_time + DASH_DURATION, now, tick_ms)
                     if self.is_dashing else 0)
        return {
            'x': self.rect.x, 'y': self.rect.y, 'vel_y': self.vel_y,
            'on_ground': self.on_ground, 'has_double_jumped': self.has_double_jumped,
            'is_dashing': self.is_dashing, 'jump_previous': self.jump_previous,
            'jump_cut': self.jump_cut, 'direction': self.direction,
            'dash_direction': self.dash_direction,
            'dash_available_in_air': self.dash_available_in_air,
            'dash_distance_remaining': self.dash_distance_remaining,
            'recoil_vx': self.recoil_vx,
            'dash_left': dash_left, 'dash_cd': cd_dash,
            'coyote': self._ticks_until(self.coyote_until, now, tick_ms),
            'jump_buf': self._ticks_until(self.jump_buffer_until, now, tick_ms),
            'recoil': self._ticks_until(self.recoil_until, now, tick_ms),
        }

    def import_physics(self, d, now, tick_ms):
        """Overwrite the physics state with one produced by ``export_physics``."""
        self.rect.x, self.rect.y = d['x'], d['y']
        self.vel_y = d['vel_y']
        self.on_ground = d['on_ground']
        self.has_double_jumped = d['has_double_jumped']
        self.is_dashing = d['is_dashing']
        self.jump_previous = d['jump_previous']
        self.jump_cut = d['jump_cut']
        self.direction = d['direction']
        self.dash_direction = d['dash_direction']
        self.dash_available_in_air = d['dash_available_in_air']
        self.dash_distance_remaining = d['dash_distance_remaining']
        self.recoil_vx = d['recoil_vx']
        # cooldown-style timers: allowed again once now - last >= duration
        self.last_dash_time = (now - COOLDOWN_DASH
                                   + (d['dash_cd'] - 0.5) * tick_ms) if d['dash_cd'] > 0 else -10**9
        self.dash_start_time = (now - DASH_DURATION
                                 + (d['dash_left'] - 0.5) * tick_ms) if d['is_dashing'] else 0
        # deadline-style timers: active while now < deadline
        self.coyote_until = self._deadline_in(d['coyote'], now, tick_ms)
        self.jump_buffer_until = self._deadline_in(d['jump_buf'], now, tick_ms)
        self.recoil_until = self._deadline_in(d['recoil'], now, tick_ms)

    # ──────────────────────────────────────────────────────────────────────
    #  ANIMATION
    # ──────────────────────────────────────────────────────────────────────

    def _init_animator(self):
        """Lazy animator loading (call from the main thread)."""
        if self._anim_charge_attempted:
            return
        self._anim_charge_attempted = True
        self.animator = _get_animator(self._anim_prefix)
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_current)
            except KeyError:
                self.animator = None
                self._anim_frames = []

    def _determine_animation(self):
        """Return the name of the animation to play for the current state."""
        p = self._anim_prefix

        if self.hp <= 0:
            return f'{p}_death'

        if self.is_hurt:
            return f'{p}_hurt'

        # Local prediction: the attack is active if the server confirms it OR
        # if the player pressed the key less than ATTACK_DURATION ms ago.
        is_attacking = (self.is_attacking or
                          pygame.time.get_ticks() - self._attack_local_start_ms < ATTACK_DURATION)

        # Detect the start of an attack to alternate attack1 / attack2
        if is_attacking and not self._attack_was_active:
            self._last_attack_num = 2 if self._last_attack_num == 1 else 1
        self._attack_was_active = is_attacking

        if is_attacking:
            return f'{p}_attack{self._last_attack_num}'

        if not self.on_ground:
            return f'{p}_jump'

        if self.is_moving or self.is_dashing:
            return f'{p}_run'

        return f'{p}_idle'

    def _update_animation(self):
        """Advance the animation by the elapsed time."""
        time_ms = pygame.time.get_ticks()
        if self._anim_last_time_ms == 0:
            self._anim_last_time_ms = time_ms
            return
        dt_ms = min(time_ms - self._anim_last_time_ms, 100)
        self._anim_last_time_ms = time_ms

        anim_wanted = self._determine_animation()

        if anim_wanted != self._anim_current:
            # Do not interrupt an attack animation before its last frame,
            # except for death or hurt which have absolute priority.
            is_attack_in_progress = '_attack' in self._anim_current
            high_priority = anim_wanted.endswith('_death') or anim_wanted.endswith('_hurt')
            attack_step_finished = (is_attack_in_progress and self._anim_frames and
                                 self._anim_frame_index < len(self._anim_frames) - 1)

            if attack_step_finished and not high_priority:
                pass  # let the attack animation finish
            else:
                self._anim_current = anim_wanted
                self._anim_frame_index = 0
                self._anim_frame_timer_ms = 0.0
                try:
                    self._anim_frames = self.animator.get_animation(anim_wanted)
                except (KeyError, AttributeError):
                    # Unknown animation: fall back to idle
                    fallback = f'{self._anim_prefix}_idle'
                    try:
                        self._anim_frames = self.animator.get_animation(fallback)
                        self._anim_current = fallback
                    except Exception:
                        self._anim_frames = []
                        return

        if not self._anim_frames:
            return

        # Freeze on the last death frame
        is_death = (self._anim_current == f'{self._anim_prefix}_death')
        if is_death and self._anim_frame_index >= len(self._anim_frames) - 1:
            return

        _, frame_duration = self._anim_frames[self._anim_frame_index]
        self._anim_frame_timer_ms += dt_ms

        if self._anim_frame_timer_ms >= frame_duration:
            self._anim_frame_timer_ms -= frame_duration
            next_idx = self._anim_frame_index + 1
            if next_idx >= len(self._anim_frames):
                self._anim_frame_index = 0  # loop (except death, handled above)
            else:
                self._anim_frame_index = next_idx

    # ──────────────────────────────────────────────────────────────────────
    #  RENDU
    # ──────────────────────────────────────────────────────────────────────

    def draw(self, surface, camera_offset=(0, 0)):
        """Draw the animated player (or a fallback rectangle) and its attack hitbox."""
        off_x, off_y = camera_offset

        # Lazy animator loading (safe: called from the main thread)
        if not self._anim_charge_attempted:
            self._init_animator()

        # White flash when hit (same effect as enemies)
        flash_active = (
            self.last_damage_time > 0
            and pygame.time.get_ticks() - self.last_damage_time < 300
        )

        if self.animator and self._anim_frames:
            self._update_animation()

            frame_surf, _ = self._anim_frames[self._anim_frame_index]

            # Horizontal mirror when the player faces left
            if self.direction == -1:
                frame_surf = flip_h(frame_surf)

            if flash_active:
                frame_surf = frame_surf.copy()
                frame_surf.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)

            sprite_w = frame_surf.get_width()
            sprite_h = frame_surf.get_height()

            # Centered horizontally on the hitbox, aligned to the bottom
            draw_x = self.rect.x - off_x + (self.rect.w - sprite_w) // 2
            draw_y = self.rect.y - off_y + self.rect.h - sprite_h

            surface.blit(frame_surf, (draw_x, draw_y))

        elif self.sprite:
            # Fallback: scaled static sprite
            sprite_to_draw = pygame.transform.flip(self.sprite, self.direction == -1, False)
            if flash_active:
                sprite_to_draw = sprite_to_draw.copy()
                sprite_to_draw.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
            surface.blit(sprite_to_draw, (self.rect.x - off_x, self.rect.y - off_y))
        else:
            # Last resort: colored rectangle
            rect_visual = pygame.Rect(
                self.rect.x - off_x, self.rect.y - off_y,
                self.rect.width, self.rect.height
            )
            pygame.draw.rect(surface, COLOR_WHITE if flash_active else self.color, rect_visual)

        # The nickname is drawn separately by draw_nickname_on_screen(),
        # directly on the final screen to avoid upscale blur.

        if DEV_MODE:
            rect_hitbox = pygame.Rect(
                self.rect.x - off_x, self.rect.y - off_y,
                self.rect.width, self.rect.height,
            )
            pygame.draw.rect(surface, (0, 255, 0), rect_hitbox, 1)

    def draw_nickname_on_screen(self, screen, camera_offset=(0, 0), zoom=1.0):
        """Draw the nickname directly on the final (post-scale) screen.
        Rendered at `base_size * zoom` to stay sharp while following the camera.
        """
        if not self.nickname:
            return
        off_x, off_y = camera_offset
        size_px = max(12, int(round(14 * zoom)))
        font = get_font_nickname(size_px)
        nickname_surf = render_text(font, self.nickname, (210, 235, 255))
        cx_screen = (self.rect.centerx - off_x) * zoom
        top_screen = (self.rect.top - off_y) * zoom
        px = int(cx_screen - nickname_surf.get_width() / 2)
        py = int(top_screen - nickname_surf.get_height() - 2 * zoom)
        bg = pygame.Surface((nickname_surf.get_width() + 6, nickname_surf.get_height() + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 10, 160))
        screen.blit(bg, (px - 3, py - 1))
        screen.blit(nickname_surf, (px, py))

    # ──────────────────────────────────────────────────────────────────────
    # NETWORK
    # ──────────────────────────────────────────────────────────────────────

    def get_detail(self, now):
        """Slowly-changing player data sent in the reliable "players" stream.

        Positions, direction and attack/dash/death flags travel in the 60 Hz
        snapshot instead. Ages are capped so the dict stops changing once a
        cooldown has elapsed (the stream is only re-sent when it changes)."""
        age_echo = min(max(0, now - self.last_echo_time), COOLDOWN_ECHO)
        age_echo_dir = min(max(0, now - self.last_echo_dir_time), COOLDOWN_ECHO_DIR)
        age_dash = min(max(0, now - self.last_dash_time), COOLDOWN_DASH)
        if self.last_damage_time > 0:
            age_damage = min(max(0, now - self.last_damage_time), INVINCIBILITY_TIME_MS)
        else:
            age_damage = None
        return {
            'id':               self.id,
            'hp':               self.hp,
            'max_hp':           self.max_hp,
            'money':           self.money,
            'can_double_jump': self.can_double_jump,
            'can_dash':        self.can_dash,
            'can_echo_dir':    self.can_echo_dir,
            'have_key':         self.have_key,
            'damage_bonus':     self.damage_bonus,
            'max_hp_bonus':     self.max_hp_bonus,
            'echo_age_ms':      int(age_echo // 50 * 50),
            'echo_dir_age_ms':  int(age_echo_dir // 50 * 50),
            'dash_age_ms':      int(age_dash // 50 * 50),
            'damage_age_ms':     None if age_damage is None else int(age_damage // 50 * 50),
            'nickname':           self.nickname,
            'skin':             self.skin,
        }

    def apply_detail(self, data):
        """Apply a dict produced by ``get_detail`` (client side)."""
        self.hp = data['hp']
        self.max_hp = data['max_hp']
        self.money = data.get('money', 0)
        self.can_double_jump = data.get('can_double_jump', False)
        self.can_dash = data.get('can_dash', False)
        self.can_echo_dir = data.get('can_echo_dir', False)
        self.have_key = data.get('have_key', False)
        self.damage_bonus = data.get('damage_bonus', 0)
        self.max_hp_bonus = data.get('max_hp_bonus', 0)
        now = pygame.time.get_ticks()
        for field, attr in (('echo_age_ms', 'last_echo_time'),
                            ('echo_dir_age_ms', 'last_echo_dir_time'),
                            ('dash_age_ms', 'last_dash_time'),
                            ('damage_age_ms', 'last_damage_time')):
            age = data.get(field)
            if age is not None:
                setattr(self, attr, now - age)
        self.is_hurt = (data.get('damage_age_ms') is not None
                             and data['damage_age_ms'] < INVINCIBILITY_TIME_MS)
        skin = data.get('skin', 0)
        if skin != self.skin:
            self.skin = skin
            self._apply_skin(skin)
        self.nickname = data.get('nickname', self.nickname)

    def apply_snapshot_flags(self, flags):
        """Apply the per-snapshot flags of a *remote* player."""
        from net import protocol as P
        self.is_dashing = bool(flags & P.PF_DASHING)
        self.is_attacking = bool(flags & P.PF_ATTACKING)
        self.direction = 1 if flags & P.PF_FACING_RIGHT else -1
        self.on_ground = bool(flags & P.PF_ON_GROUND)
        self.is_moving = bool(flags & P.PF_MOVING)
        if self.is_attacking:
            width = ATTACK_RANGE
            x = self.rect.right if self.direction == 1 else self.rect.left - width
            self.attack_rect = pygame.Rect(x, self.rect.y, width, self.rect.height)
        else:
            self.attack_rect = None
