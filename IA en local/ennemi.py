# ennemi.py
# Classe définissant un ennemi simple (IA de patrouille).

import pygame
from parametres import *

class Ennemi:
    def __init__(self, x, y, id):
        self.id = id
        self.rect = pygame.Rect(x, y, TAILLE_TUILE - 8, TAILLE_TUILE - 4)
        self.couleur = COULEUR_ENNEMI
        
        # Mouvement
        self.vel_y = 0
        self.vitesse_patrouille = VITESSE_ENNEMI
        self.sur_le_sol = False

    def appliquer_logique(self, rects_collision, carte):
        """
        Gère la physique, la patrouille et la détection de vide.
        Appelé par le SERVEUR.
        """
        dx = 0
        dy = 0

        # --- Logique de Patrouille (IA) ---
        
        # 1. Détection du vide
        # On vérifie la tuile juste en dessous et devant nous
        
        # Coordonnées de la tuile à vérifier (juste devant les pieds)
        tuile_x_verif = 0
        if self.vitesse_patrouille > 0: # Se déplace à droite
            tuile_x_verif = (self.rect.right + 2) // TAILLE_TUILE
        else: # Se déplace à gauche
            tuile_x_verif = (self.rect.left - 2) // TAILLE_TUILE
            
        tuile_y_verif = (self.rect.bottom + 1) // TAILLE_TUILE
        
        # S'il n'y a PAS de sol devant, on fait demi-tour
        if not carte.est_solide(tuile_x_verif, tuile_y_verif):
            self.vitesse_patrouille = -self.vitesse_patrouille
            
        # 2. Mouvement horizontal
        dx = self.vitesse_patrouille
            
        # --- Physique (Gravité et Collisions) ---
        
        # 3. Mouvement vertical (gravité)
        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10
        dy = self.vel_y
        
        self.sur_le_sol = False
        
        # 4. Vérification des collisions
        
        # Axe X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                    self.vitesse_patrouille = -self.vitesse_patrouille # Demi-tour
                elif dx < 0:
                    self.rect.left = mur.right
                    self.vitesse_patrouille = -self.vitesse_patrouille # Demi-tour
        
        # Axe Y
        self.rect.y += dy
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dy > 0:
                    self.rect.bottom = mur.top
                    self.vel_y = 0
                    self.sur_le_sol = True
                elif dy < 0:
                    self.rect.top = mur.bottom
                    self.vel_y = 0

    def dessiner(self, surface):
        """Dessine l'ennemi sur l'écran (côté CLIENT)."""
        pygame.draw.rect(surface, self.couleur, self.rect)

    def get_etat(self):
        """Pour l'envoi réseau : renvoie les données essentielles."""
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y
        }

    def set_etat(self, data):
        """Pour la réception réseau : met à jour l'ennemi."""
        self.rect.x = data['x']
        self.rect.y = data['y']