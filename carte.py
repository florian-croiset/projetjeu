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
            
            print(f"[CARTE] Map JSON chargée : {self.largeur_map}x{self.hauteur_map}")
            print(f"[CARTE] Première ligne : {self.map_data[0][:10]}...")
            print(f"[CARTE] Dernière ligne : {self.map_data[-1][:10]}...")
            
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
        print(f"[CARTE] Carte par défaut chargée : {self.largeur_map}x{self.hauteur_map}")

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
        """Lance des rayons depuis le centre et met à jour la carte de visibilité."""
        for i in range(NB_RAYONS_ECHO):
            angle = (i / NB_RAYONS_ECHO) * 2 * math.pi
            
            for dist in range(1, PORTEE_ECHO):
                x = centre_x + dist * math.cos(angle)
                y = centre_y + dist * math.sin(angle)
                
                tuile_x = int(x // TAILLE_TUILE)
                tuile_y = int(y // TAILLE_TUILE)

                if not (0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map):
                    break 

                if self.map_data[tuile_y][tuile_x] in [1, 3]:
                    vis_map[tuile_y][tuile_x] = True 
                    break 

    def dessiner_carte(self, surface, vis_map, camera_offset=(0,0)):
        """Dessine la carte en tenant compte de la caméra."""
        surface.fill(COULEUR_FOND)
        
        off_x, off_y = camera_offset
        
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if vis_map[y][x]:
                    pos_x = (x * TAILLE_TUILE) - off_x
                    pos_y = (y * TAILLE_TUILE) - off_y
                    
                    rect = pygame.Rect(pos_x, pos_y, TAILLE_TUILE, TAILLE_TUILE)
                    
                    if surface.get_rect().colliderect(rect):
                        tuile_type = self.map_data[y][x]
                        if tuile_type == 1:
                            pygame.draw.rect(surface, COULEUR_MUR_VISIBLE, rect)
                        elif tuile_type == 2:
                            pygame.draw.rect(surface, COULEUR_GUIDE, rect)
                        elif tuile_type == 3:
                            pygame.draw.rect(surface, COULEUR_SAUVEGARDE, rect)

    def get_rects_collisions(self):
        """Renvoie une liste de Rect pour tous les murs (type 1)."""
        rects = []
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if self.map_data[y][x] == 1:
                    rects.append(pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE))
        return rects