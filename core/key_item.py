# key_item.py
# Pickable key object placed on the map. Picked up by simple contact.
# Once picked up, the player's has_key flag becomes True.

import pygame
import math
from settings import *


class KeyItem:
    """
    Pickable key placed once on the map.
    - Picked up by player contact.
    - Sets has_key = True on the player who touches it.
    - Animated: vertical floating.
    - Drawn entirely with pygame (no external sprite).

    """

    def __init__(self, x, y):
        self.rect = pygame.Rect(x - 10, y - 14, 20, 28)
        self.x_base = float(x)
        self.y_base = float(y)
        self.is_picked_up = False
        self.color        = (255, 215, 0)    # gold
        self.color_dark = (180, 140, 0)    # outline
        self.color_hole   = (30, 20, 0)      # key holes

    # ------------------------------------------------------------------
    def update(self, time_ms):
        """Floating animation (client side only)."""
        offset_y = math.sin(time_ms / 800) * 4.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    # ------------------------------------------------------------------
    def get_state(self):
        return {
            'x': int(self.x_base),
            'y': int(self.y_base),
            'is_picked_up': self.is_picked_up,
        }

    def set_state(self, data):
        self.x_base       = float(data['x'])
        self.y_base       = float(data['y'])
        self.rect.centerx = int(self.x_base)
        self.rect.centery = int(self.y_base)
        self.is_picked_up  = data.get('is_picked_up', False)

    # ------------------------------------------------------------------
    def draw(self, surface, camera_offset=(0, 0), time_ms=0):
        if self.is_picked_up:
            return

        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        # -- Pulsing golden halo (reused surface) -------------------------
        pulse = 0.6 + 0.4 * math.sin(time_ms / 500)
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for r_h, a_h in [(22, 15), (15, 35), (9, 60)]:
            pygame.draw.ellipse(self._halo_surf, (255, 215, 0, int(a_h * pulse)),
                                pygame.Rect(24 - r_h, 24 - r_h, r_h * 2, r_h * 2))
        surface.blit(self._halo_surf, (cx - 24, cy - 24))

        # -- Key drawing ---------------------------------------------------
        # The key is oriented vertically:
        # - ring (head) at the top
        # - stem going down with two teeth on the right

        # Key ring (hollow circle)
        ring_cx = cx
        ring_cy = cy - 8
        ring_r  = 7

        pygame.draw.circle(surface, self.color,        (ring_cx, ring_cy), ring_r)
        pygame.draw.circle(surface, self.color_dark, (ring_cx, ring_cy), ring_r, 2)
        # Central hole of the ring
        pygame.draw.circle(surface, self.color_hole,   (ring_cx, ring_cy), 3)

        # Vertical stem
        stem_x  = cx - 2
        stem_y  = ring_cy + ring_r - 1   # starts at the bottom of the ring
        stem_w  = 4
        stem_h  = 16

        pygame.draw.rect(surface, self.color,
                         pygame.Rect(stem_x, stem_y, stem_w, stem_h))
        pygame.draw.rect(surface, self.color_dark,
                         pygame.Rect(stem_x, stem_y, stem_w, stem_h), 1)

        # Tooth 1 (higher and longer)
        tooth1_x = stem_x + stem_w
        tooth1_y = stem_y + 4
        tooth1_w = 5
        tooth1_h = 3

        pygame.draw.rect(surface, self.color,
                         pygame.Rect(tooth1_x, tooth1_y, tooth1_w, tooth1_h))
        pygame.draw.rect(surface, self.color_dark,
                         pygame.Rect(tooth1_x, tooth1_y, tooth1_w, tooth1_h), 1)

        # Tooth 2 (lower and shorter)
        tooth2_x = stem_x + stem_w
        tooth2_y = stem_y + 9
        tooth2_w = 3
        tooth2_h = 3

        pygame.draw.rect(surface, self.color,
                         pygame.Rect(tooth2_x, tooth2_y, tooth2_w, tooth2_h))
        pygame.draw.rect(surface, self.color_dark,
                         pygame.Rect(tooth2_x, tooth2_y, tooth2_w, tooth2_h), 1)