# ui/effets_visuels.py
# Fonctions utilitaires de dessin pour l'interface Echo.
# Extraites de client.py pour alléger le fichier principal.

import pygame
import math
from parametres import *


def dessiner_fond_echo(surface, largeur, hauteur, temps):
    """
    Fond animé style Echo :
    - dégradé vertical bleu-nuit
    - grille de particules subtile
    - lueur centrale pulsante
    """
    # 1. Fond de base dégradé vertical
    if FOND_MENU:
        for y in range(hauteur):
            ratio = y / hauteur
            r = int(8  + ratio * 4)
            g = int(8  + ratio * 2)
            b = int(20 + ratio * 15)
            pygame.draw.line(surface, (r, g, b), (0, y), (largeur, y))
    else:
        surface.fill((0, 0, 0))

    # 2. Grille en perspective (lignes horizontales fines)
    if HALOS_MENU:
        nb_lignes = 12
        grille_surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        for i in range(nb_lignes):
            ratio = (i + 1) / nb_lignes
            y_pos = int(hauteur * 0.55 + ratio * hauteur * 0.6)
            if y_pos >= hauteur:
                break
            alpha = int(12 + ratio * 25)
            epaisseur = 1 if ratio < 0.6 else 2
            pygame.draw.line(grille_surf, (0, 180, 255, alpha),
                            (0, y_pos), (largeur, y_pos), epaisseur)

        # Lignes verticales de la grille
        nb_v = 20
        for i in range(nb_v + 1):
            ratio_x = i / nb_v
            x_vanish = largeur // 2
            y_vanish = int(hauteur * 0.55)
            x_bas = int(ratio_x * largeur)
            alpha = int(8 + abs(ratio_x - 0.5) * 20)
            pygame.draw.line(grille_surf, (0, 150, 220, alpha),
                            (x_vanish, y_vanish), (x_bas, hauteur), 1)
        surface.blit(grille_surf, (0, 0))

    # 3. Lueur centrale pulsante (cyan)
    if HALOS_MENU:
        pulse = 0.75 + 0.25 * math.sin(temps / 1200)
        glow_surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        cx, cy = largeur // 2, int(hauteur * 0.38)
        for rayon, alpha_base in [(420, 18), (280, 30), (150, 45), (70, 25)]:
            a = int(alpha_base * pulse)
            pygame.draw.circle(glow_surf, (0, 180, 255, a), (cx, cy), rayon)
        surface.blit(glow_surf, (0, 0))


def dessiner_separateur_neon(surface, x1, y, x2, couleur=None, alpha=180):
    """Ligne séparatrice style néon avec dégradé de transparence."""
    if couleur is None:
        couleur = COULEUR_CYAN
    sep_surf = pygame.Surface((x2 - x1, 2), pygame.SRCALPHA)
    r, g, b = couleur
    largeur = x2 - x1
    for px in range(largeur):
        ratio = px / largeur
        dist_centre = abs(ratio - 0.5) * 2   # 0 au centre, 1 aux bords
        a = int(alpha * (1 - dist_centre ** 1.5))
        sep_surf.set_at((px, 0), (r, g, b, a))
        sep_surf.set_at((px, 1), (r, g, b, a // 3))
    surface.blit(sep_surf, (x1, y))


def dessiner_titre_neon(surface, police, texte, cx, cy, couleur_neon=None):
    """Titre avec effet de lueur néon multicouche."""
    if couleur_neon is None:
        couleur_neon = COULEUR_CYAN
    r, g, b = couleur_neon

    # Couches de glow (de la plus grande à la plus petite)
    for decal, alpha in [(6, 15), (4, 25), (2, 40)]:
        for dx in (-decal, 0, decal):
            for dy in (-decal, 0, decal):
                if dx == 0 and dy == 0:
                    continue
                glow = police.render(texte, True, (r, g, b))
                glow.set_alpha(alpha)
                rect = glow.get_rect(center=(cx + dx, cy + dy))
                surface.blit(glow, rect)

    # Texte principal
    surf = police.render(texte, True, couleur_neon)
    rect = surf.get_rect(center=(cx, cy))
    surface.blit(surf, rect)


def dessiner_panneau(surface, rect, couleur_bordure=None, alpha_fond=220):
    """Panneau semi-transparent avec bordure néon et coin biseautés."""
    if couleur_bordure is None:
        couleur_bordure = COULEUR_CYAN_SOMBRE

    # Fond
    fond_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    r_fond = (COULEUR_FOND_PANEL[0], COULEUR_FOND_PANEL[1], COULEUR_FOND_PANEL[2], alpha_fond)
    pygame.draw.rect(fond_surf, r_fond,
                    pygame.Rect(0, 0, rect.width, rect.height),
                    border_radius=12)
    surface.blit(fond_surf, rect.topleft)

    # Bordure extérieure
    pygame.draw.rect(surface, couleur_bordure, rect, width=1, border_radius=12)

    # Reflet du haut (ligne lumineuse)
    reflet = pygame.Surface((rect.width - 20, 1), pygame.SRCALPHA)
    for px in range(rect.width - 20):
        ratio = px / (rect.width - 20)
        dist = abs(ratio - 0.5) * 2
        a = int(50 * (1 - dist ** 2))
        reflet.set_at((px, 0), (200, 230, 255, a))
    surface.blit(reflet, (rect.x + 10, rect.y + 8))
