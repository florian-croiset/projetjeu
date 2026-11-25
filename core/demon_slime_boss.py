import pygame
import json
from enum import Enum, auto
from settings import DEV_MODE
from utils.cache import flip_h


# ─────────────────────────────────────────────
# 1. STATE MACHINE (FSM) STATES
# ─────────────────────────────────────────────

class BossState(Enum):
    """
    Each value = one possible boss state.
    The FSM can only be in ONE state at a time.
    """
    IDLE      = auto()   # The boss waits, does nothing
    WALK      = auto()   # The boss walks towards the player
    CLEAVE    = auto()   # The boss attacks with its machete
    TAKE_HIT  = auto()   # The boss takes damage
    DEATH     = auto()   # The boss is dead (terminal state)


# ─────────────────────────────────────────────
# 2. ANIMATION LOADER (ASEPRITE JSON)
# ─────────────────────────────────────────────

class BossAnimator:
    """
    Compatible with both the Aseprite JSON "Hash" format (frames = dictionary)
    and "Array" (frames = list). The format is detected automatically.
    """

    def __init__(self, json_path: str, png_path: str):
        with open(json_path, "r") as f:
            data = json.load(f)

        spritesheet = pygame.image.load(png_path).convert_alpha()

        # -- Normalise the frames into an ordered list -------------------
        # Hash format  -> data["frames"] is a dict  {"d_idle 0.png": {...}, ...}
        # Array format -> data["frames"] is a list [{...}, {...}, ...]
        raw_frames = data["frames"]

        if isinstance(raw_frames, dict):
            # Hash: sort by the number at the end of the file name
            # "d_idle 0.png" -> 0,  "d_walk 3.png" -> 3, etc.
            def sort_key(item):
                filename = item[0]  # e.g. "d_idle 0.png"
                # Extract the last integer found in the name
                import re
                numbers = re.findall(r'\d+', filename)
                return int(numbers[-1]) if numbers else 0

            sorted_items = sorted(raw_frames.items(), key=sort_key)
            # Convert to a list of dicts with the "filename" field added
            self.frames_list = []
            for filename, info in sorted_items:
                entry = dict(info)          # copy of the frame dict
                entry["filename"] = filename
                self.frames_list.append(entry)

        else:
            # Array: already a list, use it directly
            self.frames_list = raw_frames

        # -- Split the frames by tag -------------------------------------
        self.animations = {}

        for tag in data["meta"]["frameTags"]:
            name      = tag["name"]   # e.g. "d_idle"
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
                f"Animation '{name}' not found. "
                f"Available: {list(self.animations.keys())}"
            )
        return self.animations[name]


# ─────────────────────────────────────────────
# 3. MAIN BOSS CLASS
# ─────────────────────────────────────────────

class DemonSlimeBoss:
    """
    The Demon Slime boss with a complete FSM.

    Minimal usage:
        boss = DemonSlimeBoss(400, 300, "assets/demon_slime.json", "assets/demon_slime.png")

        # In the game loop:
        dt = clock.tick(60)
        boss.update(dt, player.rect)
        boss.draw(screen)

        # When the player attacks:
        if player_sword_rect.colliderect(boss.body_rect):
            boss.take_damage(25)

        # When the boss attacks the player:
        if boss.attack_hitbox and boss.attack_hitbox.colliderect(player.rect):
            player.take_damage(30, now)
    """

    # -- Behaviour parameters (feel free to tweak) --------------------
    DETECT_RADIUS   = 300   # Distance (px) at which the player is detected
    ATTACK_RADIUS   = 80    # Distance (px) at which the cleave is triggered
    # Movement speed (px/second). The position used to be advanced twice per update, so the
    # boss really walked at 2 x 90 px/s; the duplicate was removed and the constant doubled to
    # keep exactly the same in-game speed.
    MOVE_SPEED      = 180
    MAX_HP          = 300   # Maximum hit points
    ATTACK_COOLDOWN      = 1200  # Minimum delay between two cleaves (ms)
    INVINCIBILITY_DURATION = 800  # Invincibility frames after a TAKE_HIT (ms)

    # Indices of the frames during which the attack hitbox is ACTIVE.
    # Adjust to the animation (open it in Aseprite to count the frames).
    CLEAVE_ACTIVE_FRAME_START = 9
    CLEAVE_ACTIVE_FRAME_END   = 12

    def __init__(self, x: int, y: int, json_path: str, png_path: str):
        # Float position for smooth movement
        self.pos      = pygame.Vector2(x, y)
        self.velocity = pygame.Vector2(0, 0)
        self.on_ground = False 

        # Hit points
        self.hp = self.MAX_HP

        # True = sprite drawn as is (facing right)
        # False = sprite flipped horizontally (facing left)
        self.facing_right = True

        # Load every animation from the JSON + PNG
        self.animator = BossAnimator(json_path, png_path)

        # Animation names - must match the "name" entries in the JSON
        self.ANIM_IDLE     = "d_idle"
        self.ANIM_WALK     = "d_walk"
        self.ANIM_CLEAVE   = "d_cleave"
        self.ANIM_TAKE_HIT = "d_take_hit"
        self.ANIM_DEATH    = "death"

        # Current animation state
        self.current_anim_frames = self.animator.get_animation(self.ANIM_IDLE)
        self.current_frame_index = 0      # Which frame to display right now
        self.frame_timer_ms      = 0.0    # Time accumulated since the start of this frame

        # FSM state
        self.state = BossState.IDLE

        # Time left before another cleave may start (ms)
        self.attack_cooldown_timer = 0

        # Invincibility frames after a TAKE_HIT - during this time the boss can no longer
        # be interrupted, so that spamming hits cannot lock out every attack.
        self.invincibility_timer = 0   # in ms

        # Attack hitbox - None while the cleave is not in its active phase
        self.attack_hitbox = None  # type: pygame.Rect | None

        # Sprite size (taken from the first idle frame)
        first_surf, _ = self.current_anim_frames[0]
        self.sprite_w = first_surf.get_width()
        self.sprite_h = first_surf.get_height()

        # Body hitbox (updated every frame in update())
        self.body_rect = pygame.Rect(x, y, self.sprite_w, self.sprite_h)

    # ────────────────────────────────────────────────────────────
    # UPDATE - called every frame from the game loop
    # ────────────────────────────────────────────────────────────

    def update(self, dt_ms: float, player_rect: pygame.Rect):
        """
        dt_ms      : elapsed time in milliseconds
        player_rect: the player's pygame.Rect
        """

        # -- DEATH: advance the animation, then leave ---------------------
        if self.state == BossState.DEATH:
            self._update_animation(dt_ms)
            return

        # -- Attack cooldown countdown -------------------------------------
        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= dt_ms

        if self.invincibility_timer > 0:
            self.invincibility_timer -= dt_ms

        # -- Distance and direction to the player ---------------------------
        player_center = pygame.Vector2(player_rect.centerx, player_rect.centery)
        boss_center   = pygame.Vector2(
            self.pos.x + self.sprite_w / 2,
            self.pos.y + self.sprite_h / 2
        )
        distance_to_player = boss_center.distance_to(player_center)

        # The boss only turns around outside of attacks - during a CLEAVE the
        # direction is locked so that the player can dodge by dashing.
        if self.state in (BossState.IDLE, BossState.WALK):
            self.facing_right = player_center.x >= boss_center.x

        # -- STATE TRANSITIONS --------------------------------------------
        # CLEAVE and TAKE_HIT are "locking": the boss stays in
        # that state until the animation ends (handled in _on_animation_end)
        if self.state in (BossState.IDLE, BossState.WALK):
            self._decide_next_state(distance_to_player)

        # -- MOVEMENT -----------------------------------------------------
        if self.state == BossState.WALK:
            self._move_toward_player(player_center, boss_center)
        else:
            self.velocity.x = 0

        # -- GRAVITY ------------------------------------------------------
        # The boss falls like the player when it is not on the ground
        GRAVITY = 0.6
        MAX_FALL = 10

        if not self.on_ground:
            self.velocity.y += GRAVITY
            if self.velocity.y > MAX_FALL:
                self.velocity.y = MAX_FALL
        else:
            self.velocity.y = 0

        # Apply the velocity: x in px/second (scaled by dt), y in px per update like the player
        self.pos.x += self.velocity.x * (dt_ms / 1000.0)
        self.pos.y += self.velocity.y


        # -- HITBOX UPDATE -----------------------------------------------
        hitbox_w = self.sprite_w * 0.15      # 15% of the sprite width
        hitbox_h = int(self.sprite_h * 0.5)  # half of the sprite height
        hitbox_x = int(self.pos.x) + (self.sprite_w - hitbox_w) // 2  # centered horizontally
        hitbox_y = int(self.pos.y) + (self.sprite_h - hitbox_h)        # stuck to the bottom of the sprite

        self.body_rect = pygame.Rect(hitbox_x, hitbox_y, hitbox_w, hitbox_h)
        self._update_attack_hitbox()

        # -- ANIMATION ADVANCE -------------------------------------------
        self._update_animation(dt_ms)

    # ────────────────────────────────────────────────────────────
    # DRAW - called every frame after update()
    # ────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface):
        # Draw nothing once the death animation has finished
        if self.state == BossState.DEATH and self._is_last_frame():
            return

        frame_surf, _ = self.current_anim_frames[self.current_frame_index]

        # Flip the sprite horizontally when the boss faces left
        if self.facing_right:
            frame_surf = flip_h(frame_surf)

        surface.blit(frame_surf, (int(self.pos.x), int(self.pos.y)))

        # -- Debug hitboxes (DEV_MODE) -----------------------------------
        # self.pos was shifted to screen space by the caller;
        # body_rect/attack_hitbox are in world space, so the same delta
        # that was applied to pos is applied to them.
        if DEV_MODE:
            dx = int(self.pos.x) - (self.body_rect.x - (self.sprite_w - self.body_rect.w) // 2)
            dy = int(self.pos.y) - (self.body_rect.y - (self.sprite_h - self.body_rect.h))
            body_visual = self.body_rect.move(dx, dy)
            pygame.draw.rect(surface, (255, 0, 0), body_visual, 1)
            if self.attack_hitbox:
                atk_visual = self.attack_hitbox.move(dx, dy)
                pygame.draw.rect(surface, (255, 140, 0), atk_visual, 2)

    # ────────────────────────────────────────────────────────────
    # PUBLIC API
    # ────────────────────────────────────────────────────────────

    def take_damage(self, amount: int):
        """
        Damage the boss.
        Call this when a player attack touches body_rect.
        """
        if self.state == BossState.DEATH:
            return  # A boss that is already dead cannot be killed again

        self.hp -= amount

        if self.hp <= 0:
            self.hp = 0
            self._change_state(BossState.DEATH)
        elif self.state != BossState.TAKE_HIT and self.invincibility_timer <= 0:
            # Interrupt the current state, unless the boss is already in TAKE_HIT
            # or protected by its invincibility frames (avoids spam locking its attacks).
            self._change_state(BossState.TAKE_HIT)

    @property
    def is_dead(self) -> bool:
        """True once the death animation has completely finished."""
        return self.state == BossState.DEATH and self._is_last_frame()

    @property
    def is_attacking(self) -> bool:
        """True during the active frames of the cleave - uses attack_hitbox for collisions."""
        return self.attack_hitbox is not None

    # ────────────────────────────────────────────────────────────
    # INTERNAL (private) METHODS
    # ────────────────────────────────────────────────────────────

    def _decide_next_state(self, distance: float):
        """
        Autonomous boss AI.
        Behaviour:
        - Outside DETECT_RADIUS -> IDLE (waits quietly)
        - Inside DETECT_RADIUS  -> WALK (chase)
        - Within reach          -> CLEAVE once the cooldown has elapsed
        """
        range_real = int(self.sprite_w * 0.4)

        if distance <= range_real and self.attack_cooldown_timer <= 0:
            # The player is exactly within machete range -> stop and strike
            self._change_state(BossState.CLEAVE)

        elif distance <= self.DETECT_RADIUS:
            if distance > range_real:
                # Not in range yet -> walk towards the player
                if self.state != BossState.WALK:
                    self._change_state(BossState.WALK)
            else:
                # In range but cooldown not elapsed -> wait in place
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
            # Movement on X only - the boss stays on the ground
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
            hh = int(self.sprite_h * 0.3)
            hy = int(self.pos.y) + (self.sprite_h - hh)

            if self.facing_right:
                # Flipped to the right -> machete on the right half of the sprite
                hx = int(self.pos.x) + self.sprite_w - hw
            else:
                # Facing left by default -> machete on the left half of the sprite
                hx = int(self.pos.x)

            self.attack_hitbox = pygame.Rect(hx, hy, hw, hh)
        else:
            self.attack_hitbox = None

    def _update_animation(self, dt_ms: float):
        """
        Advance the animation using the durations of the Aseprite JSON.
        Each frame has its own duration, which allows non-uniform animations.
        """
        if not self.current_anim_frames:
            return

        _, frame_duration = self.current_anim_frames[self.current_frame_index]
        self.frame_timer_ms += dt_ms

        # As soon as the accumulated time exceeds the current frame's duration...
        if self.frame_timer_ms >= frame_duration:
            self.frame_timer_ms -= frame_duration  # carry the surplus over to the next frame
            next_idx = self.current_frame_index + 1

            if next_idx >= len(self.current_anim_frames):
                # End of the animation -> logic depends on the state
                self._on_animation_end()
            else:
                self.current_frame_index = next_idx

    def _on_animation_end(self):
        """
        Called automatically at the end of every animation.
        This is where the "locking" states (CLEAVE, TAKE_HIT) get unlocked.
        """
        if self.state == BossState.CLEAVE:
            # Attack finished -> start the cooldown and rest the boss
            self.attack_cooldown_timer = self.ATTACK_COOLDOWN
            self._change_state(BossState.IDLE)

        elif self.state == BossState.TAKE_HIT:
            # Hit reaction finished -> invincibility frames, then normal logic
            self.invincibility_timer = self.INVINCIBILITY_DURATION
            self._change_state(BossState.IDLE)

        elif self.state == BossState.DEATH:
            # Stay frozen on the very last frame (freeze on death)
            self.current_frame_index = len(self.current_anim_frames) - 1

        else:
            # IDLE and WALK: looping animation, restart at frame 0
            self.current_frame_index = 0

    def _change_state(self, new_state: BossState):
        """
        Switch to a new state:
          1. Update self.state
          2. Load the frames of the new animation
          3. Reset the timers
        """
        if new_state == self.state:
            return

        self.state = new_state

        # Mapping state -> animation name in the JSON
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
        """True when on the last frame (final state of DEATH)."""
        return self.current_frame_index >= len(self.current_anim_frames) - 1
    

    def get_state(self):
        """Serialise the boss state to send it to the client over the network."""
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

    def set_state(self, data):
        """Apply a state received from the server (client side, read-only)."""
        self.pos.x       = data['x']
        self.pos.y       = data['y']
        self.hp          = data['hp']
        self.facing_right = data['facing_right']
        self.current_frame_index = data['frame_index']

        # Synchronise the animation with the received state
        state_name = data['state']
        new_state   = BossState[state_name]
        if new_state != self.state:
            self._change_state(new_state)

        r = data['body_rect']
        self.body_rect = pygame.Rect(r[0], r[1], r[2], r[3])

        ah = data['attack_hitbox']
        self.attack_hitbox = pygame.Rect(ah[0], ah[1], ah[2], ah[3]) if ah else None