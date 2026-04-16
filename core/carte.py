# carte.py
# Gère la tilemap du niveau et la carte de visibilité pour chaque joueur.

import pygame
import math
import os
import json
from parametres import *

class Carte:
    def __init__(self, fichier_map="map.json"):
        """Charge la carte depuis un fichier JSON."""
        self.map_data = []
        self.largeur_map = 0
        self.hauteur_map = 0

        # Optimisation rendu : cache GID→Surface + surface pré-cuite
        self._cache_tuiles = {}        # Évite subsurface() à chaque frame
        self._carte_prebake = None     # Surface monde entier pré-rendue
        self._vis_map_dirty = True     # Flag de rebuild (remplace le hash)
        self._tuiles_a_reveler = []    # Buffer de (x, y) à patcher sur le prebake
        
        self._directions = [(math.cos(i/NB_RAYONS_ECHO * 2*math.pi), math.sin(i/NB_RAYONS_ECHO * 2*math.pi)) for i in range(NB_RAYONS_ECHO)]
        
        # Précalcul des sous-ensembles pour l'écho directionnel (cône ±15°)
        # Précalcul de NB_RAYONS_ECHO rayons répartis uniformément dans le cône ±15°
        _demi_rad = ECHO_DIR_DEMI_ANGLE * math.pi / 180
        # Droite : cône centré sur 0° (angle 0 rad)
        self._directions_droite = [
            (math.cos(-_demi_rad + i / (NB_RAYONS_ECHO - 1) * 2 * _demi_rad),
            math.sin(-_demi_rad + i / (NB_RAYONS_ECHO - 1) * 2 * _demi_rad))
            for i in range(NB_RAYONS_ECHO)
        ]
        # Gauche : cône centré sur 180° (angle pi rad)
        self._directions_gauche = [
            (math.cos(math.pi - _demi_rad + i / (NB_RAYONS_ECHO - 1) * 2 * _demi_rad),
            math.sin(math.pi - _demi_rad + i / (NB_RAYONS_ECHO - 1) * 2 * _demi_rad))
            for i in range(NB_RAYONS_ECHO)
        ]
        # Charger le fichier JSON
        if os.path.exists(fichier_map):
            if fichier_map.endswith('.tmx'):
                self.charger_tmx(fichier_map)
        else:
            print(f"[CARTE] Fichier {fichier_map} introuvable, utilisation de la carte par défaut")
            self.charger_carte_par_defaut()
        
        self.visibility_map = self.creer_carte_visibilite_vierge()

    def charger_tmx(self, fichier_map):
        """Charge la carte depuis un fichier TMX Tiled (multi-layers).
        Wall.1 et Sol.1 = murs solides (type 1), tout le reste = vide (type 0)."""
        try:
            import xml.etree.ElementTree as ET
            import sys

            if getattr(sys, 'frozen', False):
                base = os.path.join(sys._MEIPASS, 'assets')
            else:
                base = os.path.dirname(os.path.abspath(fichier_map))

            tree = ET.parse(fichier_map)
            root = tree.getroot()

            self.largeur_map = int(root.attrib['width'])
            self.hauteur_map = int(root.attrib['height'])

            self.map_data = [[0] * self.largeur_map for _ in range(self.hauteur_map)]

            layers_murs = {'Wall.1', 'Sol.1'}
            for layer in root.findall('layer'):
                nom = layer.attrib.get('name', '')
                data_el = layer.find('data')
                if data_el is None:
                    continue
                valeurs = [int(v) for v in data_el.text.strip().split(',')]
                if nom in layers_murs:
                    for y in range(self.hauteur_map):
                        for x in range(self.largeur_map):
                            gid = valeurs[y * self.largeur_map + x]
                            if gid != 0 and self.map_data[y][x] == 0:
                                self.map_data[y][x] = 1

            self.spawn = None
            for og in root.findall('objectgroup'):
                if og.attrib.get('name') == 'Spawn':
                    obj = og.find('object')
                    if obj is not None:
                        self.spawn = (int(float(obj.attrib['x'])),
                                    int(float(obj.attrib['y'])))

            self.layers_gids = []
            for layer in root.findall('layer'):
                data_el = layer.find('data')
                if data_el is None:
                    continue
                valeurs = [int(v) for v in data_el.text.strip().split(',')]
                grille = []
                for row_y in range(self.hauteur_map):
                    grille.append(valeurs[row_y * self.largeur_map:(row_y + 1) * self.largeur_map])
                self.layers_gids.append(grille)

            # Tileset
            ts_el = root.find('tileset')
            self.tileset_firstgid = int(ts_el.attrib.get('firstgid', 1))
            self.tileset = None

            tsx_src = ts_el.attrib.get('source', '')
            if tsx_src:
                tsx_path = os.path.join(base, tsx_src)
                tsx_tree = ET.parse(tsx_path)
                tsx_root = tsx_tree.getroot()
                self.tileset_taille   = int(tsx_root.attrib.get('tilewidth', 32))
                self.tileset_spacing  = int(tsx_root.attrib.get('spacing', 0))
                self.tileset_margin   = int(tsx_root.attrib.get('margin', 0))
                img_el = tsx_root.find('image')
                img_w  = int(img_el.attrib.get('width', 0))
                self.tileset_colonnes = (img_w - 2 * self.tileset_margin + self.tileset_spacing) // (self.tileset_taille + self.tileset_spacing)
                tileset_img_src = img_el.attrib.get('source', 'tileset.png')
            else:
                self.tileset_taille   = int(ts_el.attrib.get('tilewidth', 32))
                self.tileset_spacing  = int(ts_el.attrib.get('spacing', 0))
                self.tileset_margin   = int(ts_el.attrib.get('margin', 0))
                self.tileset_colonnes = 11
                tileset_img_src = 'tileset.png'

            try:
                self.tileset = pygame.image.load(
                    os.path.join(base, tileset_img_src)).convert_alpha()
                print("[CARTE] Tileset chargé")
            except Exception as e:
                print(f"[CARTE] Tileset introuvable : {e}")

            self._cache_tuiles = {}   # Reset cache si tileset rechargé

            # Image layers (midground, background PNG)
            self.image_layers = []
            for il in root.findall('imagelayer'):
                src = il.find('image')
                if src is None:
                    continue
                chemin_img = os.path.join(base, src.attrib['source'])
                offset_x = float(il.attrib.get('offsetx', 0))
                offset_y = float(il.attrib.get('offsety', 0))
                try:
                    img = pygame.image.load(chemin_img).convert_alpha()
                    self.image_layers.append({
                        'surface': img,
                        'offset_x': offset_x,
                        'offset_y': offset_y,
                    })
                    print(f"[CARTE] Image layer chargé : {src.attrib['source']}")
                except Exception as e:
                    print(f"[CARTE] Image layer introuvable : {e}")

            print(f"[CARTE] Map TMX chargee : {self.largeur_map}x{self.hauteur_map}")
            if self.spawn:
                print(f"[CARTE] Spawn : {self.spawn}")

        except Exception as e:
            print(f"[CARTE] ERREUR lors du chargement du TMX: {e}")
            import traceback
            traceback.print_exc()
            self.charger_carte_par_defaut()

    def charger_carte_par_defaut(self):
        """Charge la carte codée en dur (backup)."""
        self.map_data = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 2, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        ]
        self.largeur_map = len(self.map_data[0])
        self.hauteur_map = len(self.map_data)
        self.layers_gids = []        
        self.tileset = None
        self.layers_gids = []
        self.image_layers = []
        print(f"[CARTE] Carte par défaut chargee : {self.largeur_map}x{self.hauteur_map}")

    def creer_carte_visibilite_vierge(self):
        """Crée une carte de visibilité basée sur la map_data."""
        vis_map = []
        for y, rangee in enumerate(self.map_data):
            vis_map.append([])
            for x, tuile in enumerate(rangee):
                vis_map[y].append(REVELATION)
        return vis_map

    def est_mur(self, x, y):
        """Vérifie si une tuile aux coordonnées (x, y) est un mur."""
        tuile_x = int(x // TAILLE_TUILE)
        tuile_y = int(y // TAILLE_TUILE)
        
        if 0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map:
            return self.map_data[tuile_y][tuile_x] == 1
        return True 

    def est_solide(self, tuile_x, tuile_y):
        """Vérifie si une tuile est solide (pour l'ennemi)."""
        if 0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map:
            return self.map_data[tuile_y][tuile_x] in [1, 3]
        return False

    def _reveler_voisins(self, tuile_x, tuile_y, vis_map, delta_set=None):
            """Révèle le bloc touché + les voisins dans un rayon de 2 blocs (carré 5x5)."""
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = tuile_x + dx, tuile_y + dy
                    if 0 <= nx < self.largeur_map and 0 <= ny < self.hauteur_map:
                        if not vis_map[ny][nx]:
                            vis_map[ny][nx] = True
                            if delta_set is not None:
                                delta_set.add((nx, ny))

    def reveler_par_echo(self, centre_x, centre_y, vis_map):
        """Lance des rayons via l'algorithme DDA (rapide et précis)."""
        tuile_depart_x = int(centre_x // TAILLE_TUILE)
        tuile_depart_y = int(centre_y // TAILLE_TUILE)
        portee_tuiles = int(PORTEE_ECHO // TAILLE_TUILE)

        for cos_a, sin_a in self._directions:
            step_x = 1 if cos_a > 0 else -1 if cos_a < 0 else 0
            step_y = 1 if sin_a > 0 else -1 if sin_a < 0 else 0

            t_delta_x = abs(TAILLE_TUILE / cos_a) if cos_a != 0 else float('inf')
            t_delta_y = abs(TAILLE_TUILE / sin_a) if sin_a != 0 else float('inf')

            t_max_x = abs(((tuile_depart_x + (1 if step_x > 0 else 0)) * TAILLE_TUILE - centre_x) / cos_a) if cos_a != 0 else float('inf')
            t_max_y = abs(((tuile_depart_y + (1 if step_y > 0 else 0)) * TAILLE_TUILE - centre_y) / sin_a) if sin_a != 0 else float('inf')

            tuile_actuelle_x = tuile_depart_x
            tuile_actuelle_y = tuile_depart_y

            for _ in range(portee_tuiles):
                if not (0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map):
                    break

                tuile_type = self.map_data[tuile_actuelle_y][tuile_actuelle_x]
                if tuile_type in [1, 3]:
                    self._reveler_voisins(tuile_actuelle_x, tuile_actuelle_y, vis_map)
                    break
                vis_map[tuile_actuelle_y][tuile_actuelle_x] = True

                if t_max_x < t_max_y:
                    t_max_x += t_delta_x
                    tuile_actuelle_x += step_x
                else:
                    t_max_y += t_delta_y
                    tuile_actuelle_y += step_y

    def reveler_anneau(self, centre_x, centre_y, rayon_min, rayon_max, vis_map):
        """Révèle les tuiles dans l'anneau [rayon_min, rayon_max] pixels.
        Utilisé pour la révélation progressive de l'écho."""
        for i in range(NB_RAYONS_ECHO):
            cos_a, sin_a = self._directions[i]

            for dist in range(max(1, rayon_min), min(rayon_max + 1, PORTEE_ECHO)):
                x = centre_x + dist * cos_a
                y = centre_y + dist * sin_a

                tuile_x = int(x // TAILLE_TUILE)
                tuile_y = int(y // TAILLE_TUILE)

                if not (0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map):
                    break

                if self.map_data[tuile_y][tuile_x] in [1, 3]:
                    vis_map[tuile_y][tuile_x] = True
                    break  # Stop au premier mur : pas de traversée

    def _dessiner_tuile_prebake(self, x, y):
        """Dessine une seule tuile sur la surface pré-cuite."""
        px = x * TAILLE_TUILE
        py = y * TAILLE_TUILE
        tile_dessine = False
        for gids_layer in self.layers_gids:
            gid = gids_layer[y][x]
            if gid != 0 and self.tileset:
                tile_surf = self.get_tile_surface(gid)
                if tile_surf:
                    self._carte_prebake.blit(tile_surf, (px, py))
                    tile_dessine = True
        if not tile_dessine:
            tuile_type = self.map_data[y][x]
            rect = pygame.Rect(px, py, TAILLE_TUILE, TAILLE_TUILE)
            if tuile_type == 1:
                pygame.draw.rect(self._carte_prebake, COULEUR_MUR_VISIBLE, rect)
            elif tuile_type == 2:
                pygame.draw.rect(self._carte_prebake, COULEUR_GUIDE, rect)
            elif tuile_type == 3:
                pygame.draw.rect(self._carte_prebake, COULEUR_SAUVEGARDE, rect)

    def dessiner_carte(self, surface, vis_map, camera_offset=(0,0)):
        off_x, off_y = camera_offset
        lv, hv = surface.get_size()

        map_w = self.largeur_map * TAILLE_TUILE
        map_h = self.hauteur_map * TAILLE_TUILE

        if (self._carte_prebake is None
                or self._carte_prebake.get_size() != (map_w, map_h)
                or self._vis_map_dirty):
            # Chemin A — Reconstruction complète
            self._carte_prebake = pygame.Surface((map_w, map_h))
            self._carte_prebake.fill(COULEUR_FOND)

            for il in getattr(self, 'image_layers', []):
                self._carte_prebake.blit(
                    il['surface'], (int(il['offset_x']), int(il['offset_y'])))

            for y in range(self.hauteur_map):
                for x in range(self.largeur_map):
                    if not vis_map[y][x]:
                        continue
                    self._dessiner_tuile_prebake(x, y)

            self._vis_map_dirty = False
            self._tuiles_a_reveler.clear()

        elif self._tuiles_a_reveler:
            # Chemin B — Patch incrémental (tuiles nouvellement révélées)
            for x, y in self._tuiles_a_reveler:
                if 0 <= x < self.largeur_map and 0 <= y < self.hauteur_map:
                    self._dessiner_tuile_prebake(x, y)
            self._tuiles_a_reveler.clear()

        # Chemin C implicite — rien à faire si pas dirty et pas de tuiles

        # Simple blit de la fenêtre caméra depuis la surface pré-cuite
        surface.fill(COULEUR_FOND)
        surface.blit(self._carte_prebake, (0, 0), pygame.Rect(off_x, off_y, lv, hv))
        
    def get_rects_collisions(self):
        """Renvoie une liste de Rect pour tous les murs (type 1)."""
        rects = []
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if self.map_data[y][x] == 1:
                    rects.append(pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE))
        return rects

    # ------------------------------------------------------------------
    #  GRILLE SPATIALE POUR COLLISIONS
    # ------------------------------------------------------------------

    _CELL_SIZE = TAILLE_TUILE * 4  # 128px par cellule

    def construire_grille_collision(self):
        """Construit une grille spatiale à partir des rects de collision."""
        self._grille_collision = {}
        cs = self._CELL_SIZE
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if self.map_data[y][x] == 1:
                    r = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE,
                                    TAILLE_TUILE, TAILLE_TUILE)
                    cle = (x * TAILLE_TUILE // cs, y * TAILLE_TUILE // cs)
                    self._grille_collision.setdefault(cle, []).append(r)

    def get_rects_proches(self, rect, marge=None):
        """Retourne les rects de collision dans les cellules chevauchées par rect + marge.

        La marge (par défaut TAILLE_TUILE*2) compense le déplacement entre la
        requête et les vérifications de collision après mouvement.
        """
        if marge is None:
            marge = TAILLE_TUILE * 2
        cs = self._CELL_SIZE
        x_min = (rect.left   - marge) // cs
        x_max = (rect.right  + marge) // cs
        y_min = (rect.top    - marge) // cs
        y_max = (rect.bottom + marge) // cs
        resultat = []
        for cy in range(y_min, y_max + 1):
            for cx in range(x_min, x_max + 1):
                cellule = self._grille_collision.get((cx, cy))
                if cellule:
                    resultat.extend(cellule)
        return resultat
    
    # def reveler_par_echo_partiel(self, centre_x, centre_y, portee, vis_map):
    #     """Révélation progressive : repart de 0 jusqu'à portee pixels."""
    #     for i in range(NB_RAYONS_ECHO):
    #         cos_a, sin_a = self._directions[i]
    #         for dist in range(1, min(portee + 1, PORTEE_ECHO)):
    #             x = centre_x + dist * cos_a
    #             y = centre_y + dist * sin_a
    #             tuile_x = int(x // TAILLE_TUILE)
    #             tuile_y = int(y // TAILLE_TUILE)
    #             if not (0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map):
    #                 break
    #             if self.map_data[tuile_y][tuile_x] in [1, 3]:
    #                 vis_map[tuile_y][tuile_x] = True
    #                 break
    def reveler_par_echo_partiel(self, centre_x, centre_y, portee, vis_map, delta_set=None):
        """Révélation progressive avec DDA : s'arrête sur les murs et à la distance 'portee'."""
        tuile_depart_x = int(centre_x // TAILLE_TUILE)
        tuile_depart_y = int(centre_y // TAILLE_TUILE)
        for cos_a, sin_a in self._directions:
            dir_x = cos_a if cos_a != 0 else 1e-10
            dir_y = sin_a if sin_a != 0 else 1e-10
            t_delta_x = abs(TAILLE_TUILE / dir_x)
            t_delta_y = abs(TAILLE_TUILE / dir_y)
            step_x = 1 if dir_x > 0 else -1
            step_y = 1 if dir_y > 0 else -1
            if dir_x > 0:
                t_max_x = ((tuile_depart_x + 1) * TAILLE_TUILE - centre_x) / dir_x
            else:
                t_max_x = (centre_x - tuile_depart_x * TAILLE_TUILE) / abs(dir_x)
            if dir_y > 0:
                t_max_y = ((tuile_depart_y + 1) * TAILLE_TUILE - centre_y) / dir_y
            else:
                t_max_y = (centre_y - tuile_depart_y * TAILLE_TUILE) / abs(dir_y)
            tuile_actuelle_x = tuile_depart_x
            tuile_actuelle_y = tuile_depart_y
            distance_parcourue = 0
            if 0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map:
                if not vis_map[tuile_actuelle_y][tuile_actuelle_x]:
                    vis_map[tuile_actuelle_y][tuile_actuelle_x] = True
                    if delta_set is not None:
                        delta_set.add((tuile_actuelle_x, tuile_actuelle_y))
            while True:
                if t_max_x < t_max_y:
                    distance_parcourue = t_max_x
                    t_max_x += t_delta_x
                    tuile_actuelle_x += step_x
                else:
                    distance_parcourue = t_max_y
                    t_max_y += t_delta_y
                    tuile_actuelle_y += step_y
                if distance_parcourue > portee:
                    break
                if not (0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map):
                    break
                if not vis_map[tuile_actuelle_y][tuile_actuelle_x]:
                    vis_map[tuile_actuelle_y][tuile_actuelle_x] = True
                    if delta_set is not None:
                        delta_set.add((tuile_actuelle_x, tuile_actuelle_y))
                if self.map_data[tuile_actuelle_y][tuile_actuelle_x] in [1, 3]:
                    self._reveler_voisins(tuile_actuelle_x, tuile_actuelle_y, vis_map, delta_set)
                    break
    def reveler_par_echo_dir_partiel(self, centre_x, centre_y, portee, vis_map, direction, delta_set=None):
        """Révélation progressive DDA dans un cône directionnel de ±15°.
        direction : 1 = droite (0°), -1 = gauche (180°)."""
        directions_cone = self._directions_droite if direction >= 0 else self._directions_gauche
        tuile_depart_x = int(centre_x // TAILLE_TUILE)
        tuile_depart_y = int(centre_y // TAILLE_TUILE)

        for cos_a, sin_a in directions_cone:
            dir_x = cos_a if cos_a != 0 else 1e-10
            dir_y = sin_a if sin_a != 0 else 1e-10
            t_delta_x = abs(TAILLE_TUILE / dir_x)
            t_delta_y = abs(TAILLE_TUILE / dir_y)
            step_x = 1 if dir_x > 0 else -1
            step_y = 1 if dir_y > 0 else -1
            if dir_x > 0:
                t_max_x = ((tuile_depart_x + 1) * TAILLE_TUILE - centre_x) / dir_x
            else:
                t_max_x = (centre_x - tuile_depart_x * TAILLE_TUILE) / abs(dir_x)
            if dir_y > 0:
                t_max_y = ((tuile_depart_y + 1) * TAILLE_TUILE - centre_y) / dir_y
            else:
                t_max_y = (centre_y - tuile_depart_y * TAILLE_TUILE) / abs(dir_y)
            tuile_actuelle_x = tuile_depart_x
            tuile_actuelle_y = tuile_depart_y
            distance_parcourue = 0
            if 0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map:
                if not vis_map[tuile_actuelle_y][tuile_actuelle_x]:
                    vis_map[tuile_actuelle_y][tuile_actuelle_x] = True
                    if delta_set is not None:
                        delta_set.add((tuile_actuelle_x, tuile_actuelle_y))
            while True:
                if t_max_x < t_max_y:
                    distance_parcourue = t_max_x
                    t_max_x += t_delta_x
                    tuile_actuelle_x += step_x
                else:
                    distance_parcourue = t_max_y
                    t_max_y += t_delta_y
                    tuile_actuelle_y += step_y
                if distance_parcourue > portee:
                    break
                if not (0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map):
                    break
                if not vis_map[tuile_actuelle_y][tuile_actuelle_x]:
                    vis_map[tuile_actuelle_y][tuile_actuelle_x] = True
                    if delta_set is not None:
                        delta_set.add((tuile_actuelle_x, tuile_actuelle_y))
                if self.map_data[tuile_actuelle_y][tuile_actuelle_x] in [1, 3]:
                    self._reveler_voisins(tuile_actuelle_x, tuile_actuelle_y, vis_map, delta_set)
                    break
    
    

    def get_tile_surface(self, gid):
        if self.tileset is None or gid <= 0:
            return None
        # Lookup cache — subsurface() n'est appelé qu'une seule fois par GID
        if gid in self._cache_tuiles:
            return self._cache_tuiles[gid]
        idx = gid - self.tileset_firstgid
        if idx < 0:
            self._cache_tuiles[gid] = None
            return None
        col = idx % self.tileset_colonnes
        row = idx // self.tileset_colonnes
        x = self.tileset_margin + col * (self.tileset_taille + self.tileset_spacing)
        y = self.tileset_margin + row * (self.tileset_taille + self.tileset_spacing)
        ts_w, ts_h = self.tileset.get_size()
        if x + self.tileset_taille > ts_w or y + self.tileset_taille > ts_h:
            self._cache_tuiles[gid] = None
            return None
        surf = self.tileset.subsurface(pygame.Rect(x, y, self.tileset_taille, self.tileset_taille))
        self._cache_tuiles[gid] = surf
        return surf