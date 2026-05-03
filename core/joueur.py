# joueur.py
# Classe définissant le joueur, sa physique et ses actions (combat).

import pygame
import sys
import os

from parametres import *

# Import de BossAnimator pour réutiliser le même système d'animation
try:
    from core.demon_slime_boss import BossAnimator
    _ANIMATOR_DISPONIBLE = True
except ImportError:
    try:
        from demon_slime_boss import BossAnimator
        _ANIMATOR_DISPONIBLE = True
    except ImportError:
        _ANIMATOR_DISPONIBLE = False
        BossAnimator = None


def _chemin_asset(nom_fichier):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'assets', nom_fichier)


# Cache global (uniquement pour les chargements réussis depuis le thread principal)
_ANIMATEURS_CACHE = {}


def _obtenir_animator(prefix):
    """Charge et retourne un BossAnimator mis en cache pour p1 ou p2.
    Ne met en cache qu'en cas de succès pour permettre les retentatives."""
    if prefix in _ANIMATEURS_CACHE:
        return _ANIMATEURS_CACHE[prefix]
    if not _ANIMATOR_DISPONIBLE:
        return None
    try:
        animator = BossAnimator(
            _chemin_asset(f'{prefix}.json'),
            _chemin_asset(f'{prefix}.png')
        )
        _ANIMATEURS_CACHE[prefix] = animator
        return animator
    except Exception as e:
        print(f"[Joueur] Animation {prefix} non disponible: {e}")
        return None


# Charger le sprite de secours du joueur (utilisé si l'animator échoue)
def charger_sprite(nom_fichier):
    try:
        path = _chemin_asset(nom_fichier)
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

_SKINS = {
    0: ('p1', 0),   # animations p1 + sprite_perso1
    1: ('p2', 1),   # animations p2 + sprite_perso2
    2: ('p1', 2),   # animations p1 + sprite_perso3
}
NB_SKINS = len(_SKINS)
_NOMS_SKINS = {0: "Éclaireur", 1: "Spectre", 2: "Rôdeur"}

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
        self.en_mouvement = False

        # Santé et Argent
        self.pv = PV_JOUEUR_MAX
        self.pv_max = PV_JOUEUR_MAX
        self.argent = ARGENT_DEPART
        self.dernier_degat_temps = 0
        self.est_en_degat = False

        # Sons — liste des événements sonores à envoyer au client ce tick
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
        # Hit registry : IDs des ennemis déjà touchés lors de l'attaque en cours.
        self.ennemis_touches: set = set()

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

        # Interpolation (côté client pour les joueurs distants en mode UDP)
        self._interp_buffer = []

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

        # ── Animations ──────────────────────────────────────────────────────
        # Joueurs pairs (0, 2) → p1 ; joueurs impairs (1) → p2
        self.skin = 0
        self.pseudo = ""
        self._appliquer_skin(0)

        # Chargement paresseux : l'animator est None jusqu'au premier dessiner()
        # (évite d'appeler pygame.image.load depuis le thread serveur)
        self.animator = None
        self._anim_charge_tente = False
        self._anim_frames = []
        self._anim_courante = f'{self._anim_prefix}_idle'
        self._anim_frame_index = 0
        self._anim_frame_timer_ms = 0.0
        self._anim_dernier_temps_ms = 0
        # Alternance attack1 / attack2
        self._derniere_attaque_num = 1
        self._attaque_etait_active = False
        # Prédiction côté client : timestamp local du dernier déclenchement d'attaque
        self._attaque_local_debut_ms = -DUREE_ATTAQUE

    def _appliquer_skin(self, skin):
        prefix, sprite_idx = _SKINS.get(skin, ('p1', 0))
        self._anim_prefix = prefix
        self.sprite = SPRITES_JOUEURS[sprite_idx % len(SPRITES_JOUEURS)]
        self._anim_courante = f'{prefix}_idle'
        self._anim_charge_tente = False
        self.animator = None
        self._anim_frames = []
        self._attaque_etait_active = False

    # ──────────────────────────────────────────────────────────────────────
    #  PHYSIQUE
    # ──────────────────────────────────────────────────────────────────────

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

        # Suivi du mouvement horizontal pour l'animation
        self.en_mouvement = dx != 0

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
            if self.sons.get('saut'):
                self.sons_a_jouer.append('saut')

    def gerer_attaque(self, temps_actuel):
        """Gère la logique d'attaque (création hitbox, cooldown)."""
        if self.commandes['attaque'] and (temps_actuel - self.dernier_attaque_temps > COOLDOWN_ATTAQUE):
            self.est_en_attaque = True
            self.dernier_attaque_temps = temps_actuel
            self.commandes['attaque'] = False
            return True

        if self.est_en_attaque:
            if temps_actuel - self.dernier_attaque_temps > DUREE_ATTAQUE:
                self.est_en_attaque = False
                self.rect_attaque = None
                self.ennemis_touches.clear()

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
        # Réinitialise l'animation pour sortir de l'état mort
        self._anim_courante = f'{self._anim_prefix}_idle'
        self._anim_frame_index = 0
        self._anim_frame_timer_ms = 0.0
        self._attaque_etait_active = False
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_courante)
            except KeyError:
                pass

    # ──────────────────────────────────────────────────────────────────────
    #  ANIMATION
    # ──────────────────────────────────────────────────────────────────────

    def _init_animator(self):
        """Chargement paresseux de l'animator (à appeler depuis le thread principal)."""
        if self._anim_charge_tente:
            return
        self._anim_charge_tente = True
        self.animator = _obtenir_animator(self._anim_prefix)
        if self.animator:
            try:
                self._anim_frames = self.animator.get_animation(self._anim_courante)
            except KeyError:
                self.animator = None
                self._anim_frames = []

    def _determiner_animation(self):
        """Retourne le nom de l'animation à jouer selon l'état courant du joueur."""
        p = self._anim_prefix

        if self.pv <= 0:
            return f'{p}_death'

        if self.est_en_degat:
            return f'{p}_hurt'

        # Prédiction locale : l'attaque est active si le serveur le confirme OU
        # si le joueur a appuyé sur la touche il y a moins de DUREE_ATTAQUE ms.
        est_en_attaque = (self.est_en_attaque or
                          pygame.time.get_ticks() - self._attaque_local_debut_ms < DUREE_ATTAQUE)

        # Détection début d'attaque pour alterner attack1 / attack2
        if est_en_attaque and not self._attaque_etait_active:
            self._derniere_attaque_num = 2 if self._derniere_attaque_num == 1 else 1
        self._attaque_etait_active = est_en_attaque

        if est_en_attaque:
            return f'{p}_attack{self._derniere_attaque_num}'

        if not self.sur_le_sol:
            return f'{p}_jump'

        if self.en_mouvement or self.est_en_dash:
            return f'{p}_run'

        return f'{p}_idle'

    def _mettre_a_jour_animation(self):
        """Avance l'animation d'une frame selon le temps écoulé."""
        temps = pygame.time.get_ticks()
        if self._anim_dernier_temps_ms == 0:
            self._anim_dernier_temps_ms = temps
            return
        dt_ms = min(temps - self._anim_dernier_temps_ms, 100)
        self._anim_dernier_temps_ms = temps

        anim_voulue = self._determiner_animation()

        if anim_voulue != self._anim_courante:
            # Ne pas interrompre une animation d'attaque avant sa dernière frame,
            # sauf pour mort ou blessure qui ont la priorité absolue.
            est_attaque_en_cours = '_attack' in self._anim_courante
            haute_priorite = anim_voulue.endswith('_death') or anim_voulue.endswith('_hurt')
            attaque_pas_finie = (est_attaque_en_cours and self._anim_frames and
                                 self._anim_frame_index < len(self._anim_frames) - 1)

            if attaque_pas_finie and not haute_priorite:
                pass  # on laisse l'animation d'attaque se terminer
            else:
                self._anim_courante = anim_voulue
                self._anim_frame_index = 0
                self._anim_frame_timer_ms = 0.0
                try:
                    self._anim_frames = self.animator.get_animation(anim_voulue)
                except (KeyError, AttributeError):
                    # Animation inconnue : repli sur idle
                    fallback = f'{self._anim_prefix}_idle'
                    try:
                        self._anim_frames = self.animator.get_animation(fallback)
                        self._anim_courante = fallback
                    except Exception:
                        self._anim_frames = []
                        return

        if not self._anim_frames:
            return

        # Geler sur la dernière frame de mort
        is_death = (self._anim_courante == f'{self._anim_prefix}_death')
        if is_death and self._anim_frame_index >= len(self._anim_frames) - 1:
            return

        _, frame_duration = self._anim_frames[self._anim_frame_index]
        self._anim_frame_timer_ms += dt_ms

        if self._anim_frame_timer_ms >= frame_duration:
            self._anim_frame_timer_ms -= frame_duration
            next_idx = self._anim_frame_index + 1
            if next_idx >= len(self._anim_frames):
                self._anim_frame_index = 0  # boucle (sauf mort, géré ci-dessus)
            else:
                self._anim_frame_index = next_idx

    # ──────────────────────────────────────────────────────────────────────
    #  RENDU
    # ──────────────────────────────────────────────────────────────────────

    def dessiner(self, surface, camera_offset=(0, 0)):
        """Dessine le joueur animé (ou un rectangle de secours) et sa hitbox d'attaque."""
        off_x, off_y = camera_offset

        # Chargement paresseux de l'animator (sûr car appelé depuis le thread principal)
        if not self._anim_charge_tente:
            self._init_animator()

        if self.animator and self._anim_frames:
            self._mettre_a_jour_animation()

            frame_surf, _ = self._anim_frames[self._anim_frame_index]

            # Miroir horizontal quand le joueur regarde à gauche
            if self.direction == -1:
                frame_surf = pygame.transform.flip(frame_surf, True, False)

            sprite_w = frame_surf.get_width()
            sprite_h = frame_surf.get_height()

            # Centré horizontalement sur la hitbox, aligné en bas
            draw_x = self.rect.x - off_x + (self.rect.w - sprite_w) // 2
            draw_y = self.rect.y - off_y + self.rect.h - sprite_h

            surface.blit(frame_surf, (draw_x, draw_y))

        elif self.sprite:
            # Fallback : sprite statique mis à l'échelle
            sprite_a_dessiner = pygame.transform.flip(self.sprite, self.direction == -1, False)
            surface.blit(sprite_a_dessiner, (self.rect.x - off_x, self.rect.y - off_y))
        else:
            # Dernier recours : rectangle coloré
            rect_visuel = pygame.Rect(
                self.rect.x - off_x, self.rect.y - off_y,
                self.rect.width, self.rect.height
            )
            pygame.draw.rect(surface, self.couleur, rect_visuel)

        if self.pseudo:
            if not hasattr(Joueur, '_font_pseudo'):
                Joueur._font_pseudo = pygame.font.Font(None, 14)  # petite taille car la surface sera zoomée
            pseudo_surf = Joueur._font_pseudo.render(self.pseudo, True, (210, 235, 255))
            px = self.rect.centerx - off_x - pseudo_surf.get_width() // 2
            py = self.rect.top - off_y - pseudo_surf.get_height() - 2
            bg = pygame.Surface((pseudo_surf.get_width() + 6, pseudo_surf.get_height() + 2), pygame.SRCALPHA)
            bg.fill((0, 0, 10, 160))
            surface.blit(bg, (px - 3, py - 1))
            surface.blit(pseudo_surf, (px, py))

    # ──────────────────────────────────────────────────────────────────────
    #  RÉSEAU
    # ──────────────────────────────────────────────────────────────────────

    def get_etat(self):
        """Données pour le réseau."""
        etat_attaque = {
            'actif': self.est_en_attaque,
            'rect': (self.rect_attaque.x, self.rect_attaque.y,
                     self.rect_attaque.w, self.rect_attaque.h) if self.rect_attaque else None
        }
        sons = list(self.sons_a_jouer)
        self.sons_a_jouer.clear()

        temps_actuel = pygame.time.get_ticks()
        est_en_degat = bool(
            self.dernier_degat_temps > 0 and
            temps_actuel - self.dernier_degat_temps < TEMPS_INVINCIBILITE
        )

        return {
            'id':                self.id,
            'x':                 self.rect.x,
            'y':                 self.rect.y,
            'direction':         self.direction,
            'couleur':           self.couleur,
            'pv':                self.pv,
            'pv_max':            self.pv_max,
            'argent':            self.argent,
            'attaque':           etat_attaque,
            'peut_double_saut':  self.peut_double_saut,
            'peut_dash':         self.peut_dash,
            'est_en_dash':       self.est_en_dash,
            'have_key':          self.have_key,
            'peut_echo_dir':     self.peut_echo_dir,
            'echo_age_ms':       max(0, pygame.time.get_ticks() - self.dernier_echo_temps),
            'echo_dir_age_ms':   max(0, pygame.time.get_ticks() - self.dernier_echo_dir_temps),
            'sons':              sons,
            # Champs pour les animations côté client
            'sur_le_sol':        self.sur_le_sol,
            'en_mouvement':      self.en_mouvement,
            'est_en_degat':      est_en_degat,
            'pseudo': self.pseudo,
            'skin':   self.skin,
        }

    def set_etat(self, data):
        """Mise à jour depuis le réseau (joueurs distants : applique tout y compris position)."""
        self.rect.x = data['x']
        self.rect.y = data['y']
        self._set_etat_attributs(data)

    def set_etat_local(self, data):
        """Mise à jour depuis le réseau pour le joueur local : ne touche pas à la position."""
        self._set_etat_attributs(data)

    def _set_etat_attributs(self, data):
        self.direction = data.get('direction', 1)
        self.couleur = data['couleur']
        self.pv = data['pv']
        self.pv_max = data['pv_max']
        self.argent = data.get('argent', 0)
        self.peut_double_saut = data.get('peut_double_saut', False)
        self.peut_dash = data.get('peut_dash', False)
        self.est_en_dash = data.get('est_en_dash', False)
        self.have_key = data.get('have_key', False)
        self.peut_echo_dir = data.get('peut_echo_dir', False)
        age = data.get('echo_age_ms')
        if age is not None:
            self.dernier_echo_temps = pygame.time.get_ticks() - age
        age_dir = data.get('echo_dir_age_ms')
        if age_dir is not None:
            self.dernier_echo_dir_temps = pygame.time.get_ticks() - age_dir
        # Champs animation
        self.sur_le_sol  = data.get('sur_le_sol', self.sur_le_sol)
        self.en_mouvement = data.get('en_mouvement', self.en_mouvement)
        self.est_en_degat = data.get('est_en_degat', False)

        etat_attaque = data.get('attaque')
        if etat_attaque and etat_attaque['actif'] and etat_attaque['rect']:
            self.est_en_attaque = True
            r = etat_attaque['rect']
            self.rect_attaque = pygame.Rect(r[0], r[1], r[2], r[3])
        else:
            self.est_en_attaque = False
            self.rect_attaque = None

        self.sons_a_jouer = data.get('sons', [])

        nouveau_skin = data.get('skin', 0)
        if nouveau_skin != self.skin:
            self.skin = nouveau_skin
            self._appliquer_skin(nouveau_skin)
        self.pseudo = data.get('pseudo', self.pseudo)

    # ──────────────────────────────────────────────────────────────────────
    #  INTERPOLATION (client UDP, joueurs distants uniquement)
    # ──────────────────────────────────────────────────────────────────────

    def pousser_snapshot_interp(self, t_serveur_ms: int, x: float, y: float):
        buf = self._interp_buffer
        buf.append((t_serveur_ms, x, y))
        if len(buf) > 4:
            del buf[0]

    def mettre_a_jour_interp(self, t_render_serveur_ms: int):
        """Applique rect.x/y par interpolation linéaire entre les deux snapshots encadrant t_render."""
        buf = self._interp_buffer
        if not buf:
            return
        if len(buf) == 1:
            self.rect.x = int(buf[0][1])
            self.rect.y = int(buf[0][2])
            return
        avant = buf[0]
        apres = buf[-1]
        for i in range(len(buf) - 1):
            if buf[i][0] <= t_render_serveur_ms <= buf[i + 1][0]:
                avant = buf[i]
                apres = buf[i + 1]
                break
        else:
            if t_render_serveur_ms < buf[0][0]:
                self.rect.x = int(buf[0][1]); self.rect.y = int(buf[0][2])
            else:
                self.rect.x = int(buf[-1][1]); self.rect.y = int(buf[-1][2])
            return
        dt = apres[0] - avant[0]
        if dt <= 0:
            self.rect.x = int(apres[1]); self.rect.y = int(apres[2])
            return
        alpha = (t_render_serveur_ms - avant[0]) / dt
        alpha = max(0.0, min(1.0, alpha))
        self.rect.x = int(avant[1] + (apres[1] - avant[1]) * alpha)
        self.rect.y = int(avant[2] + (apres[2] - avant[2]) * alpha)
