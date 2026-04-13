# core/porte.py
# Porte interactive : ne s'ouvre qu'avec la clé.
# Bloque le passage physiquement tant qu'elle est fermée.
# Côté serveur : collision solide. Côté client : rendu animé.

import pygame
import math
import os
import sys
from parametres import TAILLE_TUILE, COULEUR_CYAN, COULEUR_CYAN_SOMBRE, COULEUR_TEXTE_SOMBRE


class Porte:
    """
    Porte qui bloque le passage jusqu'à ce qu'un joueur portant la clé
    interagisse avec elle (contact direct).

    Dimensions : 2 tuiles de large × 3 tuiles de haut (64×96 px).
    """

    LARGEUR  = TAILLE_TUILE * 2   # 64 px
    HAUTEUR  = TAILLE_TUILE * 3   # 96 px

    # Durée de l'animation d'ouverture en ms
    DUREE_OUVERTURE = 800

    def __init__(self, x: int, y: int):
        """
        x, y : coin supérieur gauche en pixels (coordonnées monde).
        """
        self.x = x
        self.y = y

        # Hitbox physique (utilisée pour la collision serveur)
        self.rect = pygame.Rect(x, y, self.LARGEUR, self.HAUTEUR)

        self.est_ouverte    = False
        self.en_ouverture   = False   # animation en cours
        self._debut_ouverture = 0     # timestamp ms

        # Offset vertical de la vantail pour l'animation (0 = fermé, HAUTEUR = ouvert)
        self._offset_anim = 0

        # Phase pour la lueur de la serrure
        self._phase_lueur = 0.0

    # ------------------------------------------------------------------
    #  LOGIQUE SERVEUR
    # ------------------------------------------------------------------

    def tenter_ouverture(self, joueur) -> bool:
        """
        Appelé par le serveur quand un joueur est en contact avec la porte.
        Retourne True si la porte vient de s'ouvrir.
        """
        if self.est_ouverte or self.en_ouverture:
            return False
        if not joueur.have_key:
            return False

        self.en_ouverture     = True
        self._debut_ouverture = pygame.time.get_ticks()
        joueur.have_key       = False   # la clé est consommée
        print(f"[PORTE] Ouverture déclenchée par joueur {joueur.id}")
        return True

    def mettre_a_jour(self, temps_ms: int):
        """Mise à jour de l'état (animation d'ouverture). Appelé chaque tick serveur."""
        if self.en_ouverture:
            elapsed = temps_ms - self._debut_ouverture
            ratio   = min(1.0, elapsed / self.DUREE_OUVERTURE)
            self._offset_anim = int(ratio * self.HAUTEUR)

            if ratio >= 1.0:
                # Ouverture terminée → supprimer la hitbox physique
                self.en_ouverture = False
                self.est_ouverte  = True
                self.rect.height  = 0   # plus de collision

    @property
    def rect_collision(self) -> pygame.Rect:
        """Rect utilisé pour les collisions physiques (vide si ouverte)."""
        if self.est_ouverte:
            return pygame.Rect(self.x, self.y, 0, 0)
        if self.en_ouverture:
            # La partie non encore montée reste solide
            hauteur_restante = self.HAUTEUR - self._offset_anim
            return pygame.Rect(self.x, self.y + self._offset_anim,
                               self.LARGEUR, hauteur_restante)
        return pygame.Rect(self.x, self.y, self.LARGEUR, self.HAUTEUR)

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self) -> dict:
        return {
            'x':            self.x,
            'y':            self.y,
            'est_ouverte':  self.est_ouverte,
            'en_ouverture': self.en_ouverture,
            'offset_anim':  self._offset_anim,
        }

    def set_etat(self, data: dict):
        self.x             = data['x']
        self.y             = data['y']
        self.est_ouverte   = data['est_ouverte']
        self.en_ouverture  = data['en_ouverture']
        self._offset_anim  = data['offset_anim']

    # ------------------------------------------------------------------
    #  RENDU CLIENT
    # ------------------------------------------------------------------

    def dessiner(self, surface: pygame.Surface, camera_offset=(0, 0), temps_ms: int = 0):
        """Dessine la porte avec animation et lueur."""
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        if self.est_ouverte and not self.en_ouverture:
            # Porte complètement ouverte : juste un petit halo résiduel au sol
            halo = pygame.Surface((self.LARGEUR + 16, 12), pygame.SRCALPHA)
            t = temps_ms / 1200
            a = int(30 + 20 * math.sin(t))
            pygame.draw.ellipse(halo, (0, 212, 255, a),
                                pygame.Rect(0, 0, self.LARGEUR + 16, 12))
            surface.blit(halo, (sx - 8, sy + self.HAUTEUR - 6))
            return

        # --- Cadre de la porte (toujours dessiné) ---
        epaisseur_cadre = 6
        couleur_cadre   = (60, 40, 120)
        couleur_bord    = (100, 60, 180)

        # Montants gauche et droit
        pygame.draw.rect(surface, couleur_cadre,
                         pygame.Rect(sx, sy, epaisseur_cadre, self.HAUTEUR))
        pygame.draw.rect(surface, couleur_cadre,
                         pygame.Rect(sx + self.LARGEUR - epaisseur_cadre, sy,
                                     epaisseur_cadre, self.HAUTEUR))
        # Linteau
        pygame.draw.rect(surface, couleur_cadre,
                         pygame.Rect(sx, sy, self.LARGEUR, epaisseur_cadre))

        # --- Vantail (la partie qui monte) ---
        vantail_y  = sy - self._offset_anim
        vantail_h  = self.HAUTEUR - self._offset_anim
        if vantail_h > 0:
            vantail_rect = pygame.Rect(sx + epaisseur_cadre, vantail_y,
                                       self.LARGEUR - epaisseur_cadre * 2, vantail_h)
            # Fond du vantail
            pygame.draw.rect(surface, (30, 15, 60), vantail_rect, border_radius=3)

            # Détails — deux panneaux
            marge = 6
            w_panneau = vantail_rect.width // 2 - marge * 2
            for col in range(2):
                px = vantail_rect.x + marge + col * (w_panneau + marge * 2)
                py = vantail_rect.y + marge
                ph = min(vantail_rect.height - marge * 2, 36)
                if ph > 4:
                    pygame.draw.rect(surface, (50, 25, 90),
                                     pygame.Rect(px, py, w_panneau, ph),
                                     border_radius=2)
                    pygame.draw.rect(surface, (80, 40, 140),
                                     pygame.Rect(px, py, w_panneau, ph),
                                     width=1, border_radius=2)

            # Serrure (si fermée et non en cours d'ouverture)
            if not self.en_ouverture:
                self._dessiner_serrure(surface, sx + self.LARGEUR // 2,
                                       sy + self.HAUTEUR // 2, temps_ms)

        # --- Bords lumineux du cadre ---
        pygame.draw.rect(surface, couleur_bord,
                         pygame.Rect(sx, sy, epaisseur_cadre, self.HAUTEUR), width=1)
        pygame.draw.rect(surface, couleur_bord,
                         pygame.Rect(sx + self.LARGEUR - epaisseur_cadre, sy,
                                     epaisseur_cadre, self.HAUTEUR), width=1)
        pygame.draw.rect(surface, couleur_bord,
                         pygame.Rect(sx, sy, self.LARGEUR, epaisseur_cadre), width=1)

    def _dessiner_serrure(self, surface, cx, cy, temps_ms):
        """Petite serrure avec lueur pulsante."""
        pulse = 0.5 + 0.5 * math.sin(temps_ms / 800)

        # Halo doré
        halo = pygame.Surface((32, 32), pygame.SRCALPHA)
        a = int(80 * pulse)
        pygame.draw.circle(halo, (255, 200, 50, a), (16, 16), 14)
        surface.blit(halo, (cx - 16, cy - 16))

        # Corps de la serrure (trou de serrure stylisé)
        pygame.draw.circle(surface, (200, 160, 40), (cx, cy - 2), 5)
        pygame.draw.rect(surface, (200, 160, 40),
                         pygame.Rect(cx - 3, cy + 2, 6, 7), border_radius=1)

        # Indicateur "Clé requise"
        police = pygame.font.Font(None, 16)
        txt = police.render("🔑", True, (255, 215, 0))
        surface.blit(txt, (cx - txt.get_width() // 2, cy + 12))