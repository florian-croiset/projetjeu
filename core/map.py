# map.py - Visualiseur de map avancé
# Contrôles :
#   Molette souris          → zoom / dézoom (centré souris)
#   Clic droit + glisser    → déplacer la map (pan)
#   Flèches / WASD          → déplacer la map au clavier
#   Clic gauche             → poser un marqueur + coordonnées
#   R                       → réinitialiser vue
#   G                       → toggle grille
#   M                       → toggle marqueurs
#   Suppr / Backspace       → effacer dernier marqueur
#   C                       → afficher dernières coords dans le terminal
#   Echap                   → quitter

import pygame
import os
import xml.etree.ElementTree as ET

# ── Config ────────────────────────────────────────────────────────────────────
TAILLE_TUILE = 32
ZOOM_MIN     = 0.15
ZOOM_MAX     = 5.0
ZOOM_STEP    = 0.12

COULEUR_FOND         = (10, 10, 15)
COULEUR_MUR          = (80, 80, 120)
COULEUR_VIDE         = (20, 20, 35)
COULEUR_GRILLE       = (35, 35, 55)
COULEUR_CLE          = (255, 215, 0)
COULEUR_MARQUEUR     = (255, 80,  80)
COULEUR_SURBRILLANCE = (255, 255, 255)
COULEUR_INFO         = (0, 212, 255)
COULEUR_WARN         = (255, 215, 0)
COULEUR_AIDE         = (120, 120, 180)


def charger_map(fichier="../assets/MapS2.tmx"):
    dossier = os.path.dirname(os.path.abspath(__file__))
    chemin  = os.path.join(dossier, fichier)
    tree    = ET.parse(chemin)
    root    = tree.getroot()
    largeur = int(root.attrib['width'])
    hauteur = int(root.attrib['height'])
    map_data = [[0] * largeur for _ in range(hauteur)]
    layers_murs = {'Wall.1', 'Sol.1'}
    for layer in root.findall('layer'):
        nom     = layer.attrib.get('name', '')
        data_el = layer.find('data')
        if data_el is None or nom not in layers_murs:
            continue
        valeurs = [int(v) for v in data_el.text.strip().split(',')]
        for y in range(hauteur):
            for x in range(largeur):
                if valeurs[y * largeur + x] != 0:
                    map_data[y][x] = 1
    return largeur, hauteur, map_data


def construire_surface(largeur, hauteur, map_data, grille=True):
    surf = pygame.Surface((largeur * TAILLE_TUILE, hauteur * TAILLE_TUILE))
    for y in range(hauteur):
        for x in range(largeur):
            t = map_data[y][x]
            r = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE)
            pygame.draw.rect(surf, COULEUR_MUR if t == 1 else COULEUR_VIDE, r)
            if grille:
                pygame.draw.rect(surf, COULEUR_GRILLE, r, 1)
    return surf


def ecran_vers_map(mx, my, ox, oy, zoom):
    return (mx - ox) / zoom, (my - oy) / zoom

def map_vers_tuile(px, py):
    return int(px // TAILLE_TUILE), int(py // TAILLE_TUILE)


def afficher_map():
    pygame.init()
    largeur, hauteur, map_data = charger_map()

    WIN_W, WIN_H = 1100, 780
    ecran = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
    pygame.display.set_caption("Visualiseur de Map")

    police     = pygame.font.Font(None, 20)
    police_mid = pygame.font.Font(None, 24)
    police_big = pygame.font.Font(None, 30)

    show_grille = True
    show_marqrs = True

    zoom     = 1.0
    offset_x = 10.0
    offset_y = 60.0

    pan_actif    = False
    dernier_clic = None
    marqueurs    = []

    MAP_W = largeur * TAILLE_TUILE
    MAP_H = hauteur * TAILLE_TUILE

    surf_base = construire_surface(largeur, hauteur, map_data, show_grille)

    # Initialiser get_rel() pour avoir un premier delta à zéro
    pygame.mouse.get_rel()

    horloge = pygame.time.Clock()
    running = True

    while running:
        WIN_W, WIN_H = ecran.get_size()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    zoom, offset_x, offset_y = 1.0, 10.0, 60.0
                elif event.key == pygame.K_g:
                    show_grille = not show_grille
                    surf_base   = construire_surface(largeur, hauteur, map_data, show_grille)
                elif event.key == pygame.K_m:
                    show_marqrs = not show_marqrs
                elif event.key == pygame.K_c and dernier_clic:
                    tx, ty, px, py = dernier_clic
                    print(f"[Copie] Cle(x={int(px)}, y={int(py)})  — tuile ({tx}, {ty})")
                elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                    if marqueurs:
                        marqueurs.pop()

            elif event.type == pygame.MOUSEWHEEL:
                mx, my   = pygame.mouse.get_pos()
                old_zoom = zoom
                if event.y > 0:
                    zoom = min(zoom * (1 + ZOOM_STEP), ZOOM_MAX)
                else:
                    zoom = max(zoom * (1 - ZOOM_STEP), ZOOM_MIN)
                ratio    = zoom / old_zoom
                offset_x = mx - ratio * (mx - offset_x)
                offset_y = my - ratio * (my - offset_y)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:
                    pan_actif = True
                    pygame.mouse.get_rel()  # reset pour éviter un saut au démarrage
                elif event.button == 1 and not pan_actif:
                    mx, my = event.pos
                    px, py = ecran_vers_map(mx, my, offset_x, offset_y, zoom)
                    if 0 <= px < MAP_W and 0 <= py < MAP_H:
                        tx, ty       = map_vers_tuile(px, py)
                        dernier_clic = (tx, ty, px, py)
                        marqueurs.append((int(px), int(py)))
                        print(f"Clic : tuile ({tx}, {ty})  ->  pixel x={int(px)}, y={int(py)}")
                        print(f"       Cle(x={int(px)}, y={int(py)})")

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    pan_actif = False
                    pygame.mouse.get_rel()  # vider le delta résiduel

        # --- Pan clic droit : lu HORS event loop pour capter chaque frame ---
        if pan_actif:
            dx, dy    = pygame.mouse.get_rel()
            offset_x += dx
            offset_y += dy
        else:
            pygame.mouse.get_rel()  # toujours vider l'accumulateur

        # --- Pan clavier ---
        vitesse = max(5, int(14 / zoom))
        keys    = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: offset_x += vitesse
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: offset_x -= vitesse
        if keys[pygame.K_UP]    or keys[pygame.K_w]: offset_y += vitesse
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: offset_y -= vitesse

        # ── Rendu ─────────────────────────────────────────────────────────────
        ecran.fill(COULEUR_FOND)

        nw = int(MAP_W * zoom)
        nh = int(MAP_H * zoom)
        surf_zoom = pygame.transform.scale(surf_base, (nw, nh))
        ecran.blit(surf_zoom, (int(offset_x), int(offset_y)))

        # Surbrillance tuile sous la souris
        mx_s, my_s = pygame.mouse.get_pos()
        px_s, py_s = ecran_vers_map(mx_s, my_s, offset_x, offset_y, zoom)
        sur_tuile  = None
        if 0 <= px_s < MAP_W and 0 <= py_s < MAP_H:
            tx_s, ty_s = map_vers_tuile(px_s, py_s)
            sur_tuile  = (tx_s, ty_s)
            sw = int(TAILLE_TUILE * zoom)
            sx = int(tx_s * TAILLE_TUILE * zoom + offset_x)
            sy = int(ty_s * TAILLE_TUILE * zoom + offset_y)
            pygame.draw.rect(ecran, COULEUR_SURBRILLANCE,
                             pygame.Rect(sx, sy, sw, sw), max(1, int(zoom)))

        # Marqueurs
        if show_marqrs:
            for i, (mpx, mpy) in enumerate(marqueurs):
                ex  = int(mpx * zoom + offset_x)
                ey  = int(mpy * zoom + offset_y)
                col = COULEUR_CLE if i == len(marqueurs) - 1 else COULEUR_MARQUEUR
                t   = max(4, int(7 * zoom))
                pygame.draw.line(ecran, col, (ex-t, ey), (ex+t, ey), 2)
                pygame.draw.line(ecran, col, (ex, ey-t), (ex, ey+t), 2)
                pygame.draw.circle(ecran, col, (ex, ey), max(3, int(4*zoom)), 2)
                if zoom >= 0.5:
                    ecran.blit(police.render(str(i+1), True, col), (ex+t+2, ey-8))

        # HUD supérieur
        hud = pygame.Surface((WIN_W, 52), pygame.SRCALPHA)
        hud.fill((12, 8, 28, 210))
        ecran.blit(hud, (0, 0))

        if sur_tuile:
            t1 = f"Souris -> tuile ({sur_tuile[0]}, {sur_tuile[1]})   pixel ({int(px_s)}, {int(py_s)})"
        else:
            t1 = "Souris hors de la map"
        ecran.blit(police_mid.render(t1, True, COULEUR_INFO), (10, 6))

        if dernier_clic:
            tx, ty, cpx, cpy = dernier_clic
            t2 = f"Dernier clic -> Cle(x={int(cpx)}, y={int(cpy)})   [tuile {tx},{ty}]   #{len(marqueurs)} marqueur(s)"
        else:
            t2 = "Clic gauche : poser marqueur  |  Clic droit drag : deplacer la map"
        ecran.blit(police.render(t2, True, COULEUR_WARN), (10, 30))

        # Zoom haut droit
        zt = police_big.render(f"Zoom {zoom:.2f}x", True, (200, 200, 255))
        ecran.blit(zt, (WIN_W - zt.get_width() - 10, 8))

        if pan_actif:
            pt = police_mid.render("PAN ACTIF", True, (100, 255, 150))
            ecran.blit(pt, (WIN_W - pt.get_width() - 10, 36))

        # Panneau aide bas droit
        aide = [
            "Molette          zoom / dezoom",
            "Clic droit drag  deplacer la map",
            "Fleches / WASD   deplacer la map",
            "R                reset vue",
            "G                toggle grille",
            "M                toggle marqueurs",
            "Suppr            effacer dernier marqueur",
            "C                copier coords (terminal)",
            "Echap            quitter",
        ]
        pw, ph = 278, len(aide) * 16 + 10
        px0    = WIN_W - pw - 8
        py0    = WIN_H - ph - 8
        panel  = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((12, 8, 28, 180))
        ecran.blit(panel, (px0, py0))
        for i, ligne in enumerate(aide):
            ecran.blit(police.render(ligne, True, COULEUR_AIDE), (px0+6, py0+5+i*16))

        # Bas gauche
        bl = police.render(
            f"{len(marqueurs)} marqueur(s)  —  {largeur}x{hauteur} tuiles  ({MAP_W}x{MAP_H} px)",
            True, COULEUR_AIDE)
        ecran.blit(bl, (10, WIN_H - 22))

        pygame.display.flip()
        horloge.tick(60)

    pygame.quit()


if __name__ == "__main__":
    afficher_map()  