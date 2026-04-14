import pygame
import json
from enum import Enum, auto


# ─────────────────────────────────────────────
#  1. ÉTATS DE LA MACHINE À ÉTATS (FSM)
# ─────────────────────────────────────────────

class BossState(Enum):
    """
    Chaque valeur = un état possible du boss.
    La FSM ne peut être que dans UN seul état à la fois.
    """
    IDLE      = auto()   # Le boss attend, ne fait rien
    WALK      = auto()   # Le boss marche vers le joueur
    CLEAVE    = auto()   # Le boss attaque avec sa machette
    TAKE_HIT  = auto()   # Le boss reçoit des dégâts
    DEATH     = auto()   # Le boss est mort (état terminal)


# ─────────────────────────────────────────────
#  2. CHARGEUR D'ANIMATIONS (ASEPRITE JSON)
# ─────────────────────────────────────────────

class BossAnimator:
    """
    Compatible avec le format JSON Aseprite "Hash" (frames = dictionnaire)
    ET "Array" (frames = liste). Détecte automatiquement le format.
    """

    def __init__(self, json_path: str, png_path: str):
        with open(json_path, "r") as f:
            data = json.load(f)

        spritesheet = pygame.image.load(png_path).convert_alpha()

        # ── Normalise les frames en liste ordonnée ───────────────
        # Format Hash  → data["frames"] est un dict  {"d_idle 0.png": {...}, ...}
        # Format Array → data["frames"] est une list [{...}, {...}, ...]
        raw_frames = data["frames"]

        if isinstance(raw_frames, dict):
            # Hash : on trie par le numéro à la fin du nom de fichier
            # "d_idle 0.png" → 0,  "d_walk 3.png" → 3, etc.
            def sort_key(item):
                filename = item[0]  # ex: "d_idle 0.png"
                # Extrait le dernier entier trouvé dans le nom
                import re
                numbers = re.findall(r'\d+', filename)
                return int(numbers[-1]) if numbers else 0

            sorted_items = sorted(raw_frames.items(), key=sort_key)
            # Convertit en liste de dicts avec le champ "filename" ajouté
            self.frames_list = []
            for filename, info in sorted_items:
                entry = dict(info)          # copie du dict de frame
                entry["filename"] = filename
                self.frames_list.append(entry)

        else:
            # Array : déjà une liste, on l'utilise directement
            self.frames_list = raw_frames

        # ── Découpe les frames par tag ───────────────────────────
        self.animations = {}

        for tag in data["meta"]["frameTags"]:
            name      = tag["name"]   # ex: "d_idle"
            idx_start = tag["from"]
            idx_end   = tag["to"]

            frames = []
            for i in range(idx_start, idx_end + 1):
                frame_info = self.frames_list[i]

                r = frame_info["frame"]
                src_rect = pygame.Rect(r["x"], r["y"], r["w"], r["h"])

                frame_surf = pygame.Surface((r["w"], r["h"]), pygame.SRCALPHA)
                frame_surf.blit(spritesheet, (0, 0), src_rect)

                duration_ms = frame_info["duration"]
                frames.append((frame_surf, duration_ms))

            self.animations[name] = frames

    def get_animation(self, name: str):
        if name not in self.animations:
            raise KeyError(
                f"Animation '{name}' introuvable. "
                f"Disponibles : {list(self.animations.keys())}"
            )
        return self.animations[name]


# ─────────────────────────────────────────────
#  3. CLASSE PRINCIPALE DU BOSS
# ─────────────────────────────────────────────

class DemonSlimeBoss:
    """
    Le boss Demon Slime avec FSM complète.

    Utilisation minimale :
        boss = DemonSlimeBoss(400, 300, "demon_slime.json", "assets/demon_slime.png")

        # Dans la boucle de jeu :
        dt = clock.tick(60)
        boss.update(dt, player.rect)
        boss.draw(screen)

        # Quand le joueur attaque :
        if player_sword_rect.colliderect(boss.body_rect):
            boss.take_damage(25)

        # Quand le boss attaque le joueur :
        if boss.attack_hitbox and boss.attack_hitbox.colliderect(player.rect):
            player.take_damage(30)
    """

    # ── Paramètres de comportement (modifie-les librement) ──────
    DETECT_RADIUS   = 300   # Distance (px) de détection du joueur
    ATTACK_RADIUS   = 80    # Distance (px) pour déclencher le cleave
    MOVE_SPEED      = 90    # Vitesse de déplacement (px/seconde)
    MAX_HP          = 300   # Points de vie maximum
    ATTACK_COOLDOWN = 1200  # Délai minimum entre deux cleave (ms)

    # Indices des frames pendant lesquelles la hitbox d'attaque est ACTIVE.
    # Ajuste selon ton animation (ouvre-la dans Aseprite pour compter les frames).
    CLEAVE_ACTIVE_FRAME_START = 9
    CLEAVE_ACTIVE_FRAME_END   = 12

    def __init__(self, x: int, y: int, json_path: str, png_path: str):
        # Position en float pour un mouvement fluide
        self.pos      = pygame.Vector2(x, y)
        self.velocity = pygame.Vector2(0, 0)
        self.sur_le_sol = False 

        # Points de vie
        self.hp = self.MAX_HP

        # True = sprite affiché normalement (vers la droite)
        # False = sprite retourné horizontalement (vers la gauche)
        self.facing_right = True

        # Charge toutes les animations depuis le JSON + PNG
        self.animator = BossAnimator(json_path, png_path)

        # Noms des animations — doivent correspondre aux "name" dans le JSON
        self.ANIM_IDLE     = "d_idle"
        self.ANIM_WALK     = "d_walk"
        self.ANIM_CLEAVE   = "d_cleave"
        self.ANIM_TAKE_HIT = "d_take_hit"
        self.ANIM_DEATH    = "death"

        # État de l'animation courante
        self.current_anim_frames = self.animator.get_animation(self.ANIM_IDLE)
        self.current_frame_index = 0      # Quelle frame afficher maintenant
        self.frame_timer_ms      = 0.0    # Temps accumulé depuis le début de cette frame

        # État de la FSM
        self.state = BossState.IDLE

        # Temps restant avant de pouvoir relancer un cleave (en ms)
        self.attack_cooldown_timer = 0

        # Hitbox d'attaque — None quand le cleave n'est pas en phase active
        self.attack_hitbox = None  # type: pygame.Rect | None

        # Taille du sprite (récupérée depuis la première frame d'idle)
        first_surf, _ = self.current_anim_frames[0]
        self.sprite_w = first_surf.get_width()
        self.sprite_h = first_surf.get_height()

        # Hitbox du corps (mise à jour chaque frame dans update())
        self.body_rect = pygame.Rect(x, y, self.sprite_w, self.sprite_h)

    # ────────────────────────────────────────────────────────────
    #  UPDATE — appelée chaque frame depuis la boucle de jeu
    # ────────────────────────────────────────────────────────────

    def update(self, dt_ms: float, player_rect: pygame.Rect):
        """
        dt_ms      : temps écoulé en millisecondes (= clock.tick())
        player_rect: le pygame.Rect du joueur
        """

        # ── DEATH : on avance l'animation puis on sort ──────────
        if self.state == BossState.DEATH:
            self._update_animation(dt_ms)
            return

        # ── Décrément du cooldown d'attaque ─────────────────────
        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= dt_ms

        # ── Calcul de la distance et direction vers le joueur ───
        player_center = pygame.Vector2(player_rect.centerx, player_rect.centery)
        boss_center   = pygame.Vector2(
            self.pos.x + self.sprite_w / 2,
            self.pos.y + self.sprite_h / 2
        )
        distance_to_player = boss_center.distance_to(player_center)

        # Le boss se retourne selon le côté où se trouve le joueur
        self.facing_right = player_center.x >= boss_center.x

        # ── TRANSITIONS D'ÉTAT ──────────────────────────────────
        # CLEAVE et TAKE_HIT sont "verrouillants" : le boss reste dans
        # cet état jusqu'à la fin de l'animation (gérée dans _on_animation_end)
        if self.state in (BossState.IDLE, BossState.WALK):
            self._decide_next_state(distance_to_player)

        # ── MOUVEMENT ───────────────────────────────────────────────
        if self.state == BossState.WALK:
            self._move_toward_player(player_center, boss_center)
        else:
            self.velocity.x = 0

        # ── GRAVITÉ ─────────────────────────────────────────────────
        # Le boss tombe comme le joueur si il n'est pas sur le sol
        GRAVITE = 0.6
        MAX_CHUTE = 10

        if not self.sur_le_sol:
            self.velocity.y += GRAVITE
            if self.velocity.y > MAX_CHUTE:
                self.velocity.y = MAX_CHUTE
        else:
            self.velocity.y = 0

        # Applique la vélocité
        self.pos.x += self.velocity.x * (dt_ms / 1000.0)
        self.pos.y += self.velocity.y  # Y en px/frame comme ton joueur, pas px/seconde

        # Applique la vélocité (convertit px/s en px/frame avec dt en secondes)
        self.pos += self.velocity * (dt_ms / 1000.0)

        # ── MISE À JOUR DES HITBOXES ────────────────────────────
        hitbox_w = self.sprite_w * 0.15      # 15% de la largeur du sprite
        hitbox_h = int(self.sprite_h * 0.5)  # la moitié de la hauteur du sprite
        hitbox_x = int(self.pos.x) + (self.sprite_w - hitbox_w) // 2  # centré horizontalement
        hitbox_y = int(self.pos.y) + (self.sprite_h - hitbox_h)        # collé en bas du sprite

        self.body_rect = pygame.Rect(hitbox_x, hitbox_y, hitbox_w, hitbox_h)
        self._update_attack_hitbox()

        # ── AVANCEMENT DE L'ANIMATION ───────────────────────────
        self._update_animation(dt_ms)

    # ────────────────────────────────────────────────────────────
    #  DRAW — appelée chaque frame après update()
    # ────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface):
        # Ne dessine plus rien après la fin de l'animation de mort
        if self.state == BossState.DEATH and self._is_last_frame():
            return

        frame_surf, _ = self.current_anim_frames[self.current_frame_index]

        # Retourne le sprite horizontalement (cache pour éviter flip chaque frame)
        if self.facing_right:
            cle_cache = (id(frame_surf), self.facing_right)
            if not hasattr(self, '_cache_flip') or self._cache_flip_cle != cle_cache:
                self._cache_flip = pygame.transform.flip(frame_surf, True, False)
                self._cache_flip_cle = cle_cache
            frame_surf = self._cache_flip

        surface.blit(frame_surf, (int(self.pos.x), int(self.pos.y)))

        # ── Hitboxes de debug (décommente pour tester) ──────────
        pygame.draw.rect(surface, (255, 0, 0), self.body_rect, 1)
        if self.attack_hitbox:
            pygame.draw.rect(surface, (255, 140, 0), self.attack_hitbox, 2)

    # ────────────────────────────────────────────────────────────
    #  API PUBLIQUE
    # ────────────────────────────────────────────────────────────

    def take_damage(self, amount: int):
        """
        Inflige des dégâts au boss.
        Appelle cette méthode quand une attaque du joueur touche body_rect.
        """
        if self.state == BossState.DEATH:
            return  # On ne peut plus tuer un boss déjà mort

        self.hp -= amount

        if self.hp <= 0:
            self.hp = 0
            self._change_state(BossState.DEATH)
        elif self.state != BossState.TAKE_HIT:
            # Interrompt n'importe quel état sauf DEATH et TAKE_HIT lui-même
            self._change_state(BossState.TAKE_HIT)

    @property
    def is_dead(self) -> bool:
        """True une fois que l'animation de mort est complètement terminée."""
        return self.state == BossState.DEATH and self._is_last_frame()

    @property
    def is_attacking(self) -> bool:
        """True pendant les frames actives du cleave — utilise attack_hitbox pour les collisions."""
        return self.attack_hitbox is not None

    # ────────────────────────────────────────────────────────────
    #  MÉTHODES INTERNES (privées)
    # ────────────────────────────────────────────────────────────

    def _decide_next_state(self, distance: float):
        """
        IA autonome du boss
        Comportement :
        - Hors DETECT_RADIUS  → IDLE (attend tranquillement)
        - Dans DETECT_RADIUS  → WALK (poursuite)
        - Dans ATTACK_RADIUS  → CLEAVE si cooldown écoulé
        """
        portee_reelle = int(self.sprite_w * 0.4)

        if distance <= portee_reelle and self.attack_cooldown_timer <= 0:
            # Le joueur est exactement à portée de machette → s'arrête et frappe
            self._change_state(BossState.CLEAVE)

        elif distance <= self.DETECT_RADIUS:
            if distance > portee_reelle:
                # Pas encore à portée → marche vers le joueur
                if self.state != BossState.WALK:
                    self._change_state(BossState.WALK)
            else:
                # À portée mais cooldown pas écoulé → attend sur place
                if self.state != BossState.IDLE:
                    self._change_state(BossState.IDLE)

        else:
            if self.state != BossState.IDLE:
                self._change_state(BossState.IDLE)

    def _move_toward_player(self, player_center: pygame.Vector2,
                         boss_center: pygame.Vector2):
        direction = player_center - boss_center
        if direction.length() > 1:
            direction = direction.normalize()
            # Mouvement uniquement sur X — le boss reste au sol
            self.velocity = pygame.Vector2(direction.x * self.MOVE_SPEED, 0)
        else:
            self.velocity = pygame.Vector2(0, 0)

    def _update_attack_hitbox(self):
        if self.state != BossState.CLEAVE:
            self.attack_hitbox = None
            return

        active = (self.CLEAVE_ACTIVE_FRAME_START
                <= self.current_frame_index
                <= self.CLEAVE_ACTIVE_FRAME_END)

        if active:
            hw = int(self.sprite_w * 0.4)
            hh = int(self.sprite_h * 0.4)
            hy = int(self.pos.y) + int(self.sprite_h * 0.3)

            if self.facing_right:
                # Flippé vers droite → machette sur la moitié gauche du sprite
                hx = int(self.pos.x)
            else:
                # Par défaut vers gauche → machette sur la moitié gauche du sprite
                hx = int(self.pos.x)

            self.attack_hitbox = pygame.Rect(hx, hy, hw, hh)
        else:
            self.attack_hitbox = None

    def _update_animation(self, dt_ms: float):
        """
        Fait avancer l'animation en se basant sur les durées du JSON Aseprite.
        Chaque frame a sa propre durée, ce qui permet des animations non-uniformes.
        """
        if not self.current_anim_frames:
            return

        _, frame_duration = self.current_anim_frames[self.current_frame_index]
        self.frame_timer_ms += dt_ms

        # Dès que le temps accumulé dépasse la durée de la frame courante…
        if self.frame_timer_ms >= frame_duration:
            self.frame_timer_ms -= frame_duration  # reporte le surplus sur la frame suivante
            next_idx = self.current_frame_index + 1

            if next_idx >= len(self.current_anim_frames):
                # Fin de l'animation → logique selon l'état
                self._on_animation_end()
            else:
                self.current_frame_index = next_idx

    def _on_animation_end(self):
        """
        Appelée automatiquement à la fin de chaque animation.
        C'est ici que les états "verrouillants" (CLEAVE, TAKE_HIT) se déverrouillent.
        """
        if self.state == BossState.CLEAVE:
            # Attaque terminée → démarre le cooldown et repose le boss
            self.attack_cooldown_timer = self.ATTACK_COOLDOWN
            self._change_state(BossState.IDLE)

        elif self.state == BossState.TAKE_HIT:
            # Réaction au coup terminée → reprend la logique normale
            self._change_state(BossState.IDLE)

        elif self.state == BossState.DEATH:
            # Reste bloqué sur la toute dernière frame (freeze on death)
            self.current_frame_index = len(self.current_anim_frames) - 1

        else:
            # IDLE et WALK : animation en boucle, on repart à la frame 0
            self.current_frame_index = 0

    def _change_state(self, new_state: BossState):
        """
        Effectue la transition vers un nouvel état :
          1. Met à jour self.state
          2. Charge les frames de la nouvelle animation
          3. Remet les timers à zéro
        """
        if new_state == self.state:
            return

        self.state = new_state

        # Table de correspondance état → nom d'animation dans le JSON
        anim_map = {
            BossState.IDLE:     self.ANIM_IDLE,
            BossState.WALK:     self.ANIM_WALK,
            BossState.CLEAVE:   self.ANIM_CLEAVE,
            BossState.TAKE_HIT: self.ANIM_TAKE_HIT,
            BossState.DEATH:    self.ANIM_DEATH,
        }

        self.current_anim_frames = self.animator.get_animation(anim_map[new_state])
        self.current_frame_index = 0
        self.frame_timer_ms      = 0.0

    def _is_last_frame(self) -> bool:
        """True quand on est sur la dernière frame (état final de DEATH)."""
        return self.current_frame_index >= len(self.current_anim_frames) - 1
    

    def get_etat(self):
        """Sérialise l'état du boss pour l'envoyer au client via le réseau."""
        return {
            'x':             int(self.pos.x),
            'y':             int(self.pos.y),
            'hp':            self.hp,
            'hp_max':        self.MAX_HP,
            'state':         self.state.name,           # ex: "WALK"
            'frame_index':   self.current_frame_index,
            'facing_right':  self.facing_right,
            'is_dead':       self.is_dead,
            'attack_hitbox': (
                (self.attack_hitbox.x, self.attack_hitbox.y,
                self.attack_hitbox.w, self.attack_hitbox.h)
                if self.attack_hitbox else None
            ),
            'body_rect': (
                self.body_rect.x, self.body_rect.y,
                self.body_rect.w, self.body_rect.h
            ),
        }

    def set_etat(self, data):
        """Applique un état reçu du serveur (côté client, lecture seule)."""
        self.pos.x       = data['x']
        self.pos.y       = data['y']
        self.hp          = data['hp']
        self.facing_right = data['facing_right']
        self.current_frame_index = data['frame_index']

        # Synchronise l'animation selon l'état reçu
        state_name = data['state']
        new_state   = BossState[state_name]
        if new_state != self.state:
            self._change_state(new_state)

        r = data['body_rect']
        self.body_rect = pygame.Rect(r[0], r[1], r[2], r[3])

        ah = data['attack_hitbox']
        self.attack_hitbox = pygame.Rect(ah[0], ah[1], ah[2], ah[3]) if ah else None