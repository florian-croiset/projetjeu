# core/ennemi.py
# Classe définissant un ennemi avec PV variables selon son type.
# Types : 'patrouilleur' (1 PV), 'garde' (2 PV), 'gardien' (3 PV)

import pygame
from parametres import *


# Configuration des types d'ennemis
_CONFIG_ENNEMIS = {
    'patrouilleur': {
        'pv':       1,
        'vitesse':  2.0,               # plus rapide
        'largeur':  TAILLE_TUILE - 12, # plus petit
        'hauteur':  TAILLE_TUILE - 8,
        'couleur':  (200, 80, 80),     # rouge clair
        'argent':   8,
    },
    'garde': {
        'pv':       2,
        'vitesse':  VITESSE_ENNEMI,    # vitesse standard
        'largeur':  TAILLE_TUILE - 8,
        'hauteur':  TAILLE_TUILE - 4,
        'couleur':  COULEUR_ENNEMI,    # rouge standard
        'argent':   ARGENT_PAR_ENNEMI,
    },
    'gardien': {
        'pv':       3,
        'vitesse':  1.0,               # plus lent mais costaud
        'largeur':  TAILLE_TUILE,      # plus grand
        'hauteur':  TAILLE_TUILE + 8,
        'couleur':  (150, 30, 30),     # rouge foncé
        'argent':   15,
    },
}


class Ennemi:
    def __init__(self, x, y, id, type_ennemi='garde'):
        self.id          = id
        self.type_ennemi = type_ennemi

        cfg = _CONFIG_ENNEMIS.get(type_ennemi, _CONFIG_ENNEMIS['garde'])

        self.pv_max     = cfg['pv']
        self.pv         = cfg['pv']
        self.vitesse_de_base = cfg['vitesse']
        self.couleur_base    = cfg['couleur']
        self.argent_drop     = cfg['argent']

        self.rect = pygame.Rect(x, y, cfg['largeur'], cfg['hauteur'])
        self.couleur = self.couleur_base

        # Mouvement
        self.vel_y              = 0
        self.vitesse_patrouille = self.vitesse_de_base
        self.sur_le_sol         = False

        # Feedback visuel dégât
        self.dernier_coup_recu = 0
        self.clignotement      = False
        self.flash_echo_temps  = 0

        # Sons
        self.sons_a_jouer = []

        # Respawn
        self.x_depart  = x
        self.y_depart  = y
        self.est_mort   = False
        self.temps_mort = None

    # ------------------------------------------------------------------
    #  LOGIQUE SERVEUR
    # ------------------------------------------------------------------

    def appliquer_logique(self, rects_collision, carte):
        """Gère la physique et l'IA de patrouille."""
        dx = 0
        dy = 0

        # --- IA Patrouille : détection du vide ---
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
                    self.vel_y      = 0
                    self.sur_le_sol = True
                elif dy < 0:
                    self.rect.top = mur.bottom
                    self.vel_y    = 0

    def prendre_degat(self, montant, temps_actuel) -> bool:
        """Inflige des dégâts. Retourne True si l'ennemi meurt."""
        self.pv -= montant
        self.dernier_coup_recu = temps_actuel
        self.clignotement      = True
        if self.pv <= 0:
            self.est_mort   = True
            self.temps_mort = temps_actuel
            self.sons_a_jouer.append('ennemi_mort')
            return True
        self.sons_a_jouer.append('ennemi_degat')
        return False

    def respawn(self):
        """Réinitialise l'ennemi à sa position de départ."""
        self.rect.topleft   = (self.x_depart, self.y_depart)
        self.pv             = self.pv_max
        self.vel_y          = 0
        self.sur_le_sol     = False
        self.est_mort       = False
        self.temps_mort     = None
        self.clignotement   = False
        self.sons_a_jouer   = []
        self.vitesse_patrouille = self.vitesse_de_base

    # ------------------------------------------------------------------
    #  RENDU CLIENT
    # ------------------------------------------------------------------

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine l'ennemi avec indicateur de PV proportionnel à son type."""
        if self.est_mort:
            return

        couleur = self.couleur_base
        if self.clignotement:
            if pygame.time.get_ticks() - self.dernier_coup_recu < 100:
                couleur = COULEUR_BLANC
            else:
                self.clignotement = False

        off_x, off_y = camera_offset
        rect_visuel = pygame.Rect(
            self.rect.x - off_x,
            self.rect.y - off_y,
            self.rect.width,
            self.rect.height,
        )
        pygame.draw.rect(surface, couleur, rect_visuel)

        # Barre de PV au-dessus (seulement si pv_max > 1 ou si blessé)
        if self.pv_max > 1 or self.pv < self.pv_max:
            self._dessiner_barre_pv(surface, rect_visuel)

    def _dessiner_barre_pv(self, surface, rect_visuel):
        """Petite barre de PV au-dessus de l'ennemi."""
        bar_w  = self.rect.width
        bar_h  = 4
        bar_x  = rect_visuel.x
        bar_y  = rect_visuel.y - bar_h - 2
        ratio  = max(0.0, self.pv / self.pv_max)

        # Fond gris
        pygame.draw.rect(surface, (50, 50, 50),
                         pygame.Rect(bar_x, bar_y, bar_w, bar_h))
        # Remplissage rouge
        if ratio > 0:
            couleur_barre = (200, 50, 50) if ratio > 0.5 else (255, 100, 30)
            pygame.draw.rect(surface, couleur_barre,
                             pygame.Rect(bar_x, bar_y, int(bar_w * ratio), bar_h))

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self) -> dict:
        sons = list(self.sons_a_jouer)
        self.sons_a_jouer.clear()
        return {
            'id':           self.id,
            'type_ennemi':  self.type_ennemi,
            'x':            self.rect.x,
            'y':            self.rect.y,
            'pv':           self.pv,
            'pv_max':       self.pv_max,
            'est_mort':     self.est_mort,
            'clignotement': self.clignotement,
            'flash_echo_temps': self.flash_echo_temps,
            'sons':         sons,
        }

    def set_etat(self, data: dict):
        self.rect.x           = data['x']
        self.rect.y           = data['y']
        self.pv               = data['pv']
        self.pv_max           = data.get('pv_max', self.pv_max)
        self.est_mort         = data.get('est_mort', False)
        self.clignotement     = data.get('clignotement', False)
        self.flash_echo_temps = data.get('flash_echo_temps', 0)
        self.sons_a_jouer     = data.get('sons', [])