# map.py - Visualiseur de map avec coordonnées au clic souris

import pygame
import json
import sys
import os

TAILLE_TUILE = 32
COULEUR_FOND       = (10, 10, 10)
COULEUR_MUR        = (80, 80, 120)
COULEUR_GUIDE      = (40, 40, 70)
COULEUR_SAUVEGARDE = (0, 200, 100)
COULEUR_VIDE       = (20, 20, 35)
COULEUR_GRILLE     = (30, 30, 50)
COULEUR_CLÉ        = (255, 215, 0)   # repère doré pour positionner la clé

def charger_map(fichier="assets/MapS2.tmx"):
    import xml.etree.ElementTree as ET
    dossier = os.path.dirname(os.path.abspath(__file__))
    chemin  = os.path.join(dossier, fichier)
    tree = ET.parse(chemin)
    root = tree.getroot()
    largeur = int(root.attrib['width'])
    hauteur = int(root.attrib['height'])
    map_data = [[0] * largeur for _ in range(hauteur)]
    layers_murs = {'Wall.1', 'Sol.1'}
    for layer in root.findall('layer'):
        nom = layer.attrib.get('name', '')
        data_el = layer.find('data')
        if data_el is None or nom not in layers_murs:
            continue
        valeurs = [int(v) for v in data_el.text.strip().split(',')]
        for y in range(hauteur):
            for x in range(largeur):
                gid = valeurs[y * largeur + x]
                if gid != 0:
                    map_data[y][x] = 1
    return largeur, hauteur, map_data

def afficher_map():
    pygame.init()
    largeur, hauteur, map_data = charger_map()

    map_w = largeur * TAILLE_TUILE   # 1024
    map_h = hauteur * TAILLE_TUILE   # 768

    # Fenêtre un peu plus grande pour laisser de l'espace à la légende
    WIN_W = max(map_w + 20, 800)
    WIN_H = max(map_h + 80, 600)
    ecran = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Visualiseur de Map — Clique pour obtenir les coordonnées")

    # Pré-dessiner la map sur une surface
    surface_map = pygame.Surface((map_w, map_h))
    for y in range(hauteur):
        for x in range(largeur):
            tuile = map_data[y][x]
            rect  = pygame.Rect(x*TAILLE_TUILE, y*TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE)
            if   tuile == 0: couleur = COULEUR_VIDE
            elif tuile == 1: couleur = COULEUR_MUR
            elif tuile == 2: couleur = COULEUR_GUIDE
            elif tuile == 3: couleur = COULEUR_SAUVEGARDE
            else:            couleur = (255, 0, 255)
            pygame.draw.rect(surface_map, couleur, rect)
            pygame.draw.rect(surface_map, COULEUR_GRILLE, rect, 1)

    police     = pygame.font.Font(None, 22)
    police_big = pygame.font.Font(None, 28)

    # Décalage de la map dans la fenêtre (centrage)
    MAP_OX = 10
    MAP_OY = 50  # espace en haut pour la légende

    dernier_clic = None   # (tuile_x, tuile_y, pixel_x, pixel_y)
    marqueur     = None   # (pixel_x, pixel_y) dans la map

    horloge = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # Convertir en coordonnées dans la map
                px = mx - MAP_OX
                py = my - MAP_OY
                if 0 <= px < map_w and 0 <= py < map_h:
                    tx = px // TAILLE_TUILE
                    ty = py // TAILLE_TUILE
                    dernier_clic = (tx, ty, px, py)
                    marqueur     = (px, py)
                    print(f"Clique : tuile ({tx}, {ty})  ->  pixels x={px}, y={py}")
                    print(f"         dans serveur.py : Cle(x={px}, y={py})")

        # Fond
        ecran.fill(COULEUR_FOND)

        # Map
        ecran.blit(surface_map, (MAP_OX, MAP_OY))

        # Marqueur au clic (croix dorée)
        if marqueur:
            mx_m = marqueur[0] + MAP_OX
            my_m = marqueur[1] + MAP_OY
            pygame.draw.line(ecran, COULEUR_CLÉ, (mx_m-10, my_m), (mx_m+10, my_m), 2)
            pygame.draw.line(ecran, COULEUR_CLÉ, (mx_m, my_m-10), (mx_m, my_m+10), 2)
            pygame.draw.circle(ecran, COULEUR_CLÉ, (mx_m, my_m), 5, 2)

        # Surbrillance tuile sous la souris
        mx_s, my_s = pygame.mouse.get_pos()
        px_s = mx_s - MAP_OX
        py_s = my_s - MAP_OY
        if 0 <= px_s < map_w and 0 <= py_s < map_h:
            tx_s = (px_s // TAILLE_TUILE) * TAILLE_TUILE
            ty_s = (py_s // TAILLE_TUILE) * TAILLE_TUILE
            sur_rect = pygame.Rect(tx_s + MAP_OX, ty_s + MAP_OY, TAILLE_TUILE, TAILLE_TUILE)
            pygame.draw.rect(ecran, (255, 255, 255), sur_rect, 2)

        # Bandeau info en haut
        info1 = f"Souris : tuile ({px_s//TAILLE_TUILE}, {py_s//TAILLE_TUILE})  pixel ({px_s}, {py_s})"
        if dernier_clic:
            tx, ty, cpx, cpy = dernier_clic
            info2 = f"Dernier clic -> Cle(x={cpx}, y={cpy})   [tuile {tx},{ty}]  — aussi affiché dans le terminal"
        else:
            info2 = "Clique sur la map pour obtenir les coordonnées à copier dans serveur.py"

        pygame.draw.rect(ecran, (14, 10, 35), pygame.Rect(0, 0, WIN_W, 46))
        ecran.blit(police.render(info1, True, (0, 212, 255)), (10, 8))
        ecran.blit(police.render(info2, True, (255, 215, 0)), (10, 28))

        pygame.display.flip()
        horloge.tick(60)

    pygame.quit()

if __name__ == "__main__":
    afficher_map()