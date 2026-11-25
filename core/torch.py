import pygame
import math
import os
import sys
import random
from settings import *


def _load_sprite_torch():
    try:
        base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
        img = pygame.image.load(os.path.join(base, 'assets', 'Torch.png')).convert_alpha()
        return pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE * 2))
    except Exception as e:
        print(f'[TORCH] sprite not found: {e}')
        return None


class Torch:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE * 2)
        self.lit = False
        self.sprite = _load_sprite_torch()
        self.never_used = True

        # Flame particles
        self.particles = []

    def toggle(self):
        self.lit = not self.lit
        self.never_used = False
        if self.lit:
            self.particles = []
        return self.lit

    def update(self, time_ms):
        if not self.lit:
            return
        # Spawn a new particle
        if random.random() < 0.4:
            self.particles.append({
                'x': self.x + TILE_SIZE // 2 + random.randint(-4, 4),
                'y': self.y + 4,
                'vy': -random.uniform(0.5, 1.5),
                'vx': random.uniform(-0.3, 0.3),
                'life': random.randint(20, 40),
                'life_max': 40,
                'size': random.randint(3, 6),
            })
        # Update the particles
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
        self.particles = [p for p in self.particles if p['life'] > 0]

    def draw(self, surface, camera_offset=(0, 0), time_ms=0):
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        # --- Light halo (when lit) ---
        if self.lit:
            pulse = 0.85 + 0.15 * math.sin(time_ms / 120)
            radius = int(TORCH_LIGHT_RADIUS * pulse)
            halo = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            for r, a in [(radius, 18), (int(radius*0.7), 35), (int(radius*0.4), 60)]:
                pygame.draw.circle(halo, (255, 140, 30, a), (radius, radius), r)
            cx = sx + TILE_SIZE // 2
            cy = sy + TILE_SIZE // 2
            surface.blit(halo, (cx - radius, cy - radius))

        # --- Sprite or rectangle ---
        if self.sprite:
            surface.blit(self.sprite, (sx, sy))
        else:
            pygame.draw.rect(surface, (100, 60, 20),
                             pygame.Rect(sx + 10, sy, 12, TILE_SIZE * 2))

        # --- Flame particles ---
        if self.lit:
            for p in self.particles:
                ratio = p['life'] / p['life_max']
                r = 255
                g = int(80 + 120 * ratio)
                b = 0
                alpha = int(200 * ratio)
                size = max(1, int(p['size'] * ratio))
                px = int(p['x']) - off_x
                py = int(p['y']) - off_y
                flame = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
                pygame.draw.circle(flame, (r, g, b, alpha), (size, size), size)
                surface.blit(flame, (px - size, py - size))