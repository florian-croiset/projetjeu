# core/orbe_capacite.py
# Orbes à usage unique qui débloquent définitivement une capacité (dash ou double saut).
# Ramassé par contact avec le joueur. Persiste dans la sauvegarde via ameliorations.

import pygame
import math
import os
import sys
from parametres import TAILLE_TUILE, COULEUR_VIOLET, COULEUR_VIOLET_CLAIR, COULEUR_CYAN


# Couleurs et icônes par type de capacité
_CONFIG_CAPACITES = {
    'double_saut': {
        'couleur':  (80, 160, 255),    # Bleu ciel
        'couleur2': (120, 200, 255),
        'icone':    '⬆',
        'nom':      'Double Saut',
    },
    'dash': {
        'couleur':  (180, 80, 255),    # Violet
        'couleur2': (220, 140, 255),
        'icone':    '»',
        'nom':      'Dash',
    },
}


class OrbeCapacite:
    """
    Orbe flottant qui débloque une capacité au contact du joueur.
    Usage unique (disparaît une fois ramassé).
    """

    RAYON = 14   # rayon de la hitbox de collecte (pixels)

    _prochain_id = 0

    def __init__(self, x: int, y: int, capacite: str):
        """
        x, y      : centre de l'orbe en pixels (coordonnées monde).
        capacite  : 'double_saut' ou 'dash'.
        """
        self.id       = OrbeCapacite._prochain_id
        OrbeCapacite._prochain_id += 1

        self.x_base   = float(x)
        self.y_base   = float(y)
        self.capacite = capacite
        self.phase    = (self.id * 1.57) % (2 * math.pi)

        cfg = _CONFIG_CAPACITES.get(capacite, _CONFIG_CAPACITES['dash'])
        self.couleur  = cfg['couleur']
        self.couleur2 = cfg['couleur2']
        self.icone    = cfg['icone']
        self.nom      = cfg['nom']

        # Rect de collecte
        self.rect = pygame.Rect(x - self.RAYON, y - self.RAYON,
                                self.RAYON * 2, self.RAYON * 2)

        self.est_ramasse = False

    # ------------------------------------------------------------------
    #  LOGIQUE SERVEUR
    # ------------------------------------------------------------------

    def mettre_a_jour(self, temps_ms: int):
        """Animation de flottement."""
        offset_y = math.sin(temps_ms / 700 + self.phase) * 5.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    def tenter_collecte(self, joueur) -> bool:
        """
        Appelé par le serveur au contact d'un joueur.
        Retourne True si la capacité a été débloquée.
        """
        if self.est_ramasse:
            return False

        # Ne donner que si le joueur n'a pas déjà la capacité
        if self.capacite == 'double_saut' and joueur.peut_double_saut:
            return False
        if self.capacite == 'dash' and joueur.peut_dash:
            return False

        self.est_ramasse = True

        if self.capacite == 'double_saut':
            joueur.peut_double_saut = True
            print(f"[ORBE] Joueur {joueur.id} débloque : Double Saut")
        elif self.capacite == 'dash':
            joueur.peut_dash = True
            print(f"[ORBE] Joueur {joueur.id} débloque : Dash")

        joueur.sons_a_jouer.append('ame_libre')   # Son de collecte
        return True

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self) -> dict:
        return {
            'id':          self.id,
            'x':           self.rect.centerx,
            'y':           self.rect.centery,
            'capacite':    self.capacite,
            'est_ramasse': self.est_ramasse,
        }

    def set_etat(self, data: dict):
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.capacite     = data['capacite']
        self.est_ramasse  = data['est_ramasse']

    # ------------------------------------------------------------------
    #  RENDU CLIENT
    # ------------------------------------------------------------------

    def dessiner(self, surface: pygame.Surface, camera_offset=(0, 0), temps_ms: int = 0):
        """Dessine l'orbe avec halo pulsant et icône."""
        if self.est_ramasse:
            return

        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        pulse = 0.65 + 0.35 * math.sin(temps_ms / 500 + self.phase)
        r, g, b = self.couleur
        r2, g2, b2 = self.couleur2

        # --- Halo externe ---
        halo_surf = pygame.Surface((70, 70), pygame.SRCALPHA)
        for rayon, alpha_base in [(32, 12), (24, 25), (16, 45)]:
            a = int(alpha_base * pulse)
            pygame.draw.circle(halo_surf, (r, g, b, a), (35, 35), rayon)
        surface.blit(halo_surf, (cx - 35, cy - 35))

        # --- Corps de l'orbe ---
        corps = pygame.Surface((self.RAYON * 2 + 4, self.RAYON * 2 + 4), pygame.SRCALPHA)
        # Cercle extérieur
        pygame.draw.circle(corps, (r, g, b, 200),
                           (self.RAYON + 2, self.RAYON + 2), self.RAYON)
        # Reflet interne
        pygame.draw.circle(corps, (r2, g2, b2, 160),
                           (self.RAYON + 2 - 3, self.RAYON + 2 - 3), self.RAYON - 4)
        # Bord lumineux
        pygame.draw.circle(corps, (r2, g2, b2, 220),
                           (self.RAYON + 2, self.RAYON + 2), self.RAYON, width=2)
        surface.blit(corps, (cx - self.RAYON - 2, cy - self.RAYON - 2))

        # --- Icône centrale ---
        police = pygame.font.Font(None, 20)
        icone_surf = police.render(self.icone, True, (255, 255, 255))
        icone_rect = icone_surf.get_rect(center=(cx, cy))
        surface.blit(icone_surf, icone_rect)

        # --- Étiquette au-dessus ---
        police_nom = pygame.font.Font(None, 16)
        nom_surf = police_nom.render(self.nom, True, (r2, g2, b2))
        nom_rect = nom_surf.get_rect(center=(cx, cy - self.RAYON - 10))
        # Fond semi-transparent
        bg = pygame.Surface((nom_rect.width + 8, nom_rect.height + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        surface.blit(bg, (nom_rect.x - 4, nom_rect.y - 2))
        surface.blit(nom_surf, nom_rect)