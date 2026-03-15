# joueur.py
# Classe définissant le joueur, sa physique et ses actions (combat).

import pygame
import sys
import os
from parametres import *

# Charger le sprite du joueur
def charger_sprite(nom_fichier):
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        path = os.path.join(base_path, 'assets', nom_fichier)
        sprite = pygame.image.load(path)
        return pygame.transform.scale(sprite, (25, 58))
    except Exception as e:
        print(f"Impossible de charger le sprite {nom_fichier}: {e}")
        return None

SPRITES_JOUEURS = [
    charger_sprite('sprite_perso1.png'),
    charger_sprite('sprite_perso2.png'),
    charger_sprite('sprite_perso3.png'),
]

class Joueur:
    def __init__(self, x, y, id, couleur=COULEUR_JOUEUR):
        self.id = id
        self.rect = pygame.Rect(x, y, 25, 58)
        self.couleur = couleur
        self.sprite = SPRITES_JOUEURS[self.id % 3]
        
        # Mouvement
        self.vel_y = 0
        self.sur_le_sol = False
        self.direction = 1  # 1 = Droite, -1 = Gauche
        
        # Santé et Argent
        self.pv = PV_JOUEUR_MAX
        self.pv_max = PV_JOUEUR_MAX
        self.argent = ARGENT_DEPART
        self.dernier_degat_temps = 0

        # Sons — liste des événements sonores à envoyer au client ce tick
        # Le serveur remplit cette liste, le client la lit et joue les sons.
        self.sons_a_jouer = []

        # Mécaniques
        self.dernier_echo_temps = 0
        self.dernier_echo_dir_temps = -COOLDOWN_ECHO_DIR
        self.peut_echo_dir = False
        self.ame_perdue = None
        self.have_key = False
        self.temps_mort = None
        
        # Combat
        self.dernier_attaque_temps = 0
        self.est_en_attaque = False
        self.rect_attaque = None

        # Capacités
        self.peut_double_saut = False
        self.peut_dash = False
        self.a_double_saute = False
        self.dash_disponibles_en_air = DASH_EN_AIR_MAX
        self.dernier_dash_temps = 0
        self.est_en_dash = False
        self.dash_direction = 0
        self.dash_distance_restante = 0
        self.dash_debut_temps = 0
        
        # Commandes
        self.commandes = {'gauche': False, 'droite': False, 'saut': False, 'attaque': False, 'dash': False}
        self.saut_precedent = False

        self.sons_a_jouer = []
        self.sons = {
            'saut':        True,
            'double_saut': True,
            'dash':        True,
            'attaque':     True,
            'degat':       True,
        }

    def appliquer_physique(self, rects_collision):
        """Gère la gravité, le mouvement et les collisions."""
        dx = 0
        dy = 0

        temps_actuel = pygame.time.get_ticks()
        
        if self.est_en_dash:
            if temps_actuel - self.dash_debut_temps >= DUREE_DASH or self.dash_distance_restante <= 0:
                self.est_en_dash = False
                self.dash_distance_restante = 0
            else:
                vitesse_dash = DISTANCE_DASH / (DUREE_DASH / 1000 * FPS)
                deplacement_dash = min(vitesse_dash, self.dash_distance_restante)
                dx = deplacement_dash * self.dash_direction
                self.dash_distance_restante -= abs(deplacement_dash)
                self.vel_y += GRAVITE * 0.3
                if self.vel_y > 10:
                    self.vel_y = 10
                dy = self.vel_y
        else:
            # 1. Activation du Dash
            if self.commandes.get('dash', False) and self.peut_dash:
                peut_dasher = self.sur_le_sol or self.dash_disponibles_en_air > 0
                
                if peut_dasher and (temps_actuel - self.dernier_dash_temps >= COOLDOWN_DASH):
                    if self.commandes['droite']:
                        self.dash_direction = 1
                    elif self.commandes['gauche']:
                        self.dash_direction = -1
                    else:
                        self.dash_direction = self.direction

                    self.est_en_dash = True
                    self.dash_debut_temps = temps_actuel
                    self.dernier_dash_temps = temps_actuel
                    self.dash_distance_restante = DISTANCE_DASH

                    if not self.sur_le_sol:
                        self.dash_disponibles_en_air -= 1

                    self.commandes['dash'] = False
                    # Événement son dash → client
                    self.sons_a_jouer.append('dash')

            # 2. Mouvement horizontal
            if self.commandes['gauche']:
                dx = -VITESSE_JOUEUR
                self.direction = -1
            if self.commandes['droite']:
                dx = VITESSE_JOUEUR
                self.direction = 1

            # 3. Saut et Double Saut
            saut_actuel = self.commandes.get('saut', False)
            if saut_actuel and not self.saut_precedent:
                if self.sur_le_sol:
                    self.vel_y = -FORCE_SAUT
                    self.sur_le_sol = False
                    self.a_double_saute = False
                elif self.peut_double_saut and not self.a_double_saute:
                    self.vel_y = -FORCE_DOUBLE_SAUT
                    self.a_double_saute = True

            self.saut_precedent = saut_actuel

            self.vel_y += GRAVITE
            if self.vel_y > 10:
                self.vel_y = 10
            dy = self.vel_y
        
        ancien_sur_le_sol = self.sur_le_sol
        self.sur_le_sol = False

        # Axe X
        self.rect.x += dx
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                    if self.est_en_dash:
                        self.est_en_dash = False
                        self.dash_distance_restante = 0
                elif dx < 0:
                    self.rect.left = mur.right
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

        if self.sur_le_sol and not ancien_sur_le_sol:
            self.dash_disponibles_en_air = DASH_EN_AIR_MAX
            # Son d'atterrissage
            if self.sons.get('saut'):
                self.sons_a_jouer.append('saut')

    def gerer_attaque(self, temps_actuel):
        """Gère la logique d'attaque (création hitbox, cooldown)."""
        if self.commandes['attaque'] and (temps_actuel - self.dernier_attaque_temps > COOLDOWN_ATTAQUE):
            self.est_en_attaque = True
            self.dernier_attaque_temps = temps_actuel
            self.commandes['attaque'] = False
            # Événement son attaque → client
            self.sons_a_jouer.append('attaque')
            return True

        if self.est_en_attaque:
            if temps_actuel - self.dernier_attaque_temps > DUREE_ATTAQUE:
                self.est_en_attaque = False
                self.rect_attaque = None

        if self.est_en_attaque:
            if self.direction == 1:
                self.rect_attaque = pygame.Rect(self.rect.right, self.rect.y, PORTEE_ATTAQUE, self.rect.height)
            else:
                self.rect_attaque = pygame.Rect(self.rect.left - PORTEE_ATTAQUE, self.rect.y, PORTEE_ATTAQUE, self.rect.height)

        return False

    def prendre_degat(self, montant, temps_actuel):
        """Tente d'infliger des dégâts au joueur."""
        if temps_actuel - self.dernier_degat_temps > TEMPS_INVINCIBILITE:
            self.pv -= montant
            self.dernier_degat_temps = temps_actuel
            # Événement son dégât → client
            if self.pv <= 0:
                self.sons_a_jouer.append('mort')
            else:
                self.sons_a_jouer.append('degat')
            return True
        return False

    def respawn(self, coords_spawn):
        """Réinitialise le joueur."""
        self.pv = self.pv_max
        self.rect.topleft = coords_spawn
        self.vel_y = 0
        self.sur_le_sol = False

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine le joueur et son attaque par rapport à la caméra."""
        off_x, off_y = camera_offset
        rect_visuel = pygame.Rect(
            self.rect.x - off_x,
            self.rect.y - off_y,
            self.rect.width,
            self.rect.height
        )
        if self.sprite:
            surface.blit(self.sprite, rect_visuel.topleft)
        else:
            pygame.draw.rect(surface, self.couleur, rect_visuel)

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
        etat_attaque = {
            'actif': self.est_en_attaque,
            'rect': (self.rect_attaque.x, self.rect_attaque.y,
                     self.rect_attaque.w, self.rect_attaque.h) if self.rect_attaque else None
        }
        # On vide la liste après envoi pour ne pas rejouer les sons en boucle
        sons = list(self.sons_a_jouer)
        self.sons_a_jouer.clear()

        return {
            'id': self.id,
            'x': self.rect.x,
            'y': self.rect.y,
            'couleur': self.couleur,
            'pv': self.pv,
            'pv_max': self.pv_max,
            'argent': self.argent,
            'attaque': etat_attaque,
            'peut_double_saut': self.peut_double_saut,
            'peut_dash': self.peut_dash,
            'est_en_dash': self.est_en_dash,
            'have_key': self.have_key,
            'peut_echo_dir': self.peut_echo_dir,
            'sons': sons,  # ← liste des sons à jouer ce tick
        }

    def set_etat(self, data):
        """Mise à jour depuis le réseau."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self.couleur = data['couleur']
        self.pv = data['pv']
        self.pv_max = data['pv_max']
        self.argent = data.get('argent', 0)
        self.peut_double_saut = data.get('peut_double_saut', False)
        self.peut_dash = data.get('peut_dash', False)
        self.est_en_dash = data.get('est_en_dash', False)
        self.have_key = data.get('have_key', False)
        self.peut_echo_dir = data.get('peut_echo_dir', False)

        etat_attaque = data.get('attaque')
        if etat_attaque and etat_attaque['actif'] and etat_attaque['rect']:
            self.est_en_attaque = True
            r = etat_attaque['rect']
            self.rect_attaque = pygame.Rect(r[0], r[1], r[2], r[3])
        else:
            self.est_en_attaque = False
            self.rect_attaque = None
        
        # Rejouer les sons reçus du serveur (seulement pour MON joueur, géré dans client.py)
        self.sons_a_jouer = data.get('sons', [])