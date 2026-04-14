# ame_loot.py
# Âme de loot : jaillit d'un ennemi tué, se disperse avec physique,
# puis se pose au sol. Le joueur doit marcher dessus pour la ramasser.
# Inspiré du système de geo de Hollow Knight.

import pygame
import math
import random
import os
import sys
from parametres import *


def _charger_sprite_loot():
    """Charge le sprite cristal redimensionné pour les âmes de loot."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        chemin = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(chemin).convert_alpha()
        return pygame.transform.scale(img, (10, 15))
    except Exception as e:
        print(f'[AME_LOOT] Sprite non trouvé : {e}')
        return None


SPRITE_LOOT = None  # Chargé à la première instanciation
_CACHE_HALOS_LOOT = None
NB_NIVEAUX_HALO = 8


def _generer_halos_loot():
    """Pré-rend 8 variantes de halo pour les âmes de loot."""
    r, g, b = COULEUR_AME_LOOT
    halos = []
    for i in range(NB_NIVEAUX_HALO):
        pulse = 0.7 + 0.3 * (i / (NB_NIVEAUX_HALO - 1))
        halo_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
        for rayon, alpha_base in [(18, 15), (13, 30), (8, 50)]:
            a = int(alpha_base * pulse)
            pygame.draw.ellipse(halo_surf, (r, g, b, a),
                                pygame.Rect(20 - rayon, 20 - rayon, rayon * 2, rayon * 2))
        halos.append(halo_surf)
    return halos


class AmeLoot:
    """
    Âme de loot lâchée par un ennemi tué.
    - Phase 'dispersion' : jaillit avec vélocité aléatoire, gravité, rebonds.
    - Phase 'repos' : flotte doucement (sinusoïde), ramassable par contact.
    - Disparaît après DUREE_VIE_AME_LOOT ms une fois posée.
    """

    _prochain_id = 0

    def __init__(self, x, y, valeur=1):
        self.id = AmeLoot._prochain_id
        AmeLoot._prochain_id += 1

        self.valeur = valeur

        # Hitbox (plus petite que AmeLibre)
        w, h = 10, 14
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        # Position de base (utilisée en phase repos)
        self.x_base = float(x)
        self.y_base = float(y)

        # Physique de dispersion
        self.vel_x = random.uniform(-VITESSE_BURST_LOOT, VITESSE_BURST_LOOT)
        self.vel_y = random.uniform(-VITESSE_BURST_LOOT, -VITESSE_BURST_LOOT * 0.3)

        # État
        self.phase = 'dispersion'
        self.temps_creation = 0      # mis à jour par le serveur au spawn
        self.temps_repos = None
        self.sur_le_sol = False

        # Animation
        self.phase_anim = (self.id * 0.91) % (2 * math.pi)
        self.couleur = COULEUR_AME_LOOT

        global SPRITE_LOOT, _CACHE_HALOS_LOOT
        if SPRITE_LOOT is None:
            SPRITE_LOOT = _charger_sprite_loot()
        if _CACHE_HALOS_LOOT is None:
            _CACHE_HALOS_LOOT = _generer_halos_loot()
        self.sprite = SPRITE_LOOT

    # ------------------------------------------------------------------
    #  LOGIQUE (appelée par le serveur chaque frame)
    # ------------------------------------------------------------------

    def mettre_a_jour(self, temps_ms, rects_collision):
        """Met à jour la physique ou l'animation selon la phase."""
        if self.phase == 'dispersion':
            self._mettre_a_jour_dispersion(temps_ms, rects_collision)
        else:
            self._mettre_a_jour_repos(temps_ms)

    def _mettre_a_jour_dispersion(self, temps_ms, rects_collision):
        """Physique : gravité, mouvement, rebonds sur murs/sol."""
        # Gravité
        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10

        dx = self.vel_x
        dy = self.vel_y

        # Collision X
        self.rect.x += int(dx)
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                elif dx < 0:
                    self.rect.left = mur.right
                self.vel_x *= -REBOND_AMORTISSEMENT

        # Collision Y
        self.sur_le_sol = False
        self.rect.y += int(dy)
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dy > 0:
                    self.rect.bottom = mur.top
                    self.sur_le_sol = True
                    self.vel_x *= 0.5  # Friction au sol
                elif dy < 0:
                    self.rect.top = mur.bottom
                self.vel_y *= -REBOND_AMORTISSEMENT

        # Transition vers repos ?
        vitesse = abs(self.vel_x) + abs(self.vel_y)
        temps_ecoule = temps_ms - self.temps_creation
        if (vitesse < SEUIL_REPOS_LOOT and self.sur_le_sol) or temps_ecoule > DUREE_MAX_DISPERSION:
            self.phase = 'repos'
            self.x_base = float(self.rect.centerx)
            self.y_base = float(self.rect.centery)
            self.temps_repos = temps_ms
            self.vel_x = 0
            self.vel_y = 0

    def _mettre_a_jour_repos(self, temps_ms):
        """Flottement sinusoïdal identique à AmeLibre."""
        offset_y = math.sin(temps_ms / 900 + self.phase_anim) * 3.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    def est_expiree(self, temps_ms):
        """True si l'orbe est posée depuis trop longtemps."""
        if self.phase != 'repos' or self.temps_repos is None:
            return False
        return temps_ms - self.temps_repos > DUREE_VIE_AME_LOOT

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self):
        """Sérialisation pour envoi au(x) client(s)."""
        return {
            'id':     self.id,
            'x':      self.rect.centerx,
            'y':      self.rect.centery,
            'valeur': self.valeur,
            'phase':  self.phase,
        }

    def set_etat(self, data):
        """Mise à jour côté client depuis les données réseau."""
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.valeur = data.get('valeur', 1)
        self.phase = data.get('phase', 'repos')

    # ------------------------------------------------------------------
    #  RENDU (appelé par le client)
    # ------------------------------------------------------------------

    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        """Dessine l'orbe avec halo pulsant + sprite."""
        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        pulse = 0.7 + 0.3 * math.sin(temps_ms / 600 + self.phase_anim)
        r, g, b = self.couleur

        # Halo (pré-rendu)
        idx_halo = int((pulse - 0.7) / 0.3 * (NB_NIVEAUX_HALO - 1))
        idx_halo = max(0, min(NB_NIVEAUX_HALO - 1, idx_halo))
        surface.blit(_CACHE_HALOS_LOOT[idx_halo], (cx - 20, cy - 20))

        if self.sprite:
            alpha = int(180 + 75 * pulse)
            self.sprite.set_alpha(alpha)
            r_spr = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r_spr)
        else:
            # Fallback : petit cercle
            pygame.draw.circle(surface, self.couleur, (cx, cy), 5)
