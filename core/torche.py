import pygame
import math
import os
import sys
import random
from parametres import *


def _charger_sprite_torche():
    try:
        base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
        img = pygame.image.load(os.path.join(base, 'assets', 'Torche.png')).convert_alpha()
        return pygame.transform.scale(img, (TAILLE_TUILE, TAILLE_TUILE * 2))
    except Exception as e:
        print(f'[TORCHE] Sprite non trouvé : {e}')
        return None


class Torche:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, TAILLE_TUILE, TAILLE_TUILE * 2)
        self.allumee = False
        self.sprite = _charger_sprite_torche()

        # Particules de flamme
        self.particules = []

    def toggle(self):
        self.allumee = not self.allumee
        if self.allumee:
            self.particules = []
        return self.allumee

    def mettre_a_jour(self, temps_ms):
        if not self.allumee:
            return
        # Spawn nouvelle particule
        if random.random() < 0.4:
            self.particules.append({
                'x': self.x + TAILLE_TUILE // 2 + random.randint(-4, 4),
                'y': self.y + 4,
                'vy': -random.uniform(0.5, 1.5),
                'vx': random.uniform(-0.3, 0.3),
                'vie': random.randint(20, 40),
                'vie_max': 40,
                'taille': random.randint(3, 6),
            })
        # Mettre à jour les particules
        for p in self.particules:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vie'] -= 1
        self.particules = [p for p in self.particules if p['vie'] > 0]

    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        # --- Halo de lumière (si allumée) ---
        if self.allumee:
            pulse = 0.85 + 0.15 * math.sin(temps_ms / 120)
            rayon = int(RAYON_LUMIERE_TORCHE * pulse)
            halo = pygame.Surface((rayon * 2, rayon * 2), pygame.SRCALPHA)
            for r, a in [(rayon, 18), (int(rayon*0.7), 35), (int(rayon*0.4), 60)]:
                pygame.draw.circle(halo, (255, 140, 30, a), (rayon, rayon), r)
            cx = sx + TAILLE_TUILE // 2
            cy = sy + TAILLE_TUILE // 2
            surface.blit(halo, (cx - rayon, cy - rayon))

        # --- Sprite ou rectangle ---
        if self.sprite:
            surface.blit(self.sprite, (sx, sy))
        else:
            pygame.draw.rect(surface, (100, 60, 20),
                             pygame.Rect(sx + 10, sy, 12, TAILLE_TUILE * 2))

        # --- Particules de flamme ---
        if self.allumee:
            for p in self.particules:
                ratio = p['vie'] / p['vie_max']
                r = 255
                g = int(80 + 120 * ratio)
                b = 0
                alpha = int(200 * ratio)
                taille = max(1, int(p['taille'] * ratio))
                px = int(p['x']) - off_x
                py = int(p['y']) - off_y
                flamme = pygame.Surface((taille*2, taille*2), pygame.SRCALPHA)
                pygame.draw.circle(flamme, (r, g, b, alpha), (taille, taille), taille)
                surface.blit(flamme, (px - taille, py - taille))