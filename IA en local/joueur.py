# joueur.py
# Classe définissant le joueur et sa physique.

import pygame
from parametres import *

class Joueur:
    def __init__(self, x, y, id, couleur=COULEUR_JOUEUR):
        self.id = id
        self.rect = pygame.Rect(x, y, TAILLE_TUILE - 8, TAILLE_TUILE - 4) # Un peu plus petit
        self.couleur = couleur
        
        # Mouvement
        self.vel_y = 0
        self.sur_le_sol = False
        
        # Commandes (sera mis à jour par le réseau)
        self.commandes = {'gauche': False, 'droite': False, 'saut': False}

    def appliquer_physique(self, rects_collision):
        """
        Gère la gravité, le mouvement et les collisions.
        Appelé par le SERVEUR.
        """
        dx = 0
        dy = 0

        # 1. Mouvement horizontal basé sur les commandes
        if self.commandes['gauche']:
            dx = -VITESSE_JOUEUR
        if self.commandes['droite']:
            dx = VITESSE_JOUEUR
            
        # 2. Mouvement vertical (saut et gravité)
        if self.commandes['saut'] and self.sur_le_sol:
            self.vel_y = -FORCE_SAUT
            self.sur_le_sol = False
            self.commandes['saut'] = False # Le saut est un événement unique

        # Appliquer la gravité
        self.vel_y += GRAVITE
        if self.vel_y > 10: # Vitesse de chute max
            self.vel_y = 10
        
        dy = self.vel_y
        
        self.sur_le_sol = False # Réinitialiser avant la vérification des collisions
        
        # 3. Vérification des collisions
        
        # Axe X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0: # Se déplace à droite
                    self.rect.right = mur.left
                elif dx < 0: # Se déplace à gauche
                    self.rect.left = mur.right
        
        # Axe Y
        self.rect.y += dy
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dy > 0: # Tombe
                    self.rect.bottom = mur.top
                    self.vel_y = 0
                    self.sur_le_sol = True
                elif dy < 0: # Saute
                    self.rect.top = mur.bottom
                    self.vel_y = 0 # Stoppe la montée

    def dessiner(self, surface):
        """Dessine le joueur sur l'écran (côté CLIENT)."""
        pygame.draw.rect(surface, self.couleur, self.rect)

    def get_etat(self):
        """Pour l'envoi réseau : renvoie les données essentielles."""
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'couleur': self.couleur
        }

    def set_etat(self, data):
        """Pour la réception réseau : met à jour le joueur."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.couleur = data['couleur']