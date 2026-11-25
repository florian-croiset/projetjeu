# loot_soul.py
# Loot soul: bursts out of a killed enemy, scatters with physics,
# then settles on the ground. The player walks over it to pick it up.
# Inspired by the geo system of Hollow Knight.

import pygame
import math
import random
import os
import sys
from settings import *


def _load_sprite_loot():
    """Load the crystal sprite scaled for loot souls."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, (10, 15))
    except Exception as e:
        print(f'[LOOT_SOUL] sprite not found: {e}')
        return None


SPRITE_LOOT = None  # Loaded on first instantiation


class LootSoul:
    """
    Loot soul dropped by a killed enemy.
    - 'dispersion' phase: bursts out with random velocity, gravity, bounces.
    - 'rest' phase: floats gently (sine wave), picked up by contact.
    - Disappears after LOOT_LIFETIME ms once settled.
    """

    _next_id = 0

    def __init__(self, x, y, value=1):
        self.id = LootSoul._next_id
        LootSoul._next_id += 1

        self.value = value

        # Hitbox (smaller than FreeSoul)
        w, h = 10, 14
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        # Base position (used during the rest phase)
        self.x_base = float(x)
        self.y_base = float(y)

        # Scatter physics
        self.vel_x = random.uniform(-LOOT_BURST_SPEED, LOOT_BURST_SPEED)
        self.vel_y = random.uniform(-LOOT_BURST_SPEED, -LOOT_BURST_SPEED * 0.3)

        # State
        self.phase = 'dispersion'
        self.creation_time = 0      # set by the server on spawn
        self.time_rest = None
        self.on_ground = False

        # Animation
        self.phase_anim = (self.id * 0.91) % (2 * math.pi)
        self.color = COLOR_LOOT_SOUL

        global SPRITE_LOOT
        if SPRITE_LOOT is None:
            SPRITE_LOOT = _load_sprite_loot()
        self.sprite = SPRITE_LOOT.copy() if SPRITE_LOOT else None

        # Grouped visual mode (client side only): N decorative sub-souls
        # generated with an RNG seeded by the network id (consistent across clients).
        self.num_visuals = 0
        self.visuals = []
        self._id_net = None

    # ------------------------------------------------------------------
    # LOGIC (called by the server every frame)
    # ------------------------------------------------------------------

    def update(self, time_ms, rects_collision):
        """Update the physics or the animation depending on the phase."""
        if self.phase == 'dispersion':
            self._update_dispersion(time_ms, rects_collision)
        else:
            self._update_rest(time_ms)

    def _update_dispersion(self, time_ms, rects_collision):
        """Physics: gravity, movement, bounces on walls/ground."""
        # Gravity
        self.vel_y += GRAVITY
        if self.vel_y > 10:
            self.vel_y = 10

        dx = self.vel_x
        dy = self.vel_y

        # X collision
        self.rect.x += int(dx)
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                elif dx < 0:
                    self.rect.left = wall.right
                self.vel_x *= -LOOT_BOUNCE_DAMPING

        # Y collision
        self.on_ground = False
        self.rect.y += int(dy)
        for wall in rects_collision:
            if self.rect.colliderect(wall):
                if dy > 0:
                    self.rect.bottom = wall.top
                    self.on_ground = True
                    self.vel_x *= 0.5  # Ground friction
                elif dy < 0:
                    self.rect.top = wall.bottom
                self.vel_y *= -LOOT_BOUNCE_DAMPING

        # Switch to rest?
        speed = abs(self.vel_x) + abs(self.vel_y)
        time_elapsed = time_ms - self.creation_time
        if (speed < LOOT_REST_THRESHOLD and self.on_ground) or time_elapsed > LOOT_MAX_DISPERSION_TIME:
            self.phase = 'rest'
            self.x_base = float(self.rect.centerx)
            self.y_base = float(self.rect.centery)
            self.time_rest = time_ms
            self.vel_x = 0
            self.vel_y = 0

    def _update_rest(self, time_ms):
        """Sine-wave float identical to FreeSoul."""
        offset_y = math.sin(time_ms / 900 + self.phase_anim) * 3.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    def is_expired(self, time_ms):
        """True if the orb has been lying on the ground for too long."""
        if self.phase != 'rest' or self.time_rest is None:
            return False
        return time_ms - self.time_rest > LOOT_LIFETIME

    # ------------------------------------------------------------------
    # NETWORK
    # ------------------------------------------------------------------

    def get_state(self):
        """Serialisation sent to the client(s)."""
        return {
            'id':         self.id,
            'x':          self.rect.centerx,
            'y':          self.rect.centery,
            'value':     self.value,
            'phase':      self.phase,
            'num_visuals': getattr(self, 'num_visuals', 0),
        }

    def set_state(self, data):
        """Client-side update from the network data."""
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.value = data.get('value', 1)
        self.phase = data.get('phase', 'rest')
        num_visuals = data.get('num_visuals', 0)
        if num_visuals > 1 and not self.visuals:
            self._create_visuals(data['id'], num_visuals)

    def _create_visuals(self, id_net, num_visuals):
        """Generate N visual sub-souls with an RNG seeded by the network id,
        so that every client sees the same burst.
        """
        self.num_visuals = num_visuals
        self._id_net = id_net
        rng = random.Random(id_net)
        cx = float(self.rect.centerx)
        cy = float(self.rect.centery)
        for _ in range(num_visuals):
            self.visuals.append({
                'x':          cx,
                'y':          cy,
                'vx':         rng.uniform(-LOOT_BURST_SPEED, LOOT_BURST_SPEED),
                'vy':         rng.uniform(-LOOT_BURST_SPEED, -LOOT_BURST_SPEED * 0.3),
                'phase':      'dispersion',
                't_rest':    None,
                'phase_anim': rng.uniform(0, 2 * math.pi),
                'x_base':     cx,
                'y_base':     cy,
            })

    def update_visuals(self, time_ms, game_map=None):
        """Client side: physics of the decorative sub-souls with collisions
        against the local map (otherwise they fall into the void).
        """
        if not self.visuals:
            return
        if not self.creation_time:
            self.creation_time = time_ms

        # Temporary hitbox reused for collision tests
        if not hasattr(self, '_v_rect'):
            self._v_rect = pygame.Rect(0, 0, 6, 6)
        hb = self._v_rect

        for v in self.visuals:
            if v['phase'] == 'dispersion':
                v['vy'] += GRAVITY
                if v['vy'] > 10:
                    v['vy'] = 10

                rects = []
                if game_map is not None:
                    hb.center = (int(v['x']), int(v['y']))
                    rects = game_map.get_nearby_rects(hb)

                # X movement + collision
                v['x'] += v['vx']
                hb.center = (int(v['x']), int(v['y']))
                for wall in rects:
                    if hb.colliderect(wall):
                        if v['vx'] > 0:
                            v['x'] = wall.left - hb.width / 2
                        elif v['vx'] < 0:
                            v['x'] = wall.right + hb.width / 2
                        v['vx'] *= -LOOT_BOUNCE_DAMPING
                        hb.center = (int(v['x']), int(v['y']))

                # Y movement + collision
                on_ground = False
                v['y'] += v['vy']
                hb.center = (int(v['x']), int(v['y']))
                for wall in rects:
                    if hb.colliderect(wall):
                        if v['vy'] > 0:
                            v['y'] = wall.top - hb.height / 2
                            on_ground = True
                            v['vx'] *= 0.5
                        elif v['vy'] < 0:
                            v['y'] = wall.bottom + hb.height / 2
                        v['vy'] *= -LOOT_BOUNCE_DAMPING
                        hb.center = (int(v['x']), int(v['y']))

                v['vx'] *= 0.99
                speed = abs(v['vx']) + abs(v['vy'])
                t_elapsed = time_ms - self.creation_time
                if (speed < LOOT_REST_THRESHOLD and on_ground) or t_elapsed > LOOT_MAX_DISPERSION_TIME:
                    v['phase'] = 'rest'
                    v['t_rest'] = time_ms
                    v['x_base'] = v['x']
                    v['y_base'] = v['y']
                    v['vx'] = 0
                    v['vy'] = 0
            else:
                offset_y = math.sin(time_ms / 900 + v['phase_anim']) * 3.0
                v['y'] = v['y_base'] + offset_y

    # ------------------------------------------------------------------
    # RENDERING (called by the client)
    # ------------------------------------------------------------------

    def draw(self, surface, camera_offset=(0, 0), time_ms=0):
        """Draw the orb with a pulsing halo + sprite. In grouped mode,
        draws the N sub-souls instead of the main soul.
        """
        off_x, off_y = camera_offset
        r, g, b = self.color

        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((40, 40), pygame.SRCALPHA)

        if self.visuals:
            for v in self.visuals:
                self._draw(surface, off_x, off_y,
                                  int(v['x']), int(v['y']),
                                  v['phase_anim'], time_ms, r, g, b)
        else:
            self._draw(surface, off_x, off_y,
                              self.rect.centerx, self.rect.centery,
                              self.phase_anim, time_ms, r, g, b)

    def _draw(self, surface, off_x, off_y, x_world, y_world,
                     phase_anim, time_ms, r, g, b):
        cx = x_world - off_x
        cy = y_world - off_y
        pulse = 0.7 + 0.3 * math.sin(time_ms / 600 + phase_anim)

        self._halo_surf.fill((0, 0, 0, 0))
        for radius, alpha_base in [(18, 15), (13, 30), (8, 50)]:
            a = int(alpha_base * pulse)
            pygame.draw.ellipse(self._halo_surf, (r, g, b, a),
                                pygame.Rect(20 - radius, 20 - radius, radius * 2, radius * 2))
        surface.blit(self._halo_surf, (cx - 20, cy - 20))

        if self.sprite:
            alpha = int(180 + 75 * pulse)
            self.sprite.set_alpha(alpha)
            r_spr = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r_spr)
        else:
            pygame.draw.circle(surface, self.color, (cx, cy), 5)
