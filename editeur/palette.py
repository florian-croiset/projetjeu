# palette.py
# Panneau latéral droit affichant toutes les tuiles disponibles + une "gomme"
# (gid 0). Scrollable verticalement à la molette quand le curseur est dessus.

import pygame
from parametres import (
    COULEUR_FOND_PANEL, COULEUR_CYAN, COULEUR_CYAN_SOMBRE,
    COULEUR_TEXTE, COULEUR_TEXTE_SOMBRE,
)


class Palette:
    """Grille cliquable des tuiles du tileset.

    L'entrée d'index 0 est la "gomme" (gid 0). Les suivantes correspondent aux
    gids du tileset (firstgid .. firstgid + nb_tuiles - 1).
    """

    def __init__(self, cache_tuiles, donnees_tmx, rect, police):
        self.cache = cache_tuiles
        self.donnees = donnees_tmx
        self.rect = pygame.Rect(rect)
        self.police = police

        # Construit la liste des entrées : [0 (gomme), firstgid, firstgid+1, ...]
        firstgid = donnees_tmx['tileset_firstgid']
        nb = donnees_tmx['tileset_nb_tuiles']
        self.entrees = [0] + [firstgid + i for i in range(nb)]

        # Mise en page
        self.taille_case = 48      # taille d'une vignette
        self.padding = 6
        self.entete_h = 40         # zone titre en haut
        self.scroll_y = 0
        self._calculer_grille()

    # ------------------------------------------------------------------
    def _calculer_grille(self):
        largeur_dispo = self.rect.width - 2 * self.padding
        self.colonnes = max(1, largeur_dispo // (self.taille_case + self.padding))
        lignes_total = (len(self.entrees) + self.colonnes - 1) // self.colonnes
        self.hauteur_contenu = lignes_total * (self.taille_case + self.padding) + self.padding

    def _zone_grille(self):
        """Rect de la zone scrollable où sont affichées les vignettes."""
        return pygame.Rect(
            self.rect.x,
            self.rect.y + self.entete_h,
            self.rect.width,
            self.rect.height - self.entete_h,
        )

    def _index_position(self, index):
        """Position (x, y) à l'écran de la vignette d'index donné, avec scroll appliqué."""
        col = index % self.colonnes
        ligne = index // self.colonnes
        x = self.rect.x + self.padding + col * (self.taille_case + self.padding)
        y = (self.rect.y + self.entete_h + self.padding
             + ligne * (self.taille_case + self.padding)
             - self.scroll_y)
        return (x, y)

    # ------------------------------------------------------------------
    def gerer_scroll(self, event):
        """Si la molette tourne au-dessus du panneau, ajuste le scroll. Retourne True si consommé."""
        if event.type != pygame.MOUSEWHEEL:
            return False
        pos = pygame.mouse.get_pos()
        if not self.rect.collidepoint(pos):
            return False
        self.scroll_y -= event.y * 60
        scroll_max = max(0, self.hauteur_contenu - (self.rect.height - self.entete_h))
        self.scroll_y = max(0, min(self.scroll_y, scroll_max))
        return True

    def gid_a_la_position(self, pos):
        """Retourne le gid correspondant à la vignette sous la position, ou None."""
        if not self._zone_grille().collidepoint(pos):
            return None
        for i in range(len(self.entrees)):
            x, y = self._index_position(i)
            r = pygame.Rect(x, y, self.taille_case, self.taille_case)
            if r.collidepoint(pos):
                return self.entrees[i]
        return None

    # ------------------------------------------------------------------
    def dessiner(self, surface, gid_actif):
        # Fond du panneau
        pygame.draw.rect(surface, COULEUR_FOND_PANEL, self.rect)
        pygame.draw.line(
            surface, COULEUR_CYAN_SOMBRE,
            (self.rect.x, self.rect.y),
            (self.rect.x, self.rect.bottom), 1,
        )

        # Titre
        titre = self.police.render("Tuiles", True, COULEUR_CYAN)
        surface.blit(titre, (self.rect.x + 12, self.rect.y + 10))
        sous = self.police.render(f"gid : {gid_actif}", True, COULEUR_TEXTE_SOMBRE)
        surface.blit(sous, (self.rect.x + 90, self.rect.y + 12))

        # Vignettes — clip sur la zone scrollable
        zone = self._zone_grille()
        surface.set_clip(zone)

        for i, gid in enumerate(self.entrees):
            x, y = self._index_position(i)
            # Culling vertical
            if y + self.taille_case < zone.top or y > zone.bottom:
                continue

            r = pygame.Rect(x, y, self.taille_case, self.taille_case)

            # Fond de la case
            pygame.draw.rect(surface, (20, 18, 40), r)

            if gid == 0:
                # Gomme : croix rouge
                pygame.draw.line(surface, (200, 60, 60),
                                 (r.left + 8, r.top + 8),
                                 (r.right - 8, r.bottom - 8), 3)
                pygame.draw.line(surface, (200, 60, 60),
                                 (r.right - 8, r.top + 8),
                                 (r.left + 8, r.bottom - 8), 3)
                lib = self.police.render("∅", True, COULEUR_TEXTE)
                surface.blit(lib, (r.centerx - lib.get_width() // 2, r.bottom - 14))
            else:
                surf = self.cache.get(gid)
                if surf is not None:
                    sz = pygame.transform.scale(surf, (self.taille_case - 4, self.taille_case - 4))
                    surface.blit(sz, (r.x + 2, r.y + 2))

            # Bordure (épaisse + cyan si sélectionné)
            if gid == gid_actif:
                pygame.draw.rect(surface, COULEUR_CYAN, r, 3)
            else:
                pygame.draw.rect(surface, (50, 55, 80), r, 1)

        surface.set_clip(None)
