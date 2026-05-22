import pygame
from parametres import TAILLE_TUILE


class Levier:
    def __init__(self, tuile_x, tuile_y):
        self.tuile_x = tuile_x
        self.tuile_y = tuile_y
        self.x = tuile_x * TAILLE_TUILE
        self.y = tuile_y * TAILLE_TUILE
        # Rect légèrement plus haut pour être plus facile à atteindre par l'attaque
        self.rect = pygame.Rect(self.x, self.y - TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE * 2)
        self.active = False
        self.temps_activation = 0

    def activer(self, timestamp):
        self.active = True
        self.temps_activation = timestamp

    def reset(self):
        self.active = False
        self.temps_activation = 0

    def get_etat(self):
        return {
            'x': self.x,
            'y': self.y,
            'active': self.active,
            'temps': self.temps_activation,
        }

    def set_etat(self, data):
        self.active = data.get('active', False)
        self.temps_activation = data.get('temps', 0)

    def dessiner(self, surface, camera_offset=(0, 0), ticks=0):
        if not self.active:
            return
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y
        # Halo jaune semi-transparent par-dessus le sprite de tuile
        glow = pygame.Surface((TAILLE_TUILE, TAILLE_TUILE), pygame.SRCALPHA)
        glow.fill((255, 220, 50, 90))
        surface.blit(glow, (sx, sy))
