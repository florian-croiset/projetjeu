# ui/effets_visuels.py
# Fonctions utilitaires de dessin pour l'interface Echo.
# Extraites de client.py pour alléger le fichier principal.

import pygame
import math
import numpy as np
from parametres import *

# Cache global pour la distorsion d'écho : profil sinusoïdal précalculé
# Taille fixe pour tous les rayons possibles (jusqu'à 500px)
_DISTORTION_PROFIL_CACHE = None
_DISTORTION_PROFIL_CACHE_TAILLE = 512


def _generer_profil_distortion_cache():
    """Génère le cache global du profil sinusoïdal pour la distorsion."""
    global _DISTORTION_PROFIL_CACHE
    if _DISTORTION_PROFIL_CACHE is not None:
        return
    demi = DISTORTION_ECHO_EPAISSEUR_PX / 2.0
    amplitude_max = DISTORTION_ECHO_AMPLITUDE_PX
    epaisseur = DISTORTION_ECHO_EPAISSEUR_PX

    # Précacul du profil pour chaque distance possible
    # Le profil varie de 0 à pi, ce qui donne un demi-sinus
    profils = []
    for i in range(_DISTORTION_PROFIL_CACHE_TAILle):
        distance_norm = i / (_DISTORTION_PROFIL_CACHE_TAILle - 1) * 2 - 1  # -1 à 1
        # On want le profil sinusoïdal pour la zone d'impact
        # (dist - (rayon - demi)) / epaisseur * pi
        # Pour dist dans [rayon-demi, rayon+demi]
        value = (distance_norm * demi + demi) / epaisseur * np.pi
        profil = np.sin(np.clip(value, 0, np.pi))
        profils.append(profil)
    _DISTORTION_PROFIL_CACHE = np.array(profils, dtype=np.float32)


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


def appliquer_distortion_echo(surface, ondes, t_now):
    """
    Effet local de distortion radiale type "goutte d'eau" sur la surface.
    Mute `surface` in-place. L'appelant gère le cycle de vie de `ondes`
    (filtrage des ondes terminées avant l'appel).

    surface : pygame.Surface — surface_virtuelle (modifiée in-place)
    ondes   : liste de dicts {start_ms, sx, sy, rayon_max, duree_ms}
              avec sx/sy déjà convertis en coords écran virtuelles.
    t_now   : pygame.time.get_ticks() — timestamp courant en ms.
    """
    if not DISTORTION_ECHO_ACTIVE or not ondes:
        return

    try:
        import numpy as np
    except ImportError:
        return

    largeur, hauteur = surface.get_size()
    epaisseur     = DISTORTION_ECHO_EPAISSEUR_PX
    amplitude_max = DISTORTION_ECHO_AMPLITUDE_PX
    demi          = epaisseur / 2.0
    pad           = int(demi) + amplitude_max + 1

    try:
        pixels = pygame.surfarray.pixels3d(surface)   # vue mutable (W, H, 3)
    except (pygame.error, ValueError):
        return

    try:
        for onde in ondes:
            t = t_now - onde['start_ms']
            duree = onde['duree_ms']
            if t < 0 or t >= duree:
                continue

            ratio = t / duree
            rayon = onde['rayon_max'] * ratio
            fade  = 1.0 - ratio
            sx, sy = onde['sx'], onde['sy']

            x0 = max(0, int(sx - rayon - pad))
            y0 = max(0, int(sy - rayon - pad))
            x1 = min(largeur, int(sx + rayon + pad) + 1)
            y1 = min(hauteur, int(sy + rayon + pad) + 1)
            if x1 <= x0 or y1 <= y0:
                continue

            src_snap = pixels[x0:x1, y0:y1].copy()

            xx, yy = np.mgrid[x0:x1, y0:y1].astype(np.float32)
            dx = xx - sx
            dy = yy - sy
            dist = np.sqrt(dx * dx + dy * dy)

            mask = np.abs(dist - rayon) < demi
            if not mask.any():
                continue

            profil = np.sin(np.clip((dist - (rayon - demi)) / epaisseur * np.pi, 0, np.pi))
            amp = profil * amplitude_max * fade

            mag = np.maximum(dist, 1e-3)
            ux = dx / mag
            uy = dy / mag

            src_x_rel = np.clip((xx - x0 + ux * amp).astype(np.int32), 0, x1 - x0 - 1)
            src_y_rel = np.clip((yy - y0 + uy * amp).astype(np.int32), 0, y1 - y0 - 1)

            ix, iy = np.where(mask)
            pixels[x0 + ix, y0 + iy] = src_snap[src_x_rel[ix, iy], src_y_rel[ix, iy]]
    finally:
        del pixels   # libère le lock pixels3d
