# ame_perdue.py
# Objet laissé par le joueur à sa mort, contenant son "argent".

import pygame
from parametres import *

class AmePerdue:
    # On utilise un compteur global simple pour les ID
    _prochain_id = 0
    
    def __init__(self, x, y, id_joueur, argent=0):
        self.id = AmePerdue._prochain_id
        AmePerdue._prochain_id += 1
        
        self.rect = pygame.Rect(x, y, 16, 24) # Plus petit qu'un joueur
        self.id_joueur = id_joueur # A qui appartient cette âme
        self.argent = argent # Montant d'argent stocké
        self.couleur = COULEUR_AME_PERDUE
        print(f"Ame {self.id} créée pour Joueur {self.id_joueur} à ({x}, {y})")

    def get_etat(self):
        """Pour l'envoi réseau."""
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'id_joueur': self.id_joueur
        }

    def set_etat(self, data):
        """Pour la réception réseau."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.id_joueur = data['id_joueur']

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine l'âme en tenant compte de la caméra."""
        
        # --- APPLICATION DE LA CAMÉRA ---
        off_x, off_y = camera_offset
        
        # On crée un rectangle temporaire décalé pour l'affichage
        rect_visuel = pygame.Rect(
            self.rect.x - off_x,
            self.rect.y - off_y,
            self.rect.width,
            self.rect.height
        )
        
        pygame.draw.ellipse(surface, self.couleur, rect_visuel)