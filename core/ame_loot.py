# ame_loot.py
# Âme de loot : jaillit d'un ennemi tué, se disperse avec physique,
# puis se pose au sol. Le joueur doit marcher dessus pour la ramasser.
# Inspiré du système de geo de Hollow Knight.

import pygame
import math
import random
import os
import sys
from parametres import *


def _charger_sprite_loot():
    """Charge le sprite cristal redimensionné pour les âmes de loot."""
    try:
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.dirname(__file__))
        chemin = os.path.join(base, 'assets', 'cristal_purifié.png')
        img = pygame.image.load(chemin).convert_alpha()
        return pygame.transform.scale(img, (10, 15))
    except Exception as e:
        print(f'[AME_LOOT] Sprite non trouvé : {e}')
        return None


SPRITE_LOOT = None  # Chargé à la première instanciation


class AmeLoot:
    """
    Âme de loot lâchée par un ennemi tué.
    - Phase 'dispersion' : jaillit avec vélocité aléatoire, gravité, rebonds.
    - Phase 'repos' : flotte doucement (sinusoïde), ramassable par contact.
    - Disparaît après DUREE_VIE_AME_LOOT ms une fois posée.
    """

    _prochain_id = 0

    def __init__(self, x, y, valeur=1):
        self.id = AmeLoot._prochain_id
        AmeLoot._prochain_id += 1

        self.valeur = valeur

        # Hitbox (plus petite que AmeLibre)
        w, h = 10, 14
        self.rect = pygame.Rect(x - w // 2, y - h // 2, w, h)

        # Position de base (utilisée en phase repos)
        self.x_base = float(x)
        self.y_base = float(y)

        # Physique de dispersion
        self.vel_x = random.uniform(-VITESSE_BURST_LOOT, VITESSE_BURST_LOOT)
        self.vel_y = random.uniform(-VITESSE_BURST_LOOT, -VITESSE_BURST_LOOT * 0.3)

        # État
        self.phase = 'dispersion'
        self.temps_creation = 0      # mis à jour par le serveur au spawn
        self.temps_repos = None
        self.sur_le_sol = False

        # Animation
        self.phase_anim = (self.id * 0.91) % (2 * math.pi)
        self.couleur = COULEUR_AME_LOOT

        global SPRITE_LOOT
        if SPRITE_LOOT is None:
            SPRITE_LOOT = _charger_sprite_loot()
        self.sprite = SPRITE_LOOT.copy() if SPRITE_LOOT else None

        # Mode visuel groupé (côté client uniquement) : N sous-âmes décoratives
        # générées avec une RNG seedée par l'id réseau (cohérence multi-clients).
        self.nb_visuels = 0
        self.visuels = []
        self._id_reseau = None

    # ------------------------------------------------------------------
    #  LOGIQUE (appelée par le serveur chaque frame)
    # ------------------------------------------------------------------

    def mettre_a_jour(self, temps_ms, rects_collision):
        """Met à jour la physique ou l'animation selon la phase."""
        if self.phase == 'dispersion':
            self._mettre_a_jour_dispersion(temps_ms, rects_collision)
        else:
            self._mettre_a_jour_repos(temps_ms)

    def _mettre_a_jour_dispersion(self, temps_ms, rects_collision):
        """Physique : gravité, mouvement, rebonds sur murs/sol."""
        # Gravité
        self.vel_y += GRAVITE
        if self.vel_y > 10:
            self.vel_y = 10

        dx = self.vel_x
        dy = self.vel_y

        # Collision X
        self.rect.x += int(dx)
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dx > 0:
                    self.rect.right = mur.left
                elif dx < 0:
                    self.rect.left = mur.right
                self.vel_x *= -REBOND_AMORTISSEMENT

        # Collision Y
        self.sur_le_sol = False
        self.rect.y += int(dy)
        for mur in rects_collision:
            if self.rect.colliderect(mur):
                if dy > 0:
                    self.rect.bottom = mur.top
                    self.sur_le_sol = True
                    self.vel_x *= 0.5  # Friction au sol
                elif dy < 0:
                    self.rect.top = mur.bottom
                self.vel_y *= -REBOND_AMORTISSEMENT

        # Transition vers repos ?
        vitesse = abs(self.vel_x) + abs(self.vel_y)
        temps_ecoule = temps_ms - self.temps_creation
        if (vitesse < SEUIL_REPOS_LOOT and self.sur_le_sol) or temps_ecoule > DUREE_MAX_DISPERSION:
            self.phase = 'repos'
            self.x_base = float(self.rect.centerx)
            self.y_base = float(self.rect.centery)
            self.temps_repos = temps_ms
            self.vel_x = 0
            self.vel_y = 0

    def _mettre_a_jour_repos(self, temps_ms):
        """Flottement sinusoïdal identique à AmeLibre."""
        offset_y = math.sin(temps_ms / 900 + self.phase_anim) * 3.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    def est_expiree(self, temps_ms):
        """True si l'orbe est posée depuis trop longtemps."""
        if self.phase != 'repos' or self.temps_repos is None:
            return False
        return temps_ms - self.temps_repos > DUREE_VIE_AME_LOOT

    # ------------------------------------------------------------------
    #  RÉSEAU
    # ------------------------------------------------------------------

    def get_etat(self):
        """Sérialisation pour envoi au(x) client(s)."""
        return {
            'id':         self.id,
            'x':          self.rect.centerx,
            'y':          self.rect.centery,
            'valeur':     self.valeur,
            'phase':      self.phase,
            'nb_visuels': getattr(self, 'nb_visuels', 0),
        }

    def set_etat(self, data):
        """Mise à jour côté client depuis les données réseau."""
        self.rect.centerx = data['x']
        self.rect.centery = data['y']
        self.valeur = data.get('valeur', 1)
        self.phase = data.get('phase', 'repos')
        nb_visuels = data.get('nb_visuels', 0)
        if nb_visuels > 1 and not self.visuels:
            self._creer_visuels(data['id'], nb_visuels)

    def _creer_visuels(self, id_reseau, nb_visuels):
        """Génère N sous-âmes visuelles avec une RNG seedée par id_reseau,
        afin que tous les clients voient la même gerbe."""
        self.nb_visuels = nb_visuels
        self._id_reseau = id_reseau
        rng = random.Random(id_reseau)
        cx = float(self.rect.centerx)
        cy = float(self.rect.centery)
        for _ in range(nb_visuels):
            self.visuels.append({
                'x':          cx,
                'y':          cy,
                'vx':         rng.uniform(-VITESSE_BURST_LOOT, VITESSE_BURST_LOOT),
                'vy':         rng.uniform(-VITESSE_BURST_LOOT, -VITESSE_BURST_LOOT * 0.3),
                'phase':      'dispersion',
                't_repos':    None,
                'phase_anim': rng.uniform(0, 2 * math.pi),
                'x_base':     cx,
                'y_base':     cy,
            })

    def mettre_a_jour_visuels(self, temps_ms, carte=None):
        """Côté client : physique des sous-âmes décoratives avec collisions
        de la carte locale (sinon elles tombent dans le vide)."""
        if not self.visuels:
            return
        if not self.temps_creation:
            self.temps_creation = temps_ms

        # Hitbox temporaire réutilisée pour les tests de collision
        if not hasattr(self, '_v_rect'):
            self._v_rect = pygame.Rect(0, 0, 6, 6)
        hb = self._v_rect

        for v in self.visuels:
            if v['phase'] == 'dispersion':
                v['vy'] += GRAVITE
                if v['vy'] > 10:
                    v['vy'] = 10

                rects = []
                if carte is not None:
                    hb.center = (int(v['x']), int(v['y']))
                    rects = carte.get_rects_proches(hb)

                # Mouvement X + collision
                v['x'] += v['vx']
                hb.center = (int(v['x']), int(v['y']))
                for mur in rects:
                    if hb.colliderect(mur):
                        if v['vx'] > 0:
                            v['x'] = mur.left - hb.width / 2
                        elif v['vx'] < 0:
                            v['x'] = mur.right + hb.width / 2
                        v['vx'] *= -REBOND_AMORTISSEMENT
                        hb.center = (int(v['x']), int(v['y']))

                # Mouvement Y + collision
                sur_le_sol = False
                v['y'] += v['vy']
                hb.center = (int(v['x']), int(v['y']))
                for mur in rects:
                    if hb.colliderect(mur):
                        if v['vy'] > 0:
                            v['y'] = mur.top - hb.height / 2
                            sur_le_sol = True
                            v['vx'] *= 0.5
                        elif v['vy'] < 0:
                            v['y'] = mur.bottom + hb.height / 2
                        v['vy'] *= -REBOND_AMORTISSEMENT
                        hb.center = (int(v['x']), int(v['y']))

                v['vx'] *= 0.99
                vitesse = abs(v['vx']) + abs(v['vy'])
                t_ecoule = temps_ms - self.temps_creation
                if (vitesse < SEUIL_REPOS_LOOT and sur_le_sol) or t_ecoule > DUREE_MAX_DISPERSION:
                    v['phase'] = 'repos'
                    v['t_repos'] = temps_ms
                    v['x_base'] = v['x']
                    v['y_base'] = v['y']
                    v['vx'] = 0
                    v['vy'] = 0
            else:
                offset_y = math.sin(temps_ms / 900 + v['phase_anim']) * 3.0
                v['y'] = v['y_base'] + offset_y

    # ------------------------------------------------------------------
    #  RENDU (appelé par le client)
    # ------------------------------------------------------------------

    def dessiner(self, surface, camera_offset=(0, 0), temps_ms=0):
        """Dessine l'orbe avec halo pulsant + sprite. En mode groupé,
        dessine les N sous-âmes au lieu de l'âme principale."""
        off_x, off_y = camera_offset
        r, g, b = self.couleur

        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((40, 40), pygame.SRCALPHA)

        if self.visuels:
            for v in self.visuels:
                self._dessiner_un(surface, off_x, off_y,
                                  int(v['x']), int(v['y']),
                                  v['phase_anim'], temps_ms, r, g, b)
        else:
            self._dessiner_un(surface, off_x, off_y,
                              self.rect.centerx, self.rect.centery,
                              self.phase_anim, temps_ms, r, g, b)

    def _dessiner_un(self, surface, off_x, off_y, x_world, y_world,
                     phase_anim, temps_ms, r, g, b):
        cx = x_world - off_x
        cy = y_world - off_y
        pulse = 0.7 + 0.3 * math.sin(temps_ms / 600 + phase_anim)

        self._halo_surf.fill((0, 0, 0, 0))
        for rayon, alpha_base in [(18, 15), (13, 30), (8, 50)]:
            a = int(alpha_base * pulse)
            pygame.draw.ellipse(self._halo_surf, (r, g, b, a),
                                pygame.Rect(20 - rayon, 20 - rayon, rayon * 2, rayon * 2))
        surface.blit(self._halo_surf, (cx - 20, cy - 20))

        if self.sprite:
            alpha = int(180 + 75 * pulse)
            self.sprite.set_alpha(alpha)
            r_spr = self.sprite.get_rect(center=(cx, cy))
            surface.blit(self.sprite, r_spr)
        else:
            pygame.draw.circle(surface, self.couleur, (cx, cy), 5)
