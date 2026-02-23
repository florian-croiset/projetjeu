# cle.py
# Objet clé ramassable sur la map. Ramassé par simple contact.
# Lorsque ramassée, HAVE_KEY passe à True côté joueur.

import pygame
import math
import os
import sys
from parametres import *


def _charger_sprite_cle():
    """Tente de charger l'asset cristal_purifié.png, sinon renvoie None."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(__file__)
        chemin = os.path.join(base, 'assets', '../cristal_purifié.png')
        img = pygame.image.load(chemin).convert_alpha()
        return pygame.transform.scale(img, (20, 28))
    except Exception:
        return None


class Cle:
    """
    Clé ramassable placée une fois sur la map (haut-droite).
    - Ramassée par contact joueur.
    - Donne HAVE_KEY = True au joueur qui la touche.
    - Animée : flottement + rotation lente.
    """

    def __init__(self, x, y):
        self.rect = pygame.Rect(x - 10, y - 14, 20, 28)
        self.x_base = float(x)
        self.y_base = float(y)
        self.est_ramassee = False
        self.sprite = _charger_sprite_cle()
        self.couleur = (255, 215, 0)   # Or si pas de sprite

    # ------------------------------------------------------------------
    def mettre_a_jour(self, temps_ms):
        offset_y = math.sin(temps_ms / 800) * 4.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    # ------------------------------------------------------------------
    def get_etat(self):
        return {
            'x': self.rect.centerx,
            'y': self.rect.centery,
            'est_ramassee': self.est_ramassee,
        }

    def set_etat(self, data):
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.est_ramassee  = data.get('est_ramassee', False)

    # ------------------------------------------------------------------
    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        if self.est_ramassee:
            return
        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        # Halo doré pulsant
        pulse = 0.6 + 0.4 * math.sin(temps_ms / 500)
        halo = pygame.Surface((48, 48), pygame.SRCALPHA)
        for r_h, a_h in [(22, 15), (15, 35), (9, 60)]:
            pygame.draw.ellipse(halo, (255, 215, 0, int(a_h * pulse)),
                                pygame.Rect(24 - r_h, 24 - r_h, r_h * 2, r_h * 2))
        surface.blit(halo, (cx - 24, cy - 24))

        if self.sprite:
            r = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r)
        else:
            # Dessin simple si pas de sprite
            body = pygame.Rect(cx - 5, cy - 10, 10, 20)
            pygame.draw.rect(surface, self.couleur, body, border_radius=3)
            pygame.draw.circle(surface, self.couleur, (cx, cy - 12), 6)
            pygame.draw.circle(surface, (30, 20, 0), (cx, cy - 12), 6, 2)