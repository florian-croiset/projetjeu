import pygame
from demon_slime_boss import DemonSlimeBoss, BossState
from parametres import TAILLE_TUILE, GRAVITE


class BossRoom:

    BOSS_ATTACK_DAMAGE = 1

    def __init__(self, room_rect: pygame.Rect,
                 boss_x: int, boss_y: int,
                 json_path: str, png_path: str,
                 rects_collision: list):          # ← paramètre ajouté

        self.room_rect       = room_rect
        self.boss            = DemonSlimeBoss(boss_x, boss_y, json_path, png_path)
        self.rects_collision = rects_collision    # ← stocké avec self.

        self.fight_started       = False
        self.boss_defeated       = False
        self._a_touche_ce_swing  = False

    def update(self, dt: float, joueurs: dict):
        if self.boss_defeated:
            return

        temps_actuel = pygame.time.get_ticks()

        # ── Cherche la cible ─────────────────────────────────────────────
        cible    = None
        dist_min = float('inf')
        boss_cx  = self.boss.pos.x + self.boss.sprite_w / 2
        boss_cy  = self.boss.pos.y + self.boss.sprite_h / 2

        for joueur in joueurs.values():
            if joueur.pv <= 0:
                continue
            if self.room_rect.colliderect(joueur.rect):
                self.fight_started = True
            d = ((joueur.rect.centerx - boss_cx) ** 2 +
                 (joueur.rect.centery - boss_cy) ** 2) ** 0.5
            if d < dist_min:
                dist_min = d
                cible = joueur

        if not self.fight_started or cible is None:
            return

        # ── Update boss ──────────────────────────────────────────────────
        self.boss.update(dt, cible.rect)

        boss = self.boss

        # ── Collisions murs axe X ────────────────────────────────────────
        boss.body_rect.x = int(boss.pos.x) + (boss.sprite_w - boss.body_rect.w) // 2
        for mur in self.rects_collision:                          # ← self.
            if boss.body_rect.colliderect(mur):
                if boss.velocity.x > 0:
                    boss.body_rect.right = mur.left
                elif boss.velocity.x < 0:
                    boss.body_rect.left = mur.right
                boss.velocity.x = 0
                boss.pos.x = boss.body_rect.x - (boss.sprite_w - boss.body_rect.w) // 2

        # ── Collisions murs axe Y ────────────────────────────────────────
        boss.body_rect.y = int(boss.pos.y) + (boss.sprite_h - boss.body_rect.h)
        boss.sur_le_sol  = False
        for mur in self.rects_collision:                          # ← self.
            if boss.body_rect.colliderect(mur):
                if boss.velocity.y > 0:
                    boss.body_rect.bottom = mur.top
                    boss.velocity.y  = 0
                    boss.sur_le_sol  = True
                elif boss.velocity.y < 0:
                    boss.body_rect.top = mur.bottom
                    boss.velocity.y = 0
                boss.pos.y = boss.body_rect.y - (boss.sprite_h - boss.body_rect.h)

        # ── Contraindre dans la salle ────────────────────────────────────
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

        # ── Mort du boss ─────────────────────────────────────────────────
        if self.boss.is_dead:
            self.boss_defeated = True
            self._on_boss_defeated(joueurs)
            return

        # ── Dégâts boss → joueurs ────────────────────────────────────────
        if self.boss.attack_hitbox:
            for joueur in joueurs.values():
                if joueur.pv <= 0:
                    continue
                if self.boss.attack_hitbox.colliderect(joueur.rect):
                    if not self._a_touche_ce_swing:
                        joueur.prendre_degat(self.BOSS_ATTACK_DAMAGE, temps_actuel)
                        self._a_touche_ce_swing = True
                        print(f"[BossRoom] Boss touche joueur — PV restants : {joueur.pv}")
        else:
            self._a_touche_ce_swing = False

    def recevoir_attaque_joueur(self, rect_attaque: pygame.Rect, degats: int):
        if self.boss_defeated:
            return
        if rect_attaque.colliderect(self.boss.body_rect):
            self.boss.take_damage(degats)

    def get_etat(self):
        return {
            'boss':          self.boss.get_etat(),
            'fight_started': self.fight_started,
            'boss_defeated': self.boss_defeated,
        }

    def _on_boss_defeated(self, joueurs):
        print("[BossRoom] Boss vaincu !")