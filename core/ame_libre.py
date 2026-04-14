# ame_libre.py
# Âme libre : flotte sur la map, ramassable par simple contact avec le joueur.
# Contrairement à l'AmePerdue (liée à la mort d'un joueur), l'AmeLibe existe
# indépendamment et récompense l'exploration.

import pygame
import math
import os
import sys
from parametres import *


def _charger_sprite_cristal():
    """Charge assets/cristal_purifié.png redimensionné pour les âmes libres."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        chemin = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(chemin).convert_alpha()
        return pygame.transform.scale(img, (16, 24))
    except Exception as e:
        print(f'[AME_LIBRE] Sprite non trouvé : {e}')
        return None

SPRITE_CRISTAL_LIBRE = None  # Chargé à la première instanciation
_CACHE_HALOS_LIBRE = None    # Cache des halos pré-rendus (8 niveaux de pulse)

NB_NIVEAUX_HALO = 8


def _generer_halos_libre():
    """Pré-rend 8 variantes de halo pour les âmes libres."""
    r, g, b = COULEUR_AME_LIBRE
    halos = []
    for i in range(NB_NIVEAUX_HALO):
        pulse = 0.7 + 0.3 * (i / (NB_NIVEAUX_HALO - 1))
        halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        for rayon, alpha_base in [(28, 18), (20, 35), (13, 60)]:
            a = int(alpha_base * pulse)
            pygame.draw.ellipse(halo_surf, (r, g, b, a),
                                pygame.Rect(30 - rayon, 30 - rayon, rayon * 2, rayon * 2))
        halos.append(halo_surf)
    return halos


class AmeLibre:
    """
    Âme libre flottante placée sur la map.
    - Visible dès le début (pas besoin d'écho).
    - Ramassée par simple collision avec le joueur (pas besoin d'attaque).
    - Donne ARGENT_AME_LIBRE âmes au joueur qui la touche.
    - Animée : flottement vertical sinusoïdal + lueur pulsante.
    """

    _prochain_id = 0

    def __init__(self, x, y, valeur=None):
        self.id = AmeLibre._prochain_id
        AmeLibre._prochain_id += 1

        self.valeur = valeur if valeur is not None else ARGENT_AME_LIBRE

        # Hitbox de collecte (centrée sur la position)
        w, h = 14, 20
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        # Position de base pour l'animation de flottement
        self.x_base = float(x)
        self.y_base = float(y)

        # Phase d'animation propre à chaque âme (évite qu'elles bougent en sync)
        self.phase = (self.id * 1.37) % (2 * math.pi)

        self.couleur = COULEUR_AME_LIBRE
        self.est_ramassee = False

        global SPRITE_CRISTAL_LIBRE, _CACHE_HALOS_LIBRE
        if SPRITE_CRISTAL_LIBRE is None:
            SPRITE_CRISTAL_LIBRE = _charger_sprite_cristal()
        if _CACHE_HALOS_LIBRE is None:
            _CACHE_HALOS_LIBRE = _generer_halos_libre()
        self.sprite = SPRITE_CRISTAL_LIBRE

    # ------------------------------------------------------------------
    #  LOGIQUE (appelée par le serveur chaque frame)
    # ------------------------------------------------------------------

    def mettre_a_jour(self, temps_ms):
        """Mise à jour de l'animation de flottement."""
        # Flottement vertical : ±4 pixels sur 1.8 s
        offset_y = math.sin(temps_ms / 900 + self.phase) * 4.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

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
        }

    def set_etat(self, data):
        """Mise à jour côté client depuis les données réseau."""
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.valeur       = data.get('valeur', ARGENT_AME_LIBRE)

    # ------------------------------------------------------------------
    #  RENDU (appelé par le client)
    # ------------------------------------------------------------------

    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        """Dessine le cristal avec halo pulsant + sprite si disponible."""
        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        pulse = 0.7 + 0.3 * math.sin(temps_ms / 600 + self.phase)
        r, g, b = self.couleur

        # Halo externe pulsant (pré-rendu)
        idx_halo = int((pulse - 0.7) / 0.3 * (NB_NIVEAUX_HALO - 1))
        idx_halo = max(0, min(NB_NIVEAUX_HALO - 1, idx_halo))
        surface.blit(_CACHE_HALOS_LIBRE[idx_halo], (cx - 30, cy - 30))

        if self.sprite:
            # Légère variation d'alpha pour effet de pulsation
            alpha = int(180 + 75 * pulse)
            self.sprite.set_alpha(alpha)
            r_spr = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r_spr)
        else:
            # Fallback : ellipse colorée
            corps_surf = pygame.Surface((12, 18), pygame.SRCALPHA)
            pygame.draw.ellipse(corps_surf, (r, g, b, 220), pygame.Rect(0, 0, 12, 18))
            surface.blit(corps_surf, (cx - 6, cy - 9))