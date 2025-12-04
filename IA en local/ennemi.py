# ennemi.py
# Classe définissant un ennemi simple avec PV et gestion des dégâts.

import pygame
from parametres import *

class Ennemi:
    def __init__(self, x, y, id):
        self.id = id
        self.rect = pygame.Rect(x, y, TAILLE_TUILE - 8, TAILLE_TUILE - 4)
        self.couleur = COULEUR_ENNEMI
        
        # Stats
        self.pv = PV_ENNEMI_BASE
        
        # Mouvement
        self.vel_y = 0
        self.vitesse_patrouille = VITESSE_ENNEMI
        self.sur_le_sol = False
        
        # Feedback visuel dégât
        self.dernier_coup_recu = 0
        self.clignotement = False

    def appliquer_logique(self, rects_collision, carte):
        """Gère la physique et l'IA de patrouille."""
        dx = 0
        dy = 0

        # --- IA Patrouille ---
        # 1. Détection du vide
        tuile_x_verif = 0
        if self.vitesse_patrouille > 0:
            tuile_x_verif = (self.rect.right + 2) // TAILLE_TUILE
        else:
            tuile_x_verif = (self.rect.left - 2) // TAILLE_TUILE
            
        tuile_y_verif = (self.rect.bottom + 1) // TAILLE_TUILE
        
        if not carte.est_solide(tuile_x_verif, tuile_y_verif):
            self.vitesse_patrouille = -self.vitesse_patrouille
            
        dx = self.vitesse_patrouille
            
        # --- Physique ---
        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10
        dy = self.vel_y
        
        self.sur_le_sol = False
        
        # Collisions X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                    self.vitesse_patrouille = -self.vitesse_patrouille
                elif dx < 0:
                    self.rect.left = mur.right
                    self.vitesse_patrouille = -self.vitesse_patrouille
        
        # Collisions Y
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

    def prendre_degat(self, montant):
        """Inflige des dégâts à l'ennemi."""
        self.pv -= montant
        self.dernier_coup_recu = pygame.time.get_ticks()
        self.clignotement = True
        return self.pv <= 0

    def dessiner(self, surface):
        """Dessine l'ennemi. Clignote blanc si touché récemment."""
        couleur = self.couleur
        
        if self.clignotement:
            if pygame.time.get_ticks() - self.dernier_coup_recu < 100:
                couleur = COULEUR_BLANC
            else:
                self.clignotement = False
        
        pygame.draw.rect(surface, couleur, self.rect)

    def get_etat(self):
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'pv': self.pv,
            'clignotement': self.clignotement # Pour synchro visuelle
        }

    def set_etat(self, data):
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.pv = data['pv']
        self.clignotement = data.get('clignotement', False)