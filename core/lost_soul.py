# lost_soul.py
# Object left by the player on death, holding their money.

import pygame
import os
import sys
import math
from settings import *


def _load_sprite_crystal_lost():
    """Load assets/cristal_purifié.png tinted violet for the lost souls."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.scale(img, (16, 24))
        # Tint violet to distinguish from free souls
        tint = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        tint.fill((160, 100, 255, 80))
        img.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return img
    except Exception as e:
        print(f'[LOST_SOUL] sprite not found: {e}')
        return None

SPRITE_CRYSTAL_LOST = None


class LostSoul:
    # A simple global counter is used for the ids
    _next_id = 0
    
    def __init__(self, x, y, player_id, money=0):
        self.id = LostSoul._next_id
        LostSoul._next_id += 1
        
        self.rect = pygame.Rect(x, y, 16, 24)
        self.player_id = player_id
        self.money = money
        self.color = COLOR_LOST_SOUL
        self.phase = (self.id * 0.91) % (2 * math.pi)
        print(f"[LOST_SOUL] soul {self.id} created for player {self.player_id} at ({x}, {y})")

        global SPRITE_CRYSTAL_LOST
        if SPRITE_CRYSTAL_LOST is None:
            SPRITE_CRYSTAL_LOST = _load_sprite_crystal_lost()
        self.sprite = SPRITE_CRYSTAL_LOST.copy() if SPRITE_CRYSTAL_LOST else None

    def get_state(self):
        """For network sending."""
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'id_player': self.player_id,
            'money': self.money,
        }

    def set_state(self, data):
        """For network reception."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.player_id = data['id_player']
        self.money = data.get('money', self.money)

    def draw(self, surface, camera_offset=(0, 0), time_ms=None, money_max=None):
        """Draw the lost crystal with a violet halo. Shrinks with the remaining money."""
        off_x, off_y = camera_offset
        cx = self.rect.x + self.rect.width // 2 - off_x
        cy = self.rect.y + self.rect.height // 2 - off_y

        if time_ms is None:
            time_ms = pygame.time.get_ticks()
        pulse = 0.7 + 0.3 * math.sin(time_ms / 600 + self.phase)
        r, g, b = self.color

        # Fill ratio (1.0 = full, 0.0 = empty)
        if money_max and money_max > 0:
            ratio = max(0.15, self.money / money_max)
        else:
            ratio = 1.0

        # Violet halo
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for radius, alpha_base in [(26, 20), (18, 40), (11, 70)]:
            a = int(alpha_base * pulse * ratio)
            r_scaled = int(radius * ratio)
            if r_scaled > 0:
                pygame.draw.ellipse(self._halo_surf, (r, g, b, a),
                                    pygame.Rect(30 - r_scaled, 30 - r_scaled,
                                                r_scaled * 2, r_scaled * 2))
        surface.blit(self._halo_surf, (cx - 30, cy - 30))

        if self.sprite:
            alpha = int((160 + 95 * pulse) * ratio)
            scaled_w = max(4, int(16 * ratio))
            scaled_h = max(6, int(24 * ratio))
            sprite_scaled = pygame.transform.scale(self.sprite, (scaled_w, scaled_h))
            sprite_scaled.set_alpha(alpha)
            r_spr = sprite_scaled.get_rect(center=(cx, cy))
            surface.blit(sprite_scaled, r_spr)
        else:
            w = max(4, int(16 * ratio))
            h = max(6, int(24 * ratio))
            rect_visual = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.ellipse(surface, self.color, rect_visual)