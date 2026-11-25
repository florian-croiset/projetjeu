import pygame
from core.demon_slime_boss import DemonSlimeBoss, BossState


class BossRoom:

    BOSS_ATTACK_DAMAGE = 1

    def __init__(self, room_rect: pygame.Rect,
                 boss_x: int, boss_y: int,
                 json_path: str, png_path: str,
                 rects_collision: list):

        self.room_rect       = room_rect
        self.boss            = DemonSlimeBoss(boss_x, boss_y, json_path, png_path)
        self.rects_collision = rects_collision

        self.fight_started       = False
        self.boss_defeated       = False
        self._has_hit_this_swing  = False

    def update(self, dt: float, players: dict, now=None):
        if self.boss_defeated:
            return

        if now is None:
            now = pygame.time.get_ticks()

        # -- Find the target ---------------------------------------------
        target    = None
        dist_min = float('inf')
        boss_cx  = self.boss.pos.x + self.boss.sprite_w / 2
        boss_cy  = self.boss.pos.y + self.boss.sprite_h / 2

        for player in players.values():
            if player.hp <= 0:
                continue
            if self.room_rect.colliderect(player.rect):
                self.fight_started = True
            d = ((player.rect.centerx - boss_cx) ** 2 +
                 (player.rect.centery - boss_cy) ** 2) ** 0.5
            if d < dist_min:
                dist_min = d
                target = player

        if not self.fight_started or target is None:
            return

        # -- Update the boss ---------------------------------------------
        self.boss.update(dt, target.rect)

        boss = self.boss

        # -- Wall collisions, X axis -------------------------------------
        boss.body_rect.x = int(boss.pos.x) + (boss.sprite_w - boss.body_rect.w) // 2
        for wall in self.rects_collision:
            if boss.body_rect.colliderect(wall):
                if boss.velocity.x > 0:
                    boss.body_rect.right = wall.left
                elif boss.velocity.x < 0:
                    boss.body_rect.left = wall.right
                boss.velocity.x = 0
                boss.pos.x = boss.body_rect.x - (boss.sprite_w - boss.body_rect.w) // 2

        # -- Wall collisions, Y axis -------------------------------------
        boss.body_rect.y = int(boss.pos.y) + (boss.sprite_h - boss.body_rect.h)
        boss.on_ground  = False
        for wall in self.rects_collision:
            if boss.body_rect.colliderect(wall):
                if boss.velocity.y > 0:
                    boss.body_rect.bottom = wall.top
                    boss.velocity.y  = 0
                    boss.on_ground  = True
                elif boss.velocity.y < 0:
                    boss.body_rect.top = wall.bottom
                    boss.velocity.y = 0
                boss.pos.y = boss.body_rect.y - (boss.sprite_h - boss.body_rect.h)

        # -- Constrain to the room ----------------------------------------
        if boss.pos.x < self.room_rect.left:
            boss.pos.x    = self.room_rect.left
            boss.velocity.x = 0
        if boss.pos.x + boss.sprite_w > self.room_rect.right:
            boss.pos.x    = self.room_rect.right - boss.sprite_w
            boss.velocity.x = 0
        if boss.pos.y < self.room_rect.top:
            boss.pos.y    = self.room_rect.top
            boss.velocity.y = 0
        if boss.pos.y + boss.sprite_h > self.room_rect.bottom:
            boss.pos.y    = self.room_rect.bottom - boss.sprite_h
            boss.velocity.y = 0

        # -- Boss death ---------------------------------------------------
        if self.boss.is_dead:
            self.boss_defeated = True
            self._on_boss_defeated(players)
            return

        # -- Boss damage -> players ----------------------------------------
        if self.boss.attack_hitbox:
            for player in players.values():
                if player.hp <= 0:
                    continue
                if self.boss.attack_hitbox.colliderect(player.rect):
                    if not self._has_hit_this_swing:
                        # Bypass INVINCIBILITY_TIME_MS - the boss forces the damage
                        player.hp -= self.BOSS_ATTACK_DAMAGE
                        player.last_damage_time = now
                        if player.hp <= 0:
                            player.hp = 0
                            player.sounds_to_play.append('dead')
                        else:
                            # Knockback away from the boss (only if still alive)
                            if not player.is_dashing:
                                from settings import RECOIL_VX, RECOIL_VY, RECOIL_DURATION_MS
                                direction = 1 if player.rect.centerx >= self.boss.attack_hitbox.centerx else -1
                                player.recoil_vx = direction * RECOIL_VX
                                player.vel_y = RECOIL_VY
                                player.recoil_until = now + RECOIL_DURATION_MS
                                player.on_ground = False
                        self._has_hit_this_swing = True
                        print(f"[BossRoom] boss hit a player - remaining HP: {player.hp}")
        else:
            self._has_hit_this_swing = False

    def receive_attack_player(self, attack_rect: pygame.Rect, damage: int):
        if self.boss_defeated:
            return
        if attack_rect.colliderect(self.boss.body_rect):
            self.boss.take_damage(damage)

    def get_state(self):
        return {
            'boss':          self.boss.get_state(),
            'fight_started': self.fight_started,
            'boss_defeated': self.boss_defeated,
        }

    def _on_boss_defeated(self, players):
        print("[BossRoom] boss defeated!")

    def reset_boss(self):
        """Reset the boss to its initial state without defeating it."""
        self.fight_started = False
        self._has_hit_this_swing = False
        self.boss.hp = self.boss.MAX_HP
        self.boss.state = BossState.IDLE
        self.boss.current_anim_frames = self.boss.animator.get_animation(self.boss.ANIM_IDLE)
        self.boss.current_frame_index = 0
        self.boss.frame_timer_ms = 0.0
        self.boss.attack_cooldown_timer = 0
        self.boss.invincibility_timer = 0
        self.boss.velocity.x = 0
        self.boss.velocity.y = 0
        print("[BossRoom] boss reset")