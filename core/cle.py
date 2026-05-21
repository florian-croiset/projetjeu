# cle.py
# Objet clé ramassable sur la map. Ramassé par simple contact.
# Lorsque ramassée, HAVE_KEY passe à True côté joueur.

import pygame
import math
import os
import sys
from parametres import *


class Cle:
    """
    Clé ramassable placée une fois sur la map.
    - Ramassée par contact joueur.
    - Donne HAVE_KEY = True au joueur qui la touche.
    - Animée : flottement vertical.
    - Dessinée entièrement en pygame (pas de sprite externe).
    """

    def __init__(self, x, y):
        self.rect = pygame.Rect(x - 10, y - 14, 20, 28)
        self.x_base = float(x)
        self.y_base = float(y)
        self.est_ramassee = False
        self.couleur        = (255, 215, 0)    # or vif
        self.couleur_sombre = (180, 140, 0)    # contour
        self.couleur_trou   = (30, 20, 0)      # trous de la clé

    # ------------------------------------------------------------------
    def mettre_a_jour(self, temps_ms):
        """Animation de flottement (appelée côté client uniquement)."""
        offset_y = math.sin(temps_ms / 800) * 4.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    # ------------------------------------------------------------------
    def get_etat(self):
        return {
            'x': int(self.x_base),
            'y': int(self.y_base),
            'est_ramassee': self.est_ramassee,
        }

    def set_etat(self, data):
        self.x_base       = float(data['x'])
        self.y_base       = float(data['y'])
        self.rect.centerx = int(self.x_base)
        self.rect.centery = int(self.y_base)
        self.est_ramassee  = data.get('est_ramassee', False)

    # ------------------------------------------------------------------
    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        if self.est_ramassee:
            return

        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        # ── Halo doré pulsant (surface réutilisée) ────────────────────
        pulse = 0.6 + 0.4 * math.sin(temps_ms / 500)
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((48, 48), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for r_h, a_h in [(22, 15), (15, 35), (9, 60)]:
            pygame.draw.ellipse(self._halo_surf, (255, 215, 0, int(a_h * pulse)),
                                pygame.Rect(24 - r_h, 24 - r_h, r_h * 2, r_h * 2))
        surface.blit(self._halo_surf, (cx - 24, cy - 24))

        # ── Dessin de la clé ───────────────────────────────────────────
        # La clé est orientée verticalement :
        # - anneau (tête) en haut
        # - tige vers le bas avec deux dents à droite

        # Anneau de la clé (cercle creux)
        anneau_cx = cx
        anneau_cy = cy - 8
        anneau_r  = 7

        pygame.draw.circle(surface, self.couleur,        (anneau_cx, anneau_cy), anneau_r)
        pygame.draw.circle(surface, self.couleur_sombre, (anneau_cx, anneau_cy), anneau_r, 2)
        # Trou central de l'anneau
        pygame.draw.circle(surface, self.couleur_trou,   (anneau_cx, anneau_cy), 3)

        # Tige verticale
        tige_x  = cx - 2
        tige_y  = anneau_cy + anneau_r - 1   # part du bas de l'anneau
        tige_w  = 4
        tige_h  = 16

        pygame.draw.rect(surface, self.couleur,
                         pygame.Rect(tige_x, tige_y, tige_w, tige_h))
        pygame.draw.rect(surface, self.couleur_sombre,
                         pygame.Rect(tige_x, tige_y, tige_w, tige_h), 1)

        # Dent 1 (plus haute, plus longue)
        dent1_x = tige_x + tige_w
        dent1_y = tige_y + 4
        dent1_w = 5
        dent1_h = 3

        pygame.draw.rect(surface, self.couleur,
                         pygame.Rect(dent1_x, dent1_y, dent1_w, dent1_h))
        pygame.draw.rect(surface, self.couleur_sombre,
                         pygame.Rect(dent1_x, dent1_y, dent1_w, dent1_h), 1)

        # Dent 2 (plus basse, plus courte)
        dent2_x = tige_x + tige_w
        dent2_y = tige_y + 9
        dent2_w = 3
        dent2_h = 3

        pygame.draw.rect(surface, self.couleur,
                         pygame.Rect(dent2_x, dent2_y, dent2_w, dent2_h))
        pygame.draw.rect(surface, self.couleur_sombre,
                         pygame.Rect(dent2_x, dent2_y, dent2_w, dent2_h), 1)