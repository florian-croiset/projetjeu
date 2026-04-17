# slider.py
# Slider horizontal dans la charte graphique Echo (cyan néon, glow au survol).

import pygame
from parametres import (COULEUR_CYAN, COULEUR_CYAN_CLAIR, COULEUR_CYAN_SOMBRE,
                        COULEUR_TEXTE, COULEUR_BOUTON)


class Slider:
    def __init__(self, x, y, largeur, hauteur, valeur=0.5, police=None):
        self.rect = pygame.Rect(x, y, largeur, hauteur)
        self.valeur = max(0.0, min(1.0, float(valeur)))
        self.police = police
        self.est_survole = False
        self._drag = False

    # ------------------------------------------------------------------
    def _rayon_knob(self):
        return max(10, self.rect.height // 2 + 2)

    def _x_knob(self):
        return self.rect.x + int(self.valeur * self.rect.width)

    def _knob_rect(self):
        r = self._rayon_knob()
        return pygame.Rect(self._x_knob() - r, self.rect.centery - r, r * 2, r * 2)

    # ------------------------------------------------------------------
    def _valeur_depuis_x(self, x_souris):
        if self.rect.width <= 0:
            return 0.0
        rel = (x_souris - self.rect.x) / self.rect.width
        return max(0.0, min(1.0, rel))

    # ------------------------------------------------------------------
    def verifier_survol(self, pos_souris):
        zone = self.rect.inflate(0, self._rayon_knob() * 2)
        self.est_survole = zone.collidepoint(pos_souris) or self._knob_rect().collidepoint(pos_souris)

    def gerer_event(self, event):
        """Retourne True si la valeur a changé."""
        ancienne = self.valeur
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zone = self.rect.inflate(0, self._rayon_knob() * 2)
            if zone.collidepoint(event.pos) or self._knob_rect().collidepoint(event.pos):
                self._drag = True
                self.valeur = self._valeur_depuis_x(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            self.valeur = self._valeur_depuis_x(event.pos[0])
        return self.valeur != ancienne

    # ------------------------------------------------------------------
    def dessiner(self, surface):
        survole = self.est_survole or self._drag

        # --- Glow externe au survol ---
        if survole:
            r, g, b = COULEUR_CYAN
            glow = pygame.Surface((self.rect.width + 16, self.rect.height + 16),
                                  pygame.SRCALPHA)
            for i, alpha in enumerate([15, 30, 50]):
                marge = 8 - i * 2
                pygame.draw.rect(
                    glow, (r, g, b, alpha),
                    pygame.Rect(marge // 2, marge // 2,
                                self.rect.width + 8 - marge,
                                self.rect.height + 8 - marge),
                    border_radius=self.rect.height // 2 + marge
                )
            surface.blit(glow, (self.rect.x - 8, self.rect.y - 8))

        # --- Track (fond de la barre) ---
        pygame.draw.rect(surface, COULEUR_BOUTON, self.rect,
                         border_radius=self.rect.height // 2)
        pygame.draw.rect(surface, COULEUR_CYAN_SOMBRE, self.rect,
                         width=1, border_radius=self.rect.height // 2)

        # --- Portion remplie (gauche du knob) ---
        fill_w = max(0, self._x_knob() - self.rect.x)
        if fill_w > 0:
            rect_fill = pygame.Rect(self.rect.x, self.rect.y,
                                    fill_w, self.rect.height)
            pygame.draw.rect(surface, COULEUR_CYAN_SOMBRE, rect_fill,
                             border_radius=self.rect.height // 2)
            inner = rect_fill.inflate(-2, -2)
            if inner.width > 0:
                pygame.draw.rect(surface, COULEUR_CYAN, inner,
                                 border_radius=self.rect.height // 2)

        # --- Knob (pastille) ---
        rayon = self._rayon_knob()
        cx_knob = self._x_knob()
        cy_knob = self.rect.centery
        couleur_knob = COULEUR_CYAN_CLAIR if survole else COULEUR_CYAN
        pygame.draw.circle(surface, (8, 8, 20), (cx_knob, cy_knob), rayon)
        pygame.draw.circle(surface, couleur_knob, (cx_knob, cy_knob),
                           rayon, width=2)
        pygame.draw.circle(surface, couleur_knob, (cx_knob, cy_knob),
                           max(3, rayon - 5))

        # --- Label pourcentage, au-dessus du knob ---
        if self.police is not None:
            txt = f"{int(round(self.valeur * 100))} %"
            surf_txt = self.police.render(txt, True, COULEUR_TEXTE)
            rect_txt = surf_txt.get_rect(midbottom=(cx_knob, self.rect.y - 8))
            surface.blit(surf_txt, rect_txt)
