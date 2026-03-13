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
        self._directions = [(math.cos(i/NB_RAYONS_ECHO * 2*math.pi), math.sin(i/NB_RAYONS_ECHO * 2*math.pi)) for i in range(NB_RAYONS_ECHO)]
        # Charger le fichier JSON
        if os.path.exists(fichier_map):
            self.charger_json(fichier_map)
        else:
            print(f"[CARTE] Fichier {fichier_map} introuvable, utilisation de la carte par défaut")
            self.charger_carte_par_defaut()
        
        self.visibility_map = self.creer_carte_visibilite_vierge()

    def charger_json(self, fichier_map):
        """Charge la carte depuis un fichier JSON."""
        try:
            with open(fichier_map, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.largeur_map = data['largeur']
            self.hauteur_map = data['hauteur']
            self.map_data = data['data']
            
            print(f"[CARTE] Map JSON chargee : {self.largeur_map}x{self.hauteur_map}")
            print(f"[CARTE] Premiere ligne : {self.map_data[0][:10]}...")
            print(f"[CARTE] Derniere ligne : {self.map_data[-1][:10]}...")
            
        except Exception as e:
            print(f"[CARTE] ERREUR lors du chargement du JSON: {e}")
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
        print(f"[CARTE] Carte par défaut chargee : {self.largeur_map}x{self.hauteur_map}")

    def creer_carte_visibilite_vierge(self):
        """Crée une carte de visibilité basée sur la map_data."""
        vis_map = []
        for y, rangee in enumerate(self.map_data):
            vis_map.append([])
            for x, tuile in enumerate(rangee):
                if tuile == 2:
                    vis_map[y].append(True) 
                else:
                    vis_map[y].append(False)
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

    def reveler_par_echo(self, centre_x, centre_y, vis_map):
        """Lance des rayons via l'algorithme DDA (rapide et précis)."""
        tuile_depart_x = int(centre_x // TAILLE_TUILE)
        tuile_depart_y = int(centre_y // TAILLE_TUILE)
        portee_tuiles = int(PORTEE_ECHO // TAILLE_TUILE)

        for cos_a, sin_a in self._directions:
            x, y = centre_x, centre_y
            
            # Calcul des pas pour se déplacer d'une tuile à l'autre
            step_x = 1 if cos_a > 0 else -1 if cos_a < 0 else 0
            step_y = 1 if sin_a > 0 else -1 if sin_a < 0 else 0
            
            # Éviter la division par zéro
            t_delta_x = abs(TAILLE_TUILE / cos_a) if cos_a != 0 else float('inf')
            t_delta_y = abs(TAILLE_TUILE / sin_a) if sin_a != 0 else float('inf')
            
            # Distance initiale jusqu'à la prochaine tuile
            t_max_x = abs(((tuile_depart_x + (1 if step_x > 0 else 0)) * TAILLE_TUILE - x) / cos_a) if cos_a != 0 else float('inf')
            t_max_y = abs(((tuile_depart_y + (1 if step_y > 0 else 0)) * TAILLE_TUILE - y) / sin_a) if sin_a != 0 else float('inf')

            tuile_actuelle_x = tuile_depart_x
            tuile_actuelle_y = tuile_depart_y

            for _ in range(portee_tuiles):
                if not (0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map):
                    break

                tuile_type = self.map_data[tuile_actuelle_y][tuile_actuelle_x]
                
                if tuile_type in [1, 3]:  # C'est un mur ou un point de sauvegarde
                    vis_map[tuile_actuelle_y][tuile_actuelle_x] = True
                    break # Le rayon s'arrête net sur le mur

                # On révèle les tuiles vides traversées
                vis_map[tuile_actuelle_y][tuile_actuelle_x] = True

                # Avancer vers la prochaine intersection de grille
                if t_max_x < t_max_y:
                    t_max_x += t_delta_x
                    tuile_actuelle_x += step_x
                else:
                    t_max_y += t_delta_y
                    tuile_actuelle_y += step_y

    # def reveler_par_echo(self, centre_x, centre_y, vis_map):
    #     """Lance des rayons depuis le centre — s'arrête sur les murs (ne traverse pas)."""
    #     for i in range(NB_RAYONS_ECHO):
    #         cos_a, sin_a = self._directions[i]

    #         for dist in range(1, PORTEE_ECHO):
    #             x = centre_x + dist * cos_a
    #             y = centre_y + dist * sin_a

    #             tuile_x = int(x // TAILLE_TUILE)
    #             tuile_y = int(y // TAILLE_TUILE)

    #             if not (0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map):
    #                 break

    #             if self.map_data[tuile_y][tuile_x] in [1, 3]:
    #                 vis_map[tuile_y][tuile_x] = True
    #                 break  # Stop : le rayon ne traverse pas le mur

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

    def dessiner_carte(self, surface, vis_map, camera_offset=(0,0)):
        surface.fill(COULEUR_FOND)
        off_x, off_y = camera_offset
        
        # Ne calculer que la zone visible à l'écran
        tuile_min_x = max(0, int(off_x // TAILLE_TUILE))
        tuile_max_x = min(self.largeur_map, int((off_x + surface.get_width()) // TAILLE_TUILE) + 2)
        tuile_min_y = max(0, int(off_y // TAILLE_TUILE))
        tuile_max_y = min(self.hauteur_map, int((off_y + surface.get_height()) // TAILLE_TUILE) + 2)
        
        for y in range(tuile_min_y, tuile_max_y):
            for x in range(tuile_min_x, tuile_max_x):
                if vis_map[y][x]:
                    pos_x = (x * TAILLE_TUILE) - off_x
                    pos_y = (y * TAILLE_TUILE) - off_y
                    
                    tuile_type = self.map_data[y][x]
                    rect = pygame.Rect(pos_x, pos_y, TAILLE_TUILE, TAILLE_TUILE)
                    if tuile_type == 1:
                        pygame.draw.rect(surface, COULEUR_MUR_VISIBLE, rect)
                    # ... suite de tes conditions

    def get_rects_collisions(self):
        """Renvoie une liste de Rect pour tous les murs (type 1)."""
        rects = []
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if self.map_data[y][x] == 1:
                    rects.append(pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE))
        return rects
    
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
    def reveler_par_echo_partiel(self, centre_x, centre_y, portee, vis_map):
        """Révélation progressive avec DDA : s'arrête exactement sur les murs et à la distance 'portee'."""
        tuile_depart_x = int(centre_x // TAILLE_TUILE)
        tuile_depart_y = int(centre_y // TAILLE_TUILE)

        for cos_a, sin_a in self._directions:
            # Sécurité pour éviter la division par zéro
            dir_x = cos_a if cos_a != 0 else 1e-10
            dir_y = sin_a if sin_a != 0 else 1e-10

            # Calcul de la distance du rayon pour traverser exactement la largeur/hauteur d'une tuile
            t_delta_x = abs(TAILLE_TUILE / dir_x)
            t_delta_y = abs(TAILLE_TUILE / dir_y)

            # Direction du pas dans la grille (+1 ou -1)
            step_x = 1 if dir_x > 0 else -1
            step_y = 1 if dir_y > 0 else -1

            # Calcul de la distance initiale jusqu'au premier bord de la tuile
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

            # On révèle la tuile de départ si elle est dans la carte
            if 0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map:
                vis_map[tuile_actuelle_y][tuile_actuelle_x] = True

            # Boucle d'avancement du rayon (DDA)
            while True:
                # Avancer vers la prochaine intersection de la grille
                if t_max_x < t_max_y:
                    distance_parcourue = t_max_x
                    t_max_x += t_delta_x
                    tuile_actuelle_x += step_x
                else:
                    distance_parcourue = t_max_y
                    t_max_y += t_delta_y
                    tuile_actuelle_y += step_y

                # Si le rayon a parcouru une distance supérieure à la portée actuelle de l'écho, on l'arrête
                if distance_parcourue > portee:
                    break

                # Si on sort des limites de la carte, on arrête ce rayon
                if not (0 <= tuile_actuelle_x < self.largeur_map and 0 <= tuile_actuelle_y < self.hauteur_map):
                    break

                # Révéler la tuile actuelle
                vis_map[tuile_actuelle_y][tuile_actuelle_x] = True

                # Arrêt net si c'est un mur (1) ou un point de sauvegarde (3)
                if self.map_data[tuile_actuelle_y][tuile_actuelle_x] in [1, 3]:
                    break