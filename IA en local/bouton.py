# bouton.py
# Une classe simple pour gérer les boutons cliquables dans le menu.

import pygame
from parametres import *

class Bouton:
    def __init__(self, x, y, largeur, hauteur, texte, police):
        self.rect = pygame.Rect(x, y, largeur, hauteur)
        self.texte = texte
        self.police = police
        self.couleur_fond = COULEUR_BOUTON
        self.couleur_texte = COULEUR_TEXTE
        self.est_survole = False

    def dessiner(self, surface):
        """Dessine le bouton sur la surface donnée."""
        # Change la couleur si survolé
        couleur_actuelle = COULEUR_BOUTON_SURVOL if self.est_survole else self.couleur_fond
        
        pygame.draw.rect(surface, couleur_actuelle, self.rect, border_radius=8)
        
        # Dessine le texte centré
        texte_surface = self.police.render(self.texte, True, self.couleur_texte)
        texte_rect = texte_surface.get_rect(center=self.rect.center)
        surface.blit(texte_surface, texte_rect)

    def verifier_clic(self, event):
        """Vérifie si le bouton a été cliqué."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def verifier_survol(self, pos_souris):
        """Met à jour l'état 'est_survole'."""
        self.est_survole = self.rect.collidepoint(pos_souris)