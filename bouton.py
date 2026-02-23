# bouton.py
# Classe Bouton avec le style visuel de la charte graphique Echo (Team Nightberry).
# Design : fond sombre, bordure cyan néon, effet glow au survol.

import pygame
from parametres import *


class Bouton:
    def __init__(self, x, y, largeur, hauteur, texte, police,
                 style="normal"):
        """
        style :
          "normal"   — bouton standard cyan/sombre
          "danger"   — bouton rouge (confirmation négative)
          "confirm"  — bouton violet (confirmation positive)
          "ghost"    — bouton transparent / désactivé
        """
        self.rect = pygame.Rect(x, y, largeur, hauteur)
        self.texte = texte
        self.police = police
        self.style = style
        self.est_survole = False

        # Couleurs par style
        self._definir_style(style)

    # ------------------------------------------------------------------
    def _definir_style(self, style):
        if style == "danger":
            self.couleur_fond        = (20, 5, 10)
            self.couleur_fond_survol = (40, 10, 20)
            self.couleur_bordure     = (220, 50, 50)
            self.couleur_bordure_survol = (255, 90, 90)
            self.couleur_texte       = (220, 50, 50)
            self.couleur_texte_survol = (255, 110, 110)

        elif style == "confirm":
            self.couleur_fond        = (14, 5, 35)
            self.couleur_fond_survol = (30, 10, 65)
            self.couleur_bordure     = COULEUR_VIOLET
            self.couleur_bordure_survol = COULEUR_VIOLET_CLAIR
            self.couleur_texte       = COULEUR_VIOLET_CLAIR
            self.couleur_texte_survol = COULEUR_BLANC

        elif style == "ghost":
            self.couleur_fond        = (0, 0, 0, 0)
            self.couleur_fond_survol = (14, 10, 35)
            self.couleur_bordure     = (40, 40, 70)
            self.couleur_bordure_survol = (80, 80, 110)
            self.couleur_texte       = COULEUR_TEXTE_SOMBRE
            self.couleur_texte_survol = COULEUR_TEXTE

        else:  # "normal" — style Echo par défaut
            self.couleur_fond        = COULEUR_BOUTON
            self.couleur_fond_survol = COULEUR_BOUTON_SURVOL
            self.couleur_bordure     = COULEUR_CYAN_SOMBRE
            self.couleur_bordure_survol = COULEUR_CYAN
            self.couleur_texte       = COULEUR_TEXTE
            self.couleur_texte_survol = COULEUR_CYAN

    # ------------------------------------------------------------------
    def dessiner(self, surface):
        """Dessine le bouton sur la surface avec l'effet néon Echo."""
        survole = self.est_survole

        fond     = self.couleur_fond_survol  if survole else self.couleur_fond
        bordure  = self.couleur_bordure_survol if survole else self.couleur_bordure
        texte_c  = self.couleur_texte_survol if survole else self.couleur_texte

        # ---- Glow externe (au survol) --------------------------------
        if survole and self.style not in ("ghost",):
            glow_surf = pygame.Surface(
                (self.rect.width + 16, self.rect.height + 16),
                pygame.SRCALPHA
            )
            r, g, b = bordure
            for i, alpha in enumerate([15, 30, 50]):
                marge = 8 - i * 2
                pygame.draw.rect(
                    glow_surf,
                    (r, g, b, alpha),
                    pygame.Rect(marge // 2, marge // 2,
                                self.rect.width + 8 - marge,
                                self.rect.height + 8 - marge),
                    border_radius=10 + marge
                )
            surface.blit(glow_surf, (self.rect.x - 8, self.rect.y - 8))

        # ---- Fond du bouton -----------------------------------------
        pygame.draw.rect(surface, fond, self.rect, border_radius=8)

        # ---- Bordure néon (1 px intérieur + 1 px extérieur) ----------
        pygame.draw.rect(surface, bordure, self.rect, width=1, border_radius=8)
        inner = self.rect.inflate(-2, -2)
        r, g, b = bordure
        pygame.draw.rect(surface, (r, g, b, 60),
                         inner, width=1, border_radius=7)

        # ---- Ligne de reflet haut (effet vitré) ----------------------
        if self.style != "ghost":
            reflet = pygame.Surface((self.rect.width - 4, 2), pygame.SRCALPHA)
            reflet.fill((255, 255, 255, 18))
            surface.blit(reflet, (self.rect.x + 2, self.rect.y + 3))

        # ---- Texte centré -------------------------------------------
        texte_surf = self.police.render(self.texte, True, texte_c)
        texte_rect = texte_surf.get_rect(center=self.rect.center)
        surface.blit(texte_surf, texte_rect)

    # ------------------------------------------------------------------
    def verifier_clic(self, event):
        """Retourne True si le bouton a été cliqué (clic gauche)."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def verifier_survol(self, pos_souris):
        """Met à jour l'état est_survole."""
        self.est_survole = self.rect.collidepoint(pos_souris)