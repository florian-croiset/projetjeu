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
        
        # Capacités
        self.peut_double_saut = False  # <-- AJOUT
        self.peut_dash = False  # <-- AJOUT
        self.a_double_saute = False  # <-- AJOUT : Pour limiter à 1 double saut
        self.dash_disponibles_en_air = DASH_EN_AIR_MAX  # <-- AJOUT
        self.dernier_dash_temps = 0  # <-- AJOUT
        self.est_en_dash = False  # <-- AJOUT
        self.dash_direction = 0  # <-- AJOUT
        self.dash_distance_restante = 0  # <-- AJOUT
        self.dash_debut_temps = 0  # <-- AJOUT
        
        # Commandes
        self.commandes = {'gauche': False, 'droite': False, 'saut': False, 'attaque': False, 'dash': False}  # <-- MODIFICATION
        # État précédent des commandes (pour détecter les nouveaux appuis)
        self.saut_precedent = False
    def appliquer_physique(self, rects_collision):
        """Gère la gravité, le mouvement et les collisions."""
        dx = 0
        dy = 0

        # --- GESTION DU DASH ---
        temps_actuel = pygame.time.get_ticks()
        
        if self.est_en_dash:
            # Vérifier si le dash est terminé
            if temps_actuel - self.dash_debut_temps >= DUREE_DASH or self.dash_distance_restante <= 0:
                self.est_en_dash = False
                self.dash_distance_restante = 0
            else:
                # Calculer la vitesse du dash pour cette frame
                vitesse_dash = DISTANCE_DASH / (DUREE_DASH / 1000 * FPS)
                deplacement_dash = min(vitesse_dash, self.dash_distance_restante)
                
                dx = deplacement_dash * self.dash_direction
                self.dash_distance_restante -= abs(deplacement_dash)
                
                # Pendant le dash, on ignore les autres mouvements
                # On applique quand même la gravité mais réduite
                self.vel_y += GRAVITE * 0.3
                if self.vel_y > 10:
                    self.vel_y = 10
                dy = self.vel_y
        else:
            # Mouvement normal
            
            # 1. Activation du Dash
            if self.commandes.get('dash', False) and self.peut_dash:
                peut_dasher = False
                
                if self.sur_le_sol:
                    peut_dasher = True
                elif self.dash_disponibles_en_air > 0:
                    peut_dasher = True
                
                if peut_dasher and (temps_actuel - self.dernier_dash_temps >= COOLDOWN_DASH):
                    # Déterminer la direction du dash
                    if self.commandes['droite']:
                        self.dash_direction = 1
                    elif self.commandes['gauche']:
                        self.dash_direction = -1
                    else:
                        self.dash_direction = self.direction  # Direction actuelle
                    
                    # Activer le dash
                    self.est_en_dash = True
                    self.dash_debut_temps = temps_actuel
                    self.dernier_dash_temps = temps_actuel
                    self.dash_distance_restante = DISTANCE_DASH
                    
                    # Consommer un dash en l'air si nécessaire
                    if not self.sur_le_sol:
                        self.dash_disponibles_en_air -= 1
                    
                    # Consommer la commande
                    if 'dash' in self.commandes:
                        self.commandes['dash'] = False
            
            # 2. Mouvement horizontal
            if self.commandes['gauche']:
                dx = -VITESSE_JOUEUR
                self.direction = -1
            if self.commandes['droite']:
                dx = VITESSE_JOUEUR
                self.direction = 1
                
            # 3. Saut et Double Saut
            # 3. Saut et Double Saut
            saut_actuel = self.commandes.get('saut', False)
            
            # Détecter un NOUVEAU front montant (passage de False à True)
            if saut_actuel and not self.saut_precedent:
                if self.sur_le_sol:
                    # Saut normal
                    self.vel_y = -FORCE_SAUT
                    self.sur_le_sol = False
                    self.a_double_saute = False  # Reset du double saut
                elif self.peut_double_saut and not self.a_double_saute:
                    # Double saut
                    self.vel_y = -FORCE_DOUBLE_SAUT
                    self.a_double_saute = True
            
            # Mémoriser l'état actuel pour la prochaine frame
            self.saut_precedent = saut_actuel

            # Gravité
            self.vel_y += GRAVITE
            if self.vel_y > 10: 
                self.vel_y = 10
            dy = self.vel_y
        
        # Reset du flag sur_le_sol
        ancien_sur_le_sol = self.sur_le_sol
        self.sur_le_sol = False 
        
        # 4. Vérification des collisions
        
        # Axe X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                    # Arrêter le dash si collision
                    if self.est_en_dash:
                        self.est_en_dash = False
                        self.dash_distance_restante = 0
                elif dx < 0:
                    self.rect.left = mur.right
                    # Arrêter le dash si collision
                    if self.est_en_dash:
                        self.est_en_dash = False
                        self.dash_distance_restante = 0
        
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
        
        # Réinitialiser les dashs en l'air quand on touche le sol
        if self.sur_le_sol and not ancien_sur_le_sol:
            self.dash_disponibles_en_air = DASH_EN_AIR_MAX
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

    def dessiner(self, surface, camera_offset=(0,0)):
        """Dessine le joueur et son attaque par rapport à la caméra."""
        off_x, off_y = camera_offset
        
        # Création d'un rect temporaire décalé pour l'affichage
        rect_visuel = pygame.Rect(
            self.rect.x - off_x,
            self.rect.y - off_y,
            self.rect.width,
            self.rect.height
        )
        
        pygame.draw.rect(surface, self.couleur, rect_visuel)

        # Dessiner l'attaque si active (carré blanc temporaire)
        if self.est_en_attaque and self.rect_attaque:
            rect_attaque_visuel = pygame.Rect(
                self.rect_attaque.x - off_x,
                self.rect_attaque.y - off_y,
                self.rect_attaque.width,
                self.rect_attaque.height
            )
            pygame.draw.rect(surface, COULEUR_ATTAQUE, rect_attaque_visuel)

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
            'attaque': etat_attaque,
            'peut_double_saut': self.peut_double_saut,  # <-- AJOUT
            'peut_dash': self.peut_dash,  # <-- AJOUT
            'est_en_dash': self.est_en_dash  # <-- AJOUT pour effet visuel
        }

    def set_etat(self, data):
        """Mise à jour depuis le réseau."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.couleur = data['couleur']
        self.pv = data['pv']
        self.pv_max = data['pv_max']
        self.argent = data.get('argent', 0)
        
        # Capacités
        self.peut_double_saut = data.get('peut_double_saut', False)  # <-- AJOUT
        self.peut_dash = data.get('peut_dash', False)  # <-- AJOUT
        self.est_en_dash = data.get('est_en_dash', False)  # <-- AJOUT
        
        # Gestion visuelle de l'attaque distante
        etat_attaque = data.get('attaque')
        if etat_attaque and etat_attaque['actif'] and etat_attaque['rect']:
            self.est_en_attaque = True
            r = etat_attaque['rect']
            self.rect_attaque = pygame.Rect(r[0], r[1], r[2], r[3])
        else:
            self.est_en_attaque = False
            self.rect_attaque = None