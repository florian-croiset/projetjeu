# core/ennemi.py
# Classe définissant un ennemi avec PV variables selon son type.
# Types : 'patrouilleur' (1 PV), 'garde' (2 PV), 'gardien' (3 PV)
# Barre de vie sous forme de cœurs discrets, toujours visible pour les ennemis multi-PV.

import math
import pygame
from parametres import *


# -----------------------------------------------------------------------
#  Configuration des types d'ennemis
# -----------------------------------------------------------------------
_CONFIG_ENNEMIS = {
    'patrouilleur': {
        'pv':      1,
        'vitesse': 2.0,
        'largeur': TAILLE_TUILE - 12,
        'hauteur': TAILLE_TUILE - 8,
        'couleur': (210, 90, 90),    # rouge clair / vif
        'argent':  8,
    },
    'garde': {
        'pv':      2,
        'vitesse': VITESSE_ENNEMI,
        'largeur': TAILLE_TUILE - 8,
        'hauteur': TAILLE_TUILE - 4,
        'couleur': COULEUR_ENNEMI,   # rouge standard
        'argent':  ARGENT_PAR_ENNEMI,
    },
    'gardien': {
        'pv':      3,
        'vitesse': 1.0,
        'largeur': TAILLE_TUILE,
        'hauteur': TAILLE_TUILE + 8,
        'couleur': (140, 25, 25),    # rouge sombre / foncé
        'argent':  15,
    },
    'traqueur': {
        'pv':      2,
        'vitesse': 2.0,
        'largeur': TAILLE_TUILE - 8,
        'hauteur': TAILLE_TUILE - 4,
        'couleur': (140, 60, 200),   # violet — IA à l'écoute des échos
        'argent':  12,
    },
}

# Couleurs de la barre de vie selon le ratio restant
_COULEUR_PV_PLEIN   = (220, 55,  55)   # rouge vif — plein
_COULEUR_PV_MOITIE  = (230, 120, 30)   # orange   — à moitié
_COULEUR_PV_BAS     = (240, 200, 20)   # jaune    — presque mort
_COULEUR_PV_FOND    = (30,  15,  15)   # fond très sombre
_COULEUR_PV_BORD    = (80,  40,  40)   # bordure subtile
_COULEUR_COEUR_VIDE = (55,  25,  25)   # icône de PV perdu


class Ennemi:
    def __init__(self, x, y, id, type_ennemi='garde'):
        self.id          = id
        self.type_ennemi = type_ennemi

        cfg = _CONFIG_ENNEMIS.get(type_ennemi, _CONFIG_ENNEMIS['garde'])

        self.pv_max          = cfg['pv']
        self.pv              = cfg['pv']
        self.vitesse_de_base = cfg['vitesse']
        self.couleur_base    = cfg['couleur']
        self.argent_drop     = cfg['argent']

        self.rect   = pygame.Rect(x, y, cfg['largeur'], cfg['hauteur'])
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

        # Interpolation (client UDP)
        self._interp_buffer = []

    # ------------------------------------------------------------------
    #  LOGIQUE SERVEUR
    # ------------------------------------------------------------------

    def appliquer_logique(self, rects_collision, carte):
        """Gère la physique et l'IA de patrouille."""
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
        self.rect.topleft       = (self.x_depart, self.y_depart)
        self.pv                 = self.pv_max
        self.vel_y              = 0
        self.sur_le_sol         = False
        self.est_mort           = False
        self.temps_mort         = None
        self.clignotement       = False
        self.sons_a_jouer       = []
        self.vitesse_patrouille = self.vitesse_de_base

    # ------------------------------------------------------------------
    #  RENDU CLIENT
    # ------------------------------------------------------------------

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine l'ennemi et sa barre de vie en cœurs discrets."""
        if self.est_mort:
            return

        # Flash blanc au coup reçu
        couleur = self.couleur_base
        if self.clignotement:
            if pygame.time.get_ticks() - self.dernier_coup_recu < 120:
                couleur = COULEUR_BLANC
            else:
                self.clignotement = False

        off_x, off_y = camera_offset
        rect_visuel  = pygame.Rect(
            self.rect.x - off_x,
            self.rect.y - off_y,
            self.rect.width,
            self.rect.height,
        )
        pygame.draw.rect(surface, couleur, rect_visuel)

        # Afficher la barre dès que l'ennemi a plus d'1 PV max,
        # OU si un ennemi 1 PV a quand même été touché (sécurité)
        if self.pv_max > 1 or self.pv < self.pv_max:
            self._dessiner_coeurs(surface, rect_visuel)

    def _dessiner_coeurs(self, surface, rect_visuel):
        """
        Barre de vie sous forme de cœurs discrets (cachée par PV).
        """
        coeur_w    = 7
        coeur_h    = 6
        espacement = 3
        marge_bas  = 4

        total_w = self.pv_max * coeur_w + (self.pv_max - 1) * espacement

        # Rebuild le cache seulement si les PV ont changé
        if not hasattr(self, '_cache_pv_val') or self._cache_pv_val != self.pv or self._cache_pv_max != self.pv_max:
            self._cache_pv_val = self.pv
            self._cache_pv_max = self.pv_max
            # Surface avec marge pour l'ombre (+1px)
            self._cache_barre_pv = pygame.Surface((total_w + 1, coeur_h + 1), pygame.SRCALPHA)
            surf = self._cache_barre_pv

            ratio = self.pv / self.pv_max
            if ratio > 0.6:
                couleur_plein = _COULEUR_PV_PLEIN
            elif ratio > 0.35:
                couleur_plein = _COULEUR_PV_MOITIE
            else:
                couleur_plein = _COULEUR_PV_BAS

            for i in range(self.pv_max):
                cx = i * (coeur_w + espacement)
                pygame.draw.rect(surf, (8, 4, 4),
                                 pygame.Rect(cx + 1, 1, coeur_w, coeur_h), border_radius=2)
                pygame.draw.rect(surf, _COULEUR_PV_FOND,
                                 pygame.Rect(cx, 0, coeur_w, coeur_h), border_radius=2)
                if i < self.pv:
                    pygame.draw.rect(surf, couleur_plein,
                                     pygame.Rect(cx, 0, coeur_w, coeur_h), border_radius=2)
                    pygame.draw.rect(surf, (255, 200, 200),
                                     pygame.Rect(cx + 1, 1, coeur_w - 2, 1))
                else:
                    pygame.draw.rect(surf, _COULEUR_COEUR_VIDE,
                                     pygame.Rect(cx, 0, coeur_w, coeur_h), border_radius=2)
                pygame.draw.rect(surf, _COULEUR_PV_BORD,
                                 pygame.Rect(cx, 0, coeur_w, coeur_h), width=1, border_radius=2)

        bx = rect_visuel.centerx - total_w // 2
        by = rect_visuel.top - coeur_h - marge_bas
        surface.blit(self._cache_barre_pv, (bx, by))

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self) -> dict:
        sons = list(self.sons_a_jouer)
        self.sons_a_jouer.clear()
        return {
            'id':               self.id,
            'type_ennemi':      self.type_ennemi,
            'x':                self.rect.x,
            'y':                self.rect.y,
            'pv':               self.pv,
            'pv_max':           self.pv_max,
            'est_mort':         self.est_mort,
            'clignotement':     self.clignotement,
            'flash_echo_temps': self.flash_echo_temps,
            'sons':             sons,
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

    # ------------------------------------------------------------------
    #  INTERPOLATION (client UDP)
    # ------------------------------------------------------------------

    def pousser_snapshot_interp(self, t_serveur_ms: int, x: float, y: float):
        buf = self._interp_buffer
        buf.append((t_serveur_ms, x, y))
        if len(buf) > 4:
            del buf[0]

    def mettre_a_jour_interp(self, t_render_serveur_ms: int):
        buf = self._interp_buffer
        if not buf:
            return
        if len(buf) == 1:
            self.rect.x = int(buf[0][1]); self.rect.y = int(buf[0][2])
            return
        avant = buf[0]; apres = buf[-1]
        for i in range(len(buf) - 1):
            if buf[i][0] <= t_render_serveur_ms <= buf[i + 1][0]:
                avant = buf[i]; apres = buf[i + 1]
                break
        else:
            cible = buf[0] if t_render_serveur_ms < buf[0][0] else buf[-1]
            self.rect.x = int(cible[1]); self.rect.y = int(cible[2])
            return
        dt = apres[0] - avant[0]
        if dt <= 0:
            self.rect.x = int(apres[1]); self.rect.y = int(apres[2])
            return
        alpha = max(0.0, min(1.0, (t_render_serveur_ms - avant[0]) / dt))
        self.rect.x = int(avant[1] + (apres[1] - avant[1]) * alpha)
        self.rect.y = int(avant[2] + (apres[2] - avant[2]) * alpha)


# -----------------------------------------------------------------------
#  Ennemi Traqueur — IA événementielle basée sur le bruit
# -----------------------------------------------------------------------

ETAT_PATROUILLE = 'patrouille'
ETAT_CHASSE     = 'chasse'


class EnemyTraqueur(Ennemi):
    """
    Ennemi aveugle. Patrouille jusqu'à entendre un écho à portée,
    puis chasse la source pendant un temps limité.
    """

    def __init__(self, x, y, id,
                 rayon_audition=RAYON_AUDITION_TRAQUEUR,
                 duree_alerte=DUREE_ALERTE_TRAQUEUR,
                 vitesse_chasse=VITESSE_CHASSE_TRAQUEUR):
        super().__init__(x, y, id, type_ennemi='traqueur')
        self.rayon_audition = rayon_audition
        self.duree_alerte   = duree_alerte
        self.vitesse_chasse = vitesse_chasse
        self.etat           = ETAT_PATROUILLE
        self.cible_x        = 0
        self.cible_y        = 0
        self.fin_alerte     = 0

    def alerter(self, position_joueur, temps_actuel):
        """
        Déclenchée par le serveur à l'émission d'un écho joueur.
        Passe en CHASSE si la source est dans le rayon d'audition.
        """
        px, py = position_joueur
        if math.dist((self.rect.centerx, self.rect.centery), (px, py)) <= self.rayon_audition:
            self.etat       = ETAT_CHASSE
            self.cible_x    = px
            self.cible_y    = py
            self.fin_alerte = temps_actuel + self.duree_alerte
            return True
        return False

    def appliquer_logique(self, rects_collision, carte):
        if self.etat == ETAT_CHASSE and pygame.time.get_ticks() >= self.fin_alerte:
            self.etat = ETAT_PATROUILLE
            self.vitesse_patrouille = (
                self.vitesse_de_base if self.vitesse_patrouille >= 0
                else -self.vitesse_de_base
            )

        if self.etat == ETAT_PATROUILLE:
            super().appliquer_logique(rects_collision, carte)
            return

        # En CHASSE : direction dictée par la cible, sans détection du vide
        # (évite l'oscillation au bord d'un trou pendant la poursuite).
        dir_x = self.cible_x - self.rect.centerx
        if abs(dir_x) > 4:
            dx = self.vitesse_chasse if dir_x > 0 else -self.vitesse_chasse
        else:
            dx = 0
        if dx != 0:
            self.vitesse_patrouille = dx

        # Sauvegarder l'état au sol avant la remise à zéro par la physique
        etait_au_sol = self.sur_le_sol

        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10
        dy = self.vel_y
        self.sur_le_sol = False

        # Collisions X — détection d'un obstacle frontal
        self.rect.x += dx
        mur_bloque = False
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                mur_bloque = True
                if dx > 0:
                    self.rect.right = mur.left
                elif dx < 0:
                    self.rect.left = mur.right

        # Saut réflexe : obstacle frontal + était au sol + pas déjà en l'air
        if mur_bloque and etait_au_sol and self.vel_y >= 0:
            self.vel_y = -FORCE_SAUT_TRAQUEUR
            dy = self.vel_y

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
