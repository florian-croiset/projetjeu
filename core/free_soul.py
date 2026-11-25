# free_soul.py
# Free soul: floats on the map, picked up by simply touching it.
# Unlike the LostSoul (tied to a player's death), the FreeSoul exists
# independently and rewards exploration.

import pygame
import math
import os
import sys
from settings import *


def _load_sprite_crystal():
    """Load assets/cristal_purifié.png scaled for the free souls."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, (16, 24))
    except Exception as e:
        print(f'[FREE_SOUL] sprite not found: {e}')
        return None

SPRITE_CRYSTAL_FREE = None  # Loaded on first instantiation


class FreeSoul:
    """
    Floating free soul placed on the map.
    - Visible from the start (no echo needed).
    - Picked up by simply colliding with the player (no attack needed).
    - Gives FREE_SOUL_MONEY souls to the player who touches it.
    - Animated: sinusoidal vertical float + pulsing glow.

    """

    _next_id = 0

    def __init__(self, x, y, value=None):
        self.id = FreeSoul._next_id
        FreeSoul._next_id += 1

        self.value = value if value is not None else FREE_SOUL_MONEY

        # Pickup hitbox (centered on the position)
        w, h = 14, 20
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        # Base position for the floating animation
        self.x_base = float(x)
        self.y_base = float(y)

        # Per-soul animation phase (keeps them from moving in sync)
        self.phase = (self.id * 1.37) % (2 * math.pi)

        self.color = COLOR_FREE_SOUL
        self.is_picked_up = False

        global SPRITE_CRYSTAL_FREE
        if SPRITE_CRYSTAL_FREE is None:
            SPRITE_CRYSTAL_FREE = _load_sprite_crystal()
        self.sprite = SPRITE_CRYSTAL_FREE.copy() if SPRITE_CRYSTAL_FREE else None

    # ------------------------------------------------------------------
    # ANIMATION (client side only)
    # ------------------------------------------------------------------

    def update(self, time_ms):
        """Floating animation (purely cosmetic, client side)."""
        # Vertical float: +-4 pixels over 1.8 s
        offset_y = math.sin(time_ms / 900 + self.phase) * 4.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    # ------------------------------------------------------------------
    # NETWORK
    # ------------------------------------------------------------------

    def get_state(self):
        """Serialisation sent to the client(s) - base position is fixed."""
        return {
            'id':     self.id,
            'x':      int(self.x_base),
            'y':      int(self.y_base),
            'value': self.value,
        }

    def set_state(self, data):
        """Client-side update from the network data."""
        self.x_base       = float(data['x'])
        self.y_base       = float(data['y'])
        self.rect.centerx = int(self.x_base)
        self.rect.centery = int(self.y_base)
        self.value       = data.get('value', FREE_SOUL_MONEY)

    # ------------------------------------------------------------------
    # RENDERING (called by the client)
    # ------------------------------------------------------------------

    def draw(self, surface, camera_offset=(0, 0), time_ms=0):
        """Draw the crystal with a pulsing halo + sprite when available."""
        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        pulse = 0.7 + 0.3 * math.sin(time_ms / 600 + self.phase)
        r, g, b = self.color

        # Pulsing outer halo - reused surface, zero allocation per frame
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for radius, alpha_base in [(28, 18), (20, 35), (13, 60)]:
            a = int(alpha_base * pulse)
            pygame.draw.ellipse(self._halo_surf, (r, g, b, a),
                                pygame.Rect(30 - radius, 30 - radius, radius * 2, radius * 2))
        surface.blit(self._halo_surf, (cx - 30, cy - 30))

        if self.sprite:
            # Slight alpha variation for the pulse effect
            alpha = int(180 + 75 * pulse)
            self.sprite.set_alpha(alpha)
            r_spr = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r_spr)
        else:
            # Fallback: colored ellipse - reused surface
            if not hasattr(self, '_body_surf'):
                self._body_surf = pygame.Surface((12, 18), pygame.SRCALPHA)
            self._body_surf.fill((0, 0, 0, 0))
            pygame.draw.ellipse(self._body_surf, (r, g, b, 220), pygame.Rect(0, 0, 12, 18))
            surface.blit(self._body_surf, (cx - 6, cy - 9))