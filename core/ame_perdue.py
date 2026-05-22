# ame_perdue.py
# Objet laissé par le joueur à sa mort, contenant son "argent".

import pygame
import os
import sys
import math
from parametres import *


def _charger_sprite_cristal_perdu():
    """Charge assets/cristal_purifié.png teinté violet pour les âmes perdues."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        chemin = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(chemin).convert_alpha()
        img = pygame.transform.scale(img, (16, 24))
        # Teinter en violet pour distinguer des âmes libres
        teinture = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        teinture.fill((160, 100, 255, 80))
        img.blit(teinture, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return img
    except Exception as e:
        print(f'[AME_PERDUE] Sprite non trouvé : {e}')
        return None

SPRITE_CRISTAL_PERDU = None


class AmePerdue:
    # On utilise un compteur global simple pour les ID
    _prochain_id = 0
    
    def __init__(self, x, y, id_joueur, argent=0):
        self.id = AmePerdue._prochain_id
        AmePerdue._prochain_id += 1
        
        self.rect = pygame.Rect(x, y, 16, 24)
        self.id_joueur = id_joueur
        self.argent = argent
        self.couleur = COULEUR_AME_PERDUE
        self.phase = (self.id * 0.91) % (2 * math.pi)
        print(f"Ame {self.id} creee pour Joueur {self.id_joueur} a ({x}, {y})")

        global SPRITE_CRISTAL_PERDU
        if SPRITE_CRISTAL_PERDU is None:
            SPRITE_CRISTAL_PERDU = _charger_sprite_cristal_perdu()
        self.sprite = SPRITE_CRISTAL_PERDU.copy() if SPRITE_CRISTAL_PERDU else None

    def get_etat(self):
        """Pour l'envoi réseau."""
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'id_joueur': self.id_joueur,
            'argent': self.argent,
        }

    def set_etat(self, data):
        """Pour la réception réseau."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.id_joueur = data['id_joueur']
        self.argent = data.get('argent', self.argent)

    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=None, argent_max=None):
        """Dessine le cristal perdu avec halo violet. Rétrécit selon l'argent restant."""
        off_x, off_y = camera_offset
        cx = self.rect.x + self.rect.width // 2 - off_x
        cy = self.rect.y + self.rect.height // 2 - off_y

        if temps_ms is None:
            temps_ms = pygame.time.get_ticks()
        pulse = 0.7 + 0.3 * math.sin(temps_ms / 600 + self.phase)
        r, g, b = self.couleur

        # Ratio de remplissage (1.0 = plein, 0.0 = vide)
        if argent_max and argent_max > 0:
            ratio = max(0.15, self.argent / argent_max)
        else:
            ratio = 1.0

        # Halo violet
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for rayon, alpha_base in [(26, 20), (18, 40), (11, 70)]:
            a = int(alpha_base * pulse * ratio)
            r_scaled = int(rayon * ratio)
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
            rect_visuel = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
            pygame.draw.ellipse(surface, self.couleur, rect_visuel)