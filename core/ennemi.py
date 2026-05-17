# core/ennemi.py
# Ennemi unifié : tous les ennemis sont des traqueurs (IA d'écoute + chasse).
# La différenciation passe par pv_max ∈ {1, 2, 3} qui pilote aussi le sprite (e1/e2/e3).

import math
import os
import sys
import pygame
from parametres import *
from utils.cache import flip_h, RAYON_AUDITION_TRAQUEUR_SQ

try:
    from core.demon_slime_boss import BossAnimator
except ImportError:
    from demon_slime_boss import BossAnimator


# -----------------------------------------------------------------------
#  Chargement paresseux des animateurs (thread principal uniquement)
# -----------------------------------------------------------------------
def _chemin_asset_ennemi(nom):
    base = sys._MEIPASS if getattr(sys, 'frozen', False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets', nom)


_ANIMATEURS_ENNEMIS = {}
_OFFSET_X_FRAME = {}   # prefix → décalage horizontal du centre du personnage par rapport au centre du frame


def _obtenir_animator_ennemi(prefix):
    """Renvoie un BossAnimator pour 'e1', 'e2' ou 'e3', mis en cache."""
    if prefix in _ANIMATEURS_ENNEMIS:
        return _ANIMATEURS_ENNEMIS[prefix]
    try:
        a = BossAnimator(_chemin_asset_ennemi(f'{prefix}.json'),
                         _chemin_asset_ennemi(f'{prefix}.png'))
        _ANIMATEURS_ENNEMIS[prefix] = a
        # Calcule une fois pour toutes le décalage horizontal du personnage
        # dans le frame (la plupart des sprites Aseprite ne sont pas centrés).
        _OFFSET_X_FRAME[prefix] = _calculer_offset_x(a)
        return a
    except Exception as e:
        print(f"[Ennemi] Animator {prefix} indisponible: {e}")
        return None


def _calculer_offset_x(animator):
    """Renvoie l'offset (en px) du centre des pixels non-transparents
    par rapport au centre du frame, mesuré sur la première frame d'idle.
    Valeur négative => personnage à gauche du centre du frame."""
    try:
        # Prend une animation idle quelconque
        for name, frames in animator.animations.items():
            if 'idle' in name and frames:
                surf, _ = frames[0]
                bbox = surf.get_bounding_rect()  # zone non transparente
                if bbox.width <= 0:
                    return 0
                char_cx = bbox.x + bbox.width / 2
                return char_cx - surf.get_width() / 2
        return 0
    except Exception:
        return 0


# -----------------------------------------------------------------------
#  Configuration par PV
# -----------------------------------------------------------------------
_CONFIG_PAR_PV = {
    1: {'vitesse': 2.0,
        'largeur': TAILLE_TUILE - 12, 'hauteur': TAILLE_TUILE - 8,
        'argent': 8,                  'sprite': 'e1'},
    2: {'vitesse': VITESSE_ENNEMI,
        'largeur': TAILLE_TUILE - 8,  'hauteur': TAILLE_TUILE - 4,
        'argent': ARGENT_PAR_ENNEMI,  'sprite': 'e2'},
    3: {'vitesse': 1.0,
        'largeur': TAILLE_TUILE,      'hauteur': TAILLE_TUILE + 8,
        'argent': 15,                 'sprite': 'e3'},
}

# Couleurs de la barre de vie selon le ratio restant
_COULEUR_PV_PLEIN   = (220, 55,  55)
_COULEUR_PV_MOITIE  = (230, 120, 30)
_COULEUR_PV_BAS     = (240, 200, 20)
_COULEUR_PV_FOND    = (30,  15,  15)
_COULEUR_PV_BORD    = (80,  40,  40)
_COULEUR_COEUR_VIDE = (55,  25,  25)

# Couleur de secours si l'animator est indisponible
_COULEUR_FALLBACK_PAR_PV = {
    1: (210, 90, 90),
    2: COULEUR_ENNEMI,
    3: (140, 25, 25),
}

# -----------------------------------------------------------------------
#  États de la FSM
# -----------------------------------------------------------------------
ETAT_PATROUILLE = 'patrouille'
ETAT_CHASSE     = 'chasse'
ETAT_ATTAQUE    = 'attaque'

# Nombre de frames de chaque animation d'attaque (pour le mapping temps → frame).
_N_FRAMES_ATTAQUE = {
    ('e1', 1): 9,
    ('e2', 1): 11,
    ('e3', 1): 14,
    ('e3', 2): 12,
}


class Ennemi:
    """Ennemi unifié : comportement traqueur + FSM d'attaque + animation."""

    def __init__(self, x, y, id, pv_max=2):
        self.id     = id
        self.pv_max = pv_max
        self.pv     = pv_max

        cfg = _CONFIG_PAR_PV.get(pv_max, _CONFIG_PAR_PV[2])
        self.vitesse_de_base = cfg['vitesse']
        self.argent_drop     = cfg['argent']
        self.sprite_prefix   = cfg['sprite']    # 'e1' | 'e2' | 'e3'
        self.couleur_base    = _COULEUR_FALLBACK_PAR_PV.get(pv_max, COULEUR_ENNEMI)
        self.couleur         = self.couleur_base

        self.rect = pygame.Rect(x, y, cfg['largeur'], cfg['hauteur'])

        # Mouvement
        self.vel_y              = 0
        self.vitesse_patrouille = self.vitesse_de_base
        self.sur_le_sol         = False
        self.en_mouvement       = False
        self.direction          = 1     # 1 droite, -1 gauche

        # Feedback visuel
        self.dernier_coup_recu = 0
        self.clignotement      = False
        self.flash_echo_temps  = 0

        # Sons
        self.sons_a_jouer = []

        # Respawn
        self.x_depart   = x
        self.y_depart   = y
        self.est_mort   = False
        self.temps_mort = None

        # IA traqueur (toujours active)
        self.rayon_audition = RAYON_AUDITION_TRAQUEUR
        self.duree_alerte   = DUREE_ALERTE_TRAQUEUR
        self.vitesse_chasse = VITESSE_CHASSE_TRAQUEUR
        self.etat           = ETAT_PATROUILLE
        self.cible_x        = 0
        self.cible_y        = 0
        self.fin_alerte     = 0

        # FSM d'attaque
        self.dernier_attaque_temps  = -COOLDOWN_ATTAQUE_ENNEMI
        self.est_en_attaque         = False
        self.attaque_debut_ms       = 0
        self.attaque_num            = 1
        self._derniere_attaque_num  = 1
        self.attaque_a_touche       = set()

        # État d'animation (sérialisé sur le réseau)
        self.etat_anim = 'idle'  # 'idle' | 'run' | 'attack' | 'attack1' | 'attack2' | 'death'

        # Animation client (chargée paresseusement depuis dessiner())
        self.animator              = None
        self._anim_charge_tente    = False
        self._anim_frames          = []
        self._anim_courante        = f'{self.sprite_prefix}_idle'
        self._anim_frame_index     = 0
        self._anim_frame_timer_ms  = 0.0
        self._anim_dernier_temps_ms = 0

        # Interpolation (client UDP)
        self._interp_buffer = []

    # ==================================================================
    #  LOGIQUE SERVEUR
    # ==================================================================

    def alerter(self, position_joueur, temps_actuel):
        """Déclenchée par le serveur à l'émission d'un écho joueur.
        Passe en CHASSE si la source est dans le rayon d'audition."""
        px, py = position_joueur
        dx = self.rect.centerx - px
        dy = self.rect.centery - py
        if dx * dx + dy * dy <= RAYON_AUDITION_TRAQUEUR_SQ:
            self.etat       = ETAT_CHASSE
            self.cible_x    = px
            self.cible_y    = py
            self.fin_alerte = temps_actuel + self.duree_alerte
            return True
        return False

    def appliquer_logique(self, rects_collision, carte, joueurs, temps_actuel):
        """Pilotage IA : patrouille → chasse → attaque + physique."""
        # 0. Fin d'alerte → retour patrouille
        if self.etat == ETAT_CHASSE and temps_actuel >= self.fin_alerte:
            self.etat = ETAT_PATROUILLE
            self.vitesse_patrouille = (
                self.vitesse_de_base if self.vitesse_patrouille >= 0
                else -self.vitesse_de_base
            )

        # 1. Fin d'attaque
        if self.etat == ETAT_ATTAQUE and (
            temps_actuel - self.attaque_debut_ms >= self._duree_attaque_courante()
        ):
            self.est_en_attaque = False
            self.attaque_a_touche.clear()
            if temps_actuel < self.fin_alerte:
                self.etat = ETAT_CHASSE
            else:
                self.etat = ETAT_PATROUILLE

        # 2. Déclenchement d'une attaque (depuis CHASSE uniquement)
        if (self.etat == ETAT_CHASSE
                and (temps_actuel - self.dernier_attaque_temps) >= COOLDOWN_ATTAQUE_ENNEMI):
            cible = self._joueur_a_portee(joueurs)
            if cible is not None:
                self._declencher_attaque(cible, temps_actuel)

        # 3. Choix de dx selon l'état
        if self.etat == ETAT_ATTAQUE:
            dx = 0
            self.en_mouvement = False
            self.etat_anim = self._nom_etat_anim_attaque()
        elif self.etat == ETAT_CHASSE:
            dir_x = self.cible_x - self.rect.centerx
            if dir_x > 4:
                dx = self.vitesse_chasse
            elif dir_x < -4:
                dx = -self.vitesse_chasse
            else:
                dx = 0
            if dx != 0:
                self.vitesse_patrouille = dx
                self.direction = 1 if dx > 0 else -1
            self.en_mouvement = dx != 0
            self.etat_anim = 'run' if dx != 0 else 'idle'
        else:  # PATROUILLE
            if self.vitesse_patrouille > 0:
                tuile_x_verif = (self.rect.right + 2) // TAILLE_TUILE
            else:
                tuile_x_verif = (self.rect.left - 2) // TAILLE_TUILE
            tuile_y_verif = (self.rect.bottom + 1) // TAILLE_TUILE
            if not carte.est_solide(tuile_x_verif, tuile_y_verif):
                self.vitesse_patrouille = -self.vitesse_patrouille
            dx = self.vitesse_patrouille
            if dx != 0:
                self.direction = 1 if dx > 0 else -1
            self.en_mouvement = dx != 0
            self.etat_anim = 'run' if dx != 0 else 'idle'

        # 4. Physique (gravité toujours appliquée)
        etait_au_sol = self.sur_le_sol
        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10
        dy = self.vel_y
        self.sur_le_sol = False

        # Collisions X
        self.rect.x += dx
        mur_bloque = False
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                mur_bloque = True
                if dx > 0:
                    self.rect.right = mur.left
                    if self.etat == ETAT_PATROUILLE:
                        self.vitesse_patrouille = -self.vitesse_patrouille
                elif dx < 0:
                    self.rect.left = mur.right
                    if self.etat == ETAT_PATROUILLE:
                        self.vitesse_patrouille = -self.vitesse_patrouille

        # Saut réflexe en chasse contre un mur frontal
        if (mur_bloque and etait_au_sol
                and self.etat == ETAT_CHASSE and self.vel_y >= 0):
            self.vel_y = -FORCE_SAUT_TRAQUEUR
            dy = self.vel_y

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

        # 5. Mort (prioritaire pour l'animation)
        if self.est_mort:
            self.etat_anim = 'death'

    def prendre_degat(self, montant, temps_actuel) -> bool:
        self.pv -= montant
        self.dernier_coup_recu = temps_actuel
        self.clignotement      = True
        if self.pv <= 0:
            self.est_mort   = True
            self.temps_mort = temps_actuel
            self.sons_a_jouer.append('ennemi_mort')
            self.etat_anim  = 'death'
            self.est_en_attaque = False
            self.attaque_a_touche.clear()
            return True
        self.sons_a_jouer.append('ennemi_degat')
        return False

    def respawn(self):
        self.rect.topleft       = (self.x_depart, self.y_depart)
        self.pv                 = self.pv_max
        self.vel_y              = 0
        self.sur_le_sol         = False
        self.est_mort           = False
        self.temps_mort         = None
        self.clignotement       = False
        self.sons_a_jouer       = []
        self.vitesse_patrouille = self.vitesse_de_base
        self.etat               = ETAT_PATROUILLE
        self.fin_alerte         = 0
        self.est_en_attaque     = False
        self.attaque_a_touche.clear()
        self.attaque_debut_ms   = 0
        self.etat_anim          = 'idle'
        # Réinitialise l'animation client si présente
        self._anim_courante     = f'{self.sprite_prefix}_idle'
        self._anim_frame_index  = 0
        self._anim_frame_timer_ms = 0.0
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_courante)
            except KeyError:
                self._anim_frames = []

    # ------------------------------------------------------------------
    #  Helpers d'attaque
    # ------------------------------------------------------------------

    def _joueur_a_portee(self, joueurs):
        """Joueur vivant le plus proche dans la fenêtre d'attaque, sinon None."""
        candidats = []
        for j in joueurs.values():
            if j.pv <= 0:
                continue
            dx = abs(j.rect.centerx - self.rect.centerx)
            dy = abs(j.rect.centery - self.rect.centery)
            if dx <= PORTEE_ATTAQUE_ENNEMI and dy <= PORTEE_ATTAQUE_ENNEMI_VERT:
                candidats.append((dx * dx + dy * dy, j))
        if not candidats:
            return None
        candidats.sort(key=lambda t: t[0])
        return candidats[0][1]

    def _declencher_attaque(self, cible, temps_actuel):
        self.etat = ETAT_ATTAQUE
        self.est_en_attaque         = True
        self.attaque_debut_ms       = temps_actuel
        self.dernier_attaque_temps  = temps_actuel
        self.attaque_a_touche.clear()
        # Direction figée vers la cible au moment du lancement
        self.direction = 1 if cible.rect.centerx >= self.rect.centerx else -1
        # Alternance attack1/attack2 (e3 uniquement)
        if self.sprite_prefix == 'e3':
            self._derniere_attaque_num = 2 if self._derniere_attaque_num == 1 else 1
            self.attaque_num = self._derniere_attaque_num
        else:
            self.attaque_num = 1
        self.sons_a_jouer.append('ennemi_attaque')

    def _nom_etat_anim_attaque(self):
        if self.sprite_prefix == 'e3':
            return f'attack{self.attaque_num}'
        return 'attack'

    def _duree_attaque_courante(self):
        if self.sprite_prefix == 'e1':
            return DUREE_ATTAQUE_E1
        if self.sprite_prefix == 'e2':
            return DUREE_ATTAQUE_E2
        return DUREE_ATTAQUE_E3_A1 if self.attaque_num == 1 else DUREE_ATTAQUE_E3_A2

    def _fenetre_hitbox_active(self):
        if self.sprite_prefix == 'e1':
            return HITBOX_FRAMES_E1
        if self.sprite_prefix == 'e2':
            return HITBOX_FRAMES_E2
        return HITBOX_FRAMES_E3_A1 if self.attaque_num == 1 else HITBOX_FRAMES_E3_A2

    def hitbox_actif(self, temps_actuel):
        """True si l'instant tombe dans la fenêtre active de l'attaque en cours."""
        if not self.est_en_attaque:
            return False
        elapsed = temps_actuel - self.attaque_debut_ms
        duree   = self._duree_attaque_courante()
        if duree <= 0:
            return False
        f0, f1 = self._fenetre_hitbox_active()
        key = (self.sprite_prefix, self.attaque_num if self.sprite_prefix == 'e3' else 1)
        n_frames = _N_FRAMES_ATTAQUE.get(key, 9)
        idx = min(n_frames - 1, int((elapsed / duree) * n_frames))
        return f0 <= idx <= f1

    def get_rect_hitbox_attaque(self):
        p = PORTEE_ATTAQUE_ENNEMI
        if self.direction == 1:
            return pygame.Rect(self.rect.right, self.rect.y, p, self.rect.height)
        return pygame.Rect(self.rect.left - p, self.rect.y, p, self.rect.height)

    # ==================================================================
    #  ANIMATION CLIENT
    # ==================================================================

    def _init_animator(self):
        if self._anim_charge_tente:
            return
        self._anim_charge_tente = True
        self.animator = _obtenir_animator_ennemi(self.sprite_prefix)
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_courante)
            except KeyError:
                self.animator = None
                self._anim_frames = []

    def _determiner_animation(self):
        p = self.sprite_prefix
        if self.est_mort or self.pv <= 0:
            return f'{p}_death'
        if self.est_en_attaque:
            if p == 'e3':
                return f'{p}_attack{self.attaque_num}'
            return f'{p}_attack'
        if self.etat_anim == 'run':
            return f'{p}_run'
        return f'{p}_idle'

    def _mettre_a_jour_animation(self):
        temps = pygame.time.get_ticks()
        if self._anim_dernier_temps_ms == 0:
            self._anim_dernier_temps_ms = temps
            return
        dt_ms = min(temps - self._anim_dernier_temps_ms, 100)
        self._anim_dernier_temps_ms = temps

        anim_voulue = self._determiner_animation()

        if anim_voulue != self._anim_courante:
            est_attaque_en_cours = '_attack' in self._anim_courante
            haute_priorite       = anim_voulue.endswith('_death')
            attaque_pas_finie    = (est_attaque_en_cours and self._anim_frames and
                                    self._anim_frame_index < len(self._anim_frames) - 1)
            if attaque_pas_finie and not haute_priorite:
                pass  # laisse l'attaque se terminer
            else:
                self._anim_courante = anim_voulue
                self._anim_frame_index = 0
                self._anim_frame_timer_ms = 0.0
                try:
                    self._anim_frames = self.animator.get_animation(anim_voulue)
                except (KeyError, AttributeError):
                    fallback = f'{self.sprite_prefix}_idle'
                    try:
                        self._anim_frames = self.animator.get_animation(fallback)
                        self._anim_courante = fallback
                    except Exception:
                        self._anim_frames = []
                        return

        if not self._anim_frames:
            return

        # Geler sur la dernière frame de mort
        is_death = self._anim_courante.endswith('_death')
        if is_death and self._anim_frame_index >= len(self._anim_frames) - 1:
            return

        _, frame_duration = self._anim_frames[self._anim_frame_index]
        self._anim_frame_timer_ms += dt_ms
        if self._anim_frame_timer_ms >= frame_duration:
            self._anim_frame_timer_ms -= frame_duration
            next_idx = self._anim_frame_index + 1
            if next_idx >= len(self._anim_frames):
                # Pour _attack : laisse rejouer (la sortie viendra de set_etat / serveur)
                self._anim_frame_index = 0
            else:
                self._anim_frame_index = next_idx

    # ==================================================================
    #  RENDU
    # ==================================================================

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine l'ennemi animé + barre de vie en cœurs. Caché si mort + anim death finie."""
        if self.est_mort:
            # Laisse l'animation death se jouer une fois, puis cache l'ennemi
            if self._anim_courante and self._anim_courante.endswith('_death') \
                    and self._anim_frames \
                    and self._anim_frame_index >= len(self._anim_frames) - 1:
                return
            if not self._anim_courante or not self._anim_courante.endswith('_death'):
                # Pas encore basculé sur death — laisse passer pour l'amorcer
                pass

        if not self._anim_charge_tente:
            self._init_animator()

        # Flash blanc au coup reçu
        flash_actif = False
        if self.clignotement:
            if pygame.time.get_ticks() - self.dernier_coup_recu < 120:
                flash_actif = True
            else:
                self.clignotement = False

        off_x, off_y = camera_offset
        rect_visuel = pygame.Rect(
            self.rect.x - off_x, self.rect.y - off_y,
            self.rect.width, self.rect.height,
        )

        if self.animator and self._anim_frames:
            self._mettre_a_jour_animation()
            frame_surf, _ = self._anim_frames[self._anim_frame_index]
            if self.direction == -1:
                frame_surf = flip_h(frame_surf)
            if flash_actif:
                frame_surf = frame_surf.copy()
                frame_surf.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_ADD)
            sw = frame_surf.get_width()
            sh = frame_surf.get_height()
            # Compensation du décalage du personnage dans le frame Aseprite.
            # offset_in_frame est mesuré sur une frame non flippée ; le signe
            # s'inverse lorsque l'on regarde à gauche.
            offset_in_frame = _OFFSET_X_FRAME.get(self.sprite_prefix, 0)
            adj_x = -offset_in_frame * self.direction
            draw_x = self.rect.centerx - off_x - sw // 2 + int(adj_x)
            draw_y = self.rect.centery - off_y - sh + 25
            surface.blit(frame_surf, (draw_x, draw_y))
        else:
            # Fallback : rect plat coloré (anim indisponible)
            if self.est_mort:
                return
            couleur = COULEUR_BLANC if flash_actif else self.couleur_base
            pygame.draw.rect(surface, couleur, rect_visuel)

        if MODE_DEV and not self.est_mort:
            pygame.draw.rect(surface, (255, 0, 0), rect_visuel, 1)
            atk = self.get_rect_hitbox_attaque()
            atk_visuel = pygame.Rect(
                atk.x - off_x, atk.y - off_y, atk.width, atk.height,
            )
            pygame.draw.rect(surface, (255, 140, 0), atk_visuel, 1)


    def _dessiner_coeurs(self, surface, rect_visuel):
        coeur_w    = 7
        coeur_h    = 6
        espacement = 3
        marge_bas  = 4

        total_w = self.pv_max * coeur_w + (self.pv_max - 1) * espacement

        if (not hasattr(self, '_cache_pv_val')
                or self._cache_pv_val != self.pv
                or self._cache_pv_max != self.pv_max):
            self._cache_pv_val = self.pv
            self._cache_pv_max = self.pv_max
            self._cache_barre_pv = pygame.Surface((total_w + 1, coeur_h + 1), pygame.SRCALPHA)
            surf = self._cache_barre_pv

            ratio = self.pv / self.pv_max if self.pv_max > 0 else 0
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

    # ==================================================================
    #  RÉSEAU
    # ==================================================================

    def get_etat(self) -> dict:
        sons = list(self.sons_a_jouer)
        self.sons_a_jouer.clear()
        return {
            'id':                self.id,
            'pv_max':            self.pv_max,
            'x':                 self.rect.x,
            'y':                 self.rect.y,
            'pv':                self.pv,
            'est_mort':          self.est_mort,
            'clignotement':      self.clignotement,
            'flash_echo_temps':  self.flash_echo_temps,
            'sons':              sons,
            # Animation
            'direction':         self.direction,
            'etat_anim':         self.etat_anim,
            'attaque_num':       self.attaque_num,
            'attaque_debut_ms':  self.attaque_debut_ms,
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
        self.direction        = data.get('direction', self.direction)

        nouveau_etat_anim   = data.get('etat_anim', 'idle')
        nouveau_attaque_num = data.get('attaque_num', 1)
        nouveau_debut       = data.get('attaque_debut_ms', 0)

        # Détection d'un nouveau déclenchement d'attaque (timestamp serveur strictement plus grand)
        if (nouveau_etat_anim.startswith('attack')
                and nouveau_debut != self.attaque_debut_ms):
            self.attaque_debut_ms = nouveau_debut
            self.attaque_num      = nouveau_attaque_num
            self.est_en_attaque   = True
        elif not nouveau_etat_anim.startswith('attack'):
            # Le serveur a quitté l'état d'attaque
            self.est_en_attaque = False

        self.etat_anim    = nouveau_etat_anim
        self.attaque_num  = nouveau_attaque_num

        if self.clignotement:
            self.dernier_coup_recu = pygame.time.get_ticks()

    # ==================================================================
    #  INTERPOLATION (client UDP)
    # ==================================================================

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
#  Alias rétro-compat : tout ennemi est un traqueur.
# -----------------------------------------------------------------------
EnemyTraqueur = Ennemi
