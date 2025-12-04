# joueur.py
# Classe définissant le joueur, sa physique et ses actions (combat).

import pygame
from parametres import *

class Joueur:
    def __init__(self, x, y, id, couleur=COULEUR_JOUEUR):
        self.id = id
        self.rect = pygame.Rect(x, y, TAILLE_TUILE - 8, TAILLE_TUILE - 4)
        self.couleur = couleur
        
        # Mouvement
        self.vel_y = 0
        self.sur_le_sol = False
        self.direction = 1 # 1 = Droite, -1 = Gauche
        
        # Santé et Argent
        self.pv = PV_JOUEUR_MAX
        self.pv_max = PV_JOUEUR_MAX
        self.argent = ARGENT_DEPART
        self.dernier_degat_temps = 0 
        
        # Mécaniques
        self.dernier_echo_temps = 0
        self.ame_perdue = None 
        
        # Combat
        self.dernier_attaque_temps = 0
        self.est_en_attaque = False
        self.rect_attaque = None # Hitbox active
        
        # Commandes
        self.commandes = {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}

    def appliquer_physique(self, rects_collision):
        """Gère la gravité, le mouvement et les collisions."""
        dx = 0
        dy = 0

        # 1. Mouvement horizontal
        if self.commandes['gauche']:
            dx = -VITESSE_JOUEUR
            self.direction = -1
        if self.commandes['droite']:
            dx = VITESSE_JOUEUR
            self.direction = 1
            
        # 2. Mouvement vertical
        if self.commandes['saut'] and self.sur_le_sol:
            self.vel_y = -FORCE_SAUT
            self.sur_le_sol = False
            self.commandes['saut'] = False 

        # Gravité
        self.vel_y += GRAVITE
        if self.vel_y > 10: 
            self.vel_y = 10
        dy = self.vel_y
        
        self.sur_le_sol = False 
        
        # 3. Vérification des collisions
        
        # Axe X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                elif dx < 0:
                    self.rect.left = mur.right
        
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

    def gerer_attaque(self, temps_actuel):
        """Gère la logique d'attaque (création hitbox, cooldown)."""
        # Si on demande d'attaquer et que le cooldown est fini
        if self.commandes['attaque'] and (temps_actuel - self.dernier_attaque_temps > COOLDOWN_ATTAQUE):
            self.est_en_attaque = True
            self.dernier_attaque_temps = temps_actuel
            # Créer la hitbox devant le joueur
            if self.direction == 1:
                self.rect_attaque = pygame.Rect(self.rect.right, self.rect.y, PORTEE_ATTAQUE, self.rect.height)
            else:
                self.rect_attaque = pygame.Rect(self.rect.left - PORTEE_ATTAQUE, self.rect.y, PORTEE_ATTAQUE, self.rect.height)
            
            # Consommer la commande (pour ne pas spammer)
            self.commandes['attaque'] = False
            return True # Une attaque vient d'être lancée
            
        # Vérifier si l'attaque est finie
        if self.est_en_attaque:
            if temps_actuel - self.dernier_attaque_temps > DUREE_ATTAQUE:
                self.est_en_attaque = False
                self.rect_attaque = None
                
        return False

    def prendre_degat(self, montant, temps_actuel):
        """Tente d'infliger des dégâts au joueur."""
        if temps_actuel - self.dernier_degat_temps > TEMPS_INVINCIBILITE:
            self.pv -= montant
            self.dernier_degat_temps = temps_actuel
            return True
        return False

    def respawn(self, coords_spawn):
        """Réinitialise le joueur."""
        self.pv = self.pv_max
        self.rect.topleft = coords_spawn
        self.vel_y = 0
        self.sur_le_sol = False
        # On ne reset pas l'argent ici, c'est géré par l'âme perdue

    def dessiner(self, surface):
        """Dessine le joueur et son attaque."""
        pygame.draw.rect(surface, self.couleur, self.rect)
        
        # Dessiner l'attaque si active (carré blanc temporaire)
        if self.est_en_attaque and self.rect_attaque:
            pygame.draw.rect(surface, COULEUR_ATTAQUE, self.rect_attaque)

    def get_etat(self):
        """Données pour le réseau."""
        # On envoie aussi l'état de l'attaque pour que les autres joueurs la voient
        etat_attaque = {
            'actif': self.est_en_attaque,
            'rect': (self.rect_attaque.x, self.rect_attaque.y, self.rect_attaque.w, self.rect_attaque.h) if self.rect_attaque else None
        }
        
        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'couleur': self.couleur,
            'pv': self.pv,
            'pv_max': self.pv_max,
            'argent': self.argent,
            'attaque': etat_attaque
        }

    def set_etat(self, data):
        """Mise à jour depuis le réseau."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.couleur = data['couleur']
        self.pv = data['pv']
        self.pv_max = data['pv_max']
        self.argent = data.get('argent', 0)
        
        # Gestion visuelle de l'attaque distante
        etat_attaque = data.get('attaque')
        if etat_attaque and etat_attaque['actif'] and etat_attaque['rect']:
            self.est_en_attaque = True
            r = etat_attaque['rect']
            self.rect_attaque = pygame.Rect(r[0], r[1], r[2], r[3])
        else:
            self.est_en_attaque = False
            self.rect_attaque = None