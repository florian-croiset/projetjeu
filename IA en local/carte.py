# carte.py
# Gère la tilemap du niveau et la carte de visibilité pour chaque joueur.

import pygame
import math
from parametres import *

class Carte:
    def __init__(self):
        # Pour ce prototype, la carte est codée en dur.
        # 0 = Vide, 1 = Mur, 2 = Point de repère visible
        self.map_data = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 2, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        ]
        
        self.largeur_map = len(self.map_data[0])
        self.hauteur_map = len(self.map_data)
        
        # Le serveur stockera une carte de visibilité PAR joueur.
        # Ici, on crée juste la structure. Le serveur la remplira.
        # False = non visible, True = visible
        self.visibility_map = self.creer_carte_visibilite_vierge()

    def creer_carte_visibilite_vierge(self):
        """Crée une carte de visibilité basée sur la map_data."""
        vis_map = []
        for y, rangee in enumerate(self.map_data):
            vis_map.append([])
            for x, tuile in enumerate(rangee):
                if tuile == 2:
                    vis_map[y].append(True) # Les points de repère sont visibles
                else:
                    vis_map[y].append(False)
        return vis_map

    def est_mur(self, x, y):
        """Vérifie si une tuile aux coordonnées (x, y) est un mur."""
        # Convertit les coordonnées en pixels en coordonnées de tuile
        tuile_x = int(x // TAILLE_TUILE)
        tuile_y = int(y // TAILLE_TUILE)
        
        # Vérifie les limites de la carte
        if 0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map:
            return self.map_data[tuile_y][tuile_x] == 1
        return True # Considérer l'extérieur de la carte comme un mur

    def est_solide(self, tuile_x, tuile_y):
        """Vérifie si une tuile aux coordonnées DE TUILE (pas pixels) est un mur."""
        if 0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map:
            return self.map_data[tuile_y][tuile_x] == 1
        return False # Considérer l'extérieur (haut/bas/côtés) comme non solide

    def reveler_par_echo(self, centre_x, centre_y, vis_map):
        """
        Lance des rayons depuis le centre et met à jour la carte de visibilité (vis_map).
        Cette fonction est appelée par le SERVEUR.
        """
        for i in range(NB_RAYONS_ECHO):
            angle = (i / NB_RAYONS_ECHO) * 2 * math.pi
            
            for dist in range(1, PORTEE_ECHO):
                x = centre_x + dist * math.cos(angle)
                y = centre_y + dist * math.sin(angle)
                
                tuile_x = int(x // TAILLE_TUILE)
                tuile_y = int(y // TAILLE_TUILE)

                # Vérifie les limites
                if not (0 <= tuile_x < self.largeur_map and 0 <= tuile_y < self.hauteur_map):
                    break # Sort de la boucle 'dist' si hors carte

                # Si le rayon touche un mur
                if self.map_data[tuile_y][tuile_x] == 1:
                    vis_map[tuile_y][tuile_x] = True # Révèle le mur
                    break # Arrête ce rayon
                else:
                    # Optionnel : révéler aussi le sol traversé ?
                    # Pour l'instant, on ne révèle que le mur touché.
                    pass
        
        # La visibilité est permanente, donc on ne fait que mettre à True.
        # Pour la rendre temporaire, il faudrait stocker un "timestamp"
        # et une autre fonction devrait repasser les True à False.

    def dessiner_carte(self, surface, vis_map):
        """
        Dessine la carte sur la surface (écran).
        Cette fonction est appelée par le CLIENT.
        Elle ne dessine QUE les tuiles visibles (True dans vis_map).
        """
        surface.fill(COULEUR_FOND) # Remplit le fond
        
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if vis_map[y][x]: # Si la tuile est visible
                    rect = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE)
                    
                    tuile_type = self.map_data[y][x]
                    
                    if tuile_type == 1:
                        pygame.draw.rect(surface, COULEUR_MUR_VISIBLE, rect)
                    elif tuile_type == 2:
                        pygame.draw.rect(surface, COULEUR_GUIDE, rect)

    def get_rects_collisions(self):
        """Renvoie une liste de Rect pour tous les murs."""
        rects = []
        for y in range(self.hauteur_map):
            for x in range(self.largeur_map):
                if self.map_data[y][x] == 1:
                    rects.append(pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE))
        return rects