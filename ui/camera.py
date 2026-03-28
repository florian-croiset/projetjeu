# ui/camera.py
# Gestion de la caméra (offset, zoom) et du masque de halo précalculé.
# Extraits de client.py pour séparation des responsabilités.

import pygame
from parametres import *


def calculer_camera(rect_cible, largeur_ecran, hauteur_ecran, zoom,
                    largeur_monde, hauteur_monde):
    """Calcule l'offset de la caméra centrée sur rect_cible."""
    largeur_vue = largeur_ecran / zoom
    hauteur_vue = hauteur_ecran / zoom
    offset_x = rect_cible.centerx - (largeur_vue / 2)
    offset_y = rect_cible.centery - (hauteur_vue / 2)
    offset_x = max(0, offset_x)
    offset_y = max(0, offset_y)
    offset_x = min(offset_x, largeur_monde - largeur_vue)
    offset_y = min(offset_y, hauteur_monde - hauteur_vue)
    return int(offset_x), int(offset_y)


def creer_masque_halo(rayon, etendue, alpha_max=220):
    """
    Précalcule une surface circulaire avec dégradé linéaire d'obscurité.
    À blitter avec BLEND_RGBA_MIN sur le calque d'obscurité chaque frame.

    rayon     : rayon total du halo (pixels)
    etendue   : largeur de la zone de dégradé depuis le bord vers le centre
                (etendue == rayon → dégradé sur tout le rayon, centre transparent)
    alpha_max : niveau maximal d'obscurité (0–255)
    """
    diameter = rayon * 2 + 2
    centre   = rayon + 1
    surf     = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    depart   = max(0, rayon - int(etendue))   # début du dégradé depuis le centre

    if HALO_NB_NIVEAUX == 0:
        # Dégradé parfait pixel par pixel via numpy
        try:
            import numpy as np
            x_idx, y_idx = np.ogrid[:diameter, :diameter]
            dist  = np.sqrt((x_idx - centre) ** 2 + (y_idx - centre) ** 2)
            alpha = np.clip(
                (dist - depart) / max(1, etendue) * alpha_max,
                0, alpha_max
            ).astype(np.uint8)

            arr_a        = pygame.surfarray.pixels_alpha(surf)
            arr_a[:]     = alpha
            del arr_a

            arr_rgb      = pygame.surfarray.pixels3d(surf)
            arr_rgb[:, :] = (0, 0, 10)
            del arr_rgb

            return surf
        except (ImportError, pygame.error):
            print("[HALO] numpy indisponible — fallback couches discrètes")

    # Fallback ou mode discret (HALO_NB_NIVEAUX > 0)
    nb = HALO_NB_NIVEAUX if HALO_NB_NIVEAUX > 0 else max(32, rayon)
    surf.fill((0, 0, 10, alpha_max))             # tout sombre par défaut
    for i in range(nb, -1, -1):                  # du plus grand cercle au plus petit
        r = depart + int(etendue * i / nb)
        a = int(alpha_max * i / nb)
        pygame.draw.circle(surf, (0, 0, 10, a), (centre, centre), r)

    return surf
