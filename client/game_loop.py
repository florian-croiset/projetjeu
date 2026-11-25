# game_loop.py
# Main loop of the application: menus dispatch, in-game input, prediction ticks,
# world rendering. Networking lives in net/, applying server data in
# client_state.py, connection handling in client_connection.py.

import copy
import random
import sys
import time

import pygame
from utils.paths import asset_path

from net import protocol as P
from settings import *
from storage import settings_io
from ui.camera import compute_camera, create_mask_halo
from ui.tutorial import Tutorial
from ui.visual_effects import apply_distortion_echo
from utils import i18n, music
from core.lore_sign import (LoreSign, COST_DASH)
from utils.i18n import get_text


class GameLoopMixin:
    """Game loop methods: main loop, input, rendering."""

    # ====================================================================
    # ENDING SEQUENCE
    # ====================================================================

    END_ENDING_IMAGE = asset_path("ending.png")
    END_TEASER_IMAGE = asset_path("teaser_echo2.png")
    END_CRYSTAL_FRAMES = [
        asset_path(name)
        for name in [
            "Destruction_Solaris_1_-_Instabilité.png",
            "Destruction_Solaris_2_-_Fissures.png",
            "Destruction_Solaris_3_-_Explosion.png",
            "Destruction_Solaris_4_-_Aftermath.png",
            "Destruction_Solaris_5_-_Noir.png",
        ]
    ]
    
    # ==================================================================
    # MAIN APPLICATION LOOP
    # ==================================================================

    def launch_application(self):
        if not self.settings.get("meta", {}).get("tutorial_seen", False):
            tutorial = Tutorial(
                self.screen, self.width_screen, self.height_screen,
                self.settings['controls'],
                self.font_title, self.font_text,
                self.font_button, self.font_small
            )
            tutorial.launch()
            self.settings.setdefault("meta", {})["tutorial_seen"] = True
            settings_io.save_settings(self.settings)

        while self.running:
            self.time_anim = pygame.time.get_ticks()
            pos_mouse      = pygame.mouse.get_pos()

            if self.game_state == "MENU_MAIN":
                self.handle_menu_main(pos_mouse)
                self.draw_menu_main()

            elif self.game_state == "MENU_JOIN":
                self.handle_menu_join(pos_mouse)
                self.draw_menu_join()

            elif self.game_state in ("MENU_NEW_GAME", "MENU_CONTINUE"):
                self.handle_menu_slots(pos_mouse)
                self.draw_menu_slots()

            elif self.game_state == "MENU_CONFIRMATION":
                self.handle_menu_confirmation(pos_mouse)
                self.draw_menu_confirmation()

            elif self.game_state == "MENU_SETTINGS":
                if not self.settings_temp:
                    self.settings_temp = copy.deepcopy(self.settings)
                self.handle_menu_settings(pos_mouse)
                self.draw_menu_settings()

            elif self.game_state == "MENU_BRIGHTNESS":
                self.handle_menu_brightness(pos_mouse)
                if self.game_state == "MENU_BRIGHTNESS":
                    self.draw_menu_brightness()

            elif self.game_state == "IN_GAME":
                if self.inner_game_state != "PAUSE":
                    self.inner_game_state = "GAME"
                self.network_game_loop()
                if self.game_state == "MENU_SETTINGS":
                    self.previous_game_state = "IN_GAME"
                    self.settings_temp    = copy.deepcopy(self.settings)
                elif self.game_state != "IN_GAME":
                    self.game_state = "MENU_MAIN"
                    self.cleanup_connection()
                    self.refresh_languages_widgets()

            elif self.game_state == "QUIT":
                self.running = False

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()

    # ==================================================================
    # IN-GAME EVENT HANDLING
    # ==================================================================

    def _sound_attack(self, player):
        """Slash2/Slash3 if an enemy is within attack range, otherwise Slash1."""
        if player.direction == 1:
            rect_a = pygame.Rect(player.rect.right, player.rect.y, ATTACK_RANGE, player.rect.height)
        else:
            rect_a = pygame.Rect(player.rect.left - ATTACK_RANGE, player.rect.y, ATTACK_RANGE, player.rect.height)
        for enemy in self.local_enemies.values():
            if not enemy.is_dead and rect_a.colliderect(enemy.rect):
                return random.choice(['slash2', 'slash3'])
        return 'attack'

    def handle_game_events(self):
        """Process pygame events while playing.

        Returns ``(held_bits, actions)``: the movement keys currently held (as
        ``P.IN_*`` bits) and the one-shot actions to send to the server. Pressed
        attack/dash keys are *latched* in ``self._latched_bits`` until the next
        prediction tick consumes them."""
        held = 0
        actions = []

        key = self._codes_keys.get

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN and event.key == self._codes_keys.get('journal'):
                if hasattr(self, 'journal_quest') and self.journal_quest:
                    self.journal_quest.toggle()
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == self._codes_mouse.get('journal'):
                if hasattr(self, 'journal_quest') and self.journal_quest:
                    self.journal_quest.toggle()
                continue

            # Let the bubble and the popups consume the events first
            if self.bubble_lore and self.bubble_lore.visible:
                if self.bubble_lore.handle_event(event):
                    continue
            if self.popup_payment and self.popup_payment.visible:
                if self.popup_payment.handle_event(event):
                    continue
            if self.popup_shop_upgrades and self.popup_shop_upgrades.visible:
                if self.popup_shop_upgrades.handle_event(event):
                    continue

            # If the journal is open, block every game input
            if hasattr(self, 'journal_quest') and self.journal_quest and self.journal_quest.is_open:
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    try:
                        self._last_frame_game = self.screen.copy()
                    except Exception:
                        self._last_frame_game = None
                    self.inner_game_state = "PAUSE"
                    music.pause()
                if event.key == key('attack'):
                    self._latched_bits |= P.IN_ATTACK
                    _j = self.local_players.get(self.my_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attack_local_start_ms >= ATTACK_COOLDOWN:
                        music.play_sfx(self._sound_attack(_j) if _j else 'attack')
                        if _j:
                            _j._attack_local_start_ms = now
                if event.key == key('echo'):
                    actions.append({'a': 'echo'})
                    music.play_sfx('echo')
                    if ECHO_DISTORTION_ENABLED:
                        _je = self.local_players.get(self.my_id)
                        _now = pygame.time.get_ticks()
                        if _je and _now - getattr(_je, '_last_echo_local_ms', -COOLDOWN_ECHO) >= COOLDOWN_ECHO:
                            _je._last_echo_local_ms = _now
                            if not hasattr(self, '_distortions_echo'):
                                self._distortions_echo = []
                            self._distortions_echo.append({
                                'start_ms':  _now,
                                'wx':        _je.rect.centerx,
                                'wy':        _je.rect.centery,
                                'radius_max': ECHO_RANGE,
                                'duration_ms':  ECHO_REVEAL_DURATION,
                            })
                if event.key == key('dash'):
                    self._latched_bits |= P.IN_DASH
                if event.key == key('echo_dir'):
                    actions.append({'a': 'echo_dir'})
                    music.play_sfx('echo_dir')
                    if ECHO_DISTORTION_ENABLED:
                        _je = self.local_players.get(self.my_id)
                        _now = pygame.time.get_ticks()
                        if (_je and getattr(_je, 'can_echo_dir', False)
                                and _now - getattr(_je, '_last_echo_dir_local_ms', -COOLDOWN_ECHO_DIR) >= COOLDOWN_ECHO_DIR):
                            _je._last_echo_dir_local_ms = _now
                            if not hasattr(self, '_distortions_echo'):
                                self._distortions_echo = []
                            self._distortions_echo.append({
                                'start_ms':  _now,
                                'wx':        _je.rect.centerx,
                                'wy':        _je.rect.centery,
                                'radius_max': ECHO_DIR_RANGE,
                                'duration_ms':  int(ECHO_DIR_RANGE / ECHO_RANGE * ECHO_REVEAL_DURATION),
                            })
                if event.key == key('torch'):
                    actions.append({'a': 'torch'})
                    if not self.torch.lit:
                        music.torch_loop_start()
                    else:
                        music.torch_loop_stop()

                # Interaction key (F by default)
                if event.key == key('interact'):
                    my_player = self.local_players.get(self.my_id)
                    if my_player and not self.bubble_lore.visible and not self.popup_payment.visible:
                        sign_near = None
                        for i, sign in self.local_lore_signs.items():
                            dx = my_player.rect.centerx - sign.rect.centerx
                            dy = my_player.rect.centery - sign.rect.centery
                            if (dx**2 + dy**2) ** 0.5 <= LoreSign.RANGE_INTERACTION:
                                sign_near = (i, sign)
                                break
                        if sign_near:
                            i, sign = sign_near
                            type_p = getattr(sign, 'type_sign', 'lore')
                            if type_p == 'shop_upgrades':
                                damage_bonus = getattr(my_player, 'damage_bonus', 0)
                                max_hp_bonus = getattr(my_player, 'max_hp_bonus', 0)
                                echo_dir     = getattr(my_player, 'can_echo_dir', False)
                                def _callback_shop(item):
                                    self._purchase_in_waiting = True
                                    self._shop_item_in_waiting = item
                                self.popup_shop_upgrades.open(
                                    my_player.money, damage_bonus, max_hp_bonus,
                                    echo_dir, _callback_shop)
                            elif sign.is_unlocked:
                                if type_p == 'letter':
                                    self.bubble_lore.open(
                                        get_text("lore_letter_jonas"),
                                        title=get_text("lore_title_letter"),
                                        sub_title=get_text("lore_sub_letter"),
                                    )
                                elif type_p == 'shop_dash':
                                    self.bubble_lore.open(get_text("lore_stele_dash"))
                                elif type_p == 'lore_lever':
                                    self.bubble_lore.open_multi([
                                        {'text': get_text("lore_lever"),
                                         'title': get_text("lore_title_fragment"),
                                         'sub_title': get_text("lore_sub_sector7")},
                                        {'text': get_text("lore_stele"),
                                         'title': get_text("lore_title_inscription"),
                                         'sub_title': get_text("lore_sub_inscription")},
                                    ])
                                else:
                                    self.bubble_lore.open()
                            else:
                                self._sign_active_id = i

                                def _callback_payment():
                                    self._purchase_in_waiting = self._sign_active_id

                                if type_p == 'shop_dash':
                                    self.popup_payment._title_popup = get_text("lore_popup_fragment")
                                    self.popup_payment._message_popup = get_text("lore_popup_dash_msg").format(cost=COST_DASH)
                                    self.popup_payment.open_confirmation(
                                        my_player.money,
                                        _callback_payment,
                                        COST_DASH
                                    )
                                else:
                                    # Free lore: triggered directly, without a popup
                                    self._purchase_in_waiting = i
                        elif (self.local_paid_wall
                              and not self.paid_wall_unlocked):
                            mp = self.local_paid_wall
                            dx = my_player.rect.centerx - (mp.x + TILE_SIZE // 2)
                            dy = my_player.rect.centery - (mp.y + TILE_SIZE // 2)
                            if dx*dx + dy*dy <= mp.RANGE_INTERACTION ** 2:
                                self._purchase_in_waiting = 'paid_wall'

            if event.type == pygame.MOUSEBUTTONDOWN:
                ms = self._codes_mouse.get
                if ms('attack') and event.button == ms('attack'):
                    self._latched_bits |= P.IN_ATTACK
                    _j = self.local_players.get(self.my_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attack_local_start_ms >= ATTACK_COOLDOWN:
                        music.play_sfx(self._sound_attack(_j) if _j else 'attack')
                        if _j:
                            _j._attack_local_start_ms = now
                if ms('echo') and event.button == ms('echo'):
                    actions.append({'a': 'echo'})
                    music.play_sfx('echo')
                if ms('dash') and event.button == ms('dash'):
                    self._latched_bits |= P.IN_DASH
                if ms('echo_dir') and event.button == ms('echo_dir'):
                    actions.append({'a': 'echo_dir'})
                    music.play_sfx('echo_dir')

        key_names = pygame.key.get_pressed()
        if key('left') and key_names[key('left')]:
            held |= P.IN_LEFT
        if key('right') and key_names[key('right')]:
            held |= P.IN_RIGHT
        if key('jump') and key_names[key('jump')]:
            held |= P.IN_JUMP
        if self._codes_mouse:
            mouse = pygame.mouse.get_pressed(num_buttons=5)
            for action in ('left', 'right', 'jump'):
                btn = self._codes_mouse.get(action)
                if btn and 1 <= btn <= 5 and mouse[btn - 1]:
                    held |= {'left': P.IN_LEFT, 'right': P.IN_RIGHT, 'jump': P.IN_JUMP}[action]

        my_player = self.local_players.get(self.my_id)
        if my_player and my_player.hp <= 0:
            held, actions, self._latched_bits = 0, [], 0

        if self._purchase_in_waiting is not None:
            actions.append({'a': 'interact', 'item': self._shop_item_in_waiting})
            self._purchase_in_waiting = None
            self._shop_item_in_waiting = None

        return held, actions

    # ==================================================================
    # WORLD RENDERING
    # ==================================================================

    def draw_game(self):
        self._init_hud_cache()
        my_player = self.local_players.get(self.my_id)
        if not my_player or not self.game_map or not self.vis_map_local:
            self.screen.fill(COLOR_BACKGROUND)
            return

        zoom = self.zoom_effective
        lv   = int(self.width_screen / zoom)
        hv   = int(self.height_screen / zoom)
        if not hasattr(self, '_surface_virtual') or self._surface_virtual.get_size() != (lv, hv):
            self._surface_virtual = pygame.Surface((lv, hv))
        surface_virtual = self._surface_virtual

        lm = self.game_map.width_map * TILE_SIZE
        hm = self.game_map.height_map * TILE_SIZE
        camera_offset = compute_camera(my_player.rect,
                                        self.width_screen, self.height_screen,
                                        zoom, lm, hm)

        self.game_map.draw_map(surface_virtual, self.vis_map_local, camera_offset)

        # --- Progressive fade of the tiles revealed by echo ---
        if self._fade_surface is not None and DARKNESS_ENABLED:
            now_fade = pygame.time.get_ticks()

            # Lit torch: keeps the tiles of its radius visible
            if getattr(self, 'torch', None) and self.torch.lit:
                tx_world = self.torch.x + TILE_SIZE // 2
                ty_world = self.torch.y + TILE_SIZE // 2
                r = TORCH_LIGHT_RADIUS
                t_min_x = max(0, int((tx_world - r) // TILE_SIZE))
                t_max_x = min(self.game_map.width_map - 1, int((tx_world + r) // TILE_SIZE))
                t_min_y = max(0, int((ty_world - r) // TILE_SIZE))
                t_max_y = min(self.game_map.height_map - 1, int((ty_world + r) // TILE_SIZE))
                r2 = r * r
                for tty in range(t_min_y, t_max_y + 1):
                    for ttx in range(t_min_x, t_max_x + 1):
                        cx = ttx * TILE_SIZE + TILE_SIZE // 2
                        cy = tty * TILE_SIZE + TILE_SIZE // 2
                        if (cx - tx_world) ** 2 + (cy - ty_world) ** 2 <= r2:
                            self.echo_fade_times[(ttx, tty)] = now_fade
                            if not self.vis_map_local[tty][ttx]:
                                self.vis_map_local[tty][ttx] = True
                                self.game_map._tiles_to_reveal.append((ttx, tty))
                                self.game_map._vis_map_dirty = True

            expired = []
            for (tx, ty), t_reveal in self.echo_fade_times.items():
                age = now_fade - t_reveal
                if age >= ECHO_FADE_DURATION:
                    expired.append((tx, ty))
                    alpha = 255
                else:
                    alpha = int(age * 255 / ECHO_FADE_DURATION)
                self._fade_surface.fill(
                    (0, 0, 0, alpha),
                    pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE,
                                TILE_SIZE, TILE_SIZE))
            for tile in expired:
                del self.echo_fade_times[tile]
            off_x, off_y = camera_offset
            surface_virtual.blit(self._fade_surface, (0, 0),
                                   pygame.Rect(off_x, off_y, lv, hv))

        # --- Doors ---
        ticks_render_doors = pygame.time.get_ticks()
        for door in self.local_doors.values():
            door.draw(surface_virtual, camera_offset, ticks_render_doors)

        # --- Potions ---
        if hasattr(self, 'potions') and self.potions is not None:
            self.potions.draw(surface_virtual, camera_offset)

        # --- Ability orbs ---
        off_x, off_y = camera_offset
        camera_rect = pygame.Rect(off_x, off_y, lv, hv)
        ticks_render = pygame.time.get_ticks()
        for orb in self.local_ability_orbs.values():
            if orb.is_picked_up:
                continue
            orb.update(ticks_render)
            if not camera_rect.colliderect(orb.rect):
                continue
            if orb.ability == 'double_jump' and getattr(my_player, 'can_double_jump', False):
                continue
            if orb.ability == 'dash' and getattr(my_player, 'can_dash', False):
                continue
            if orb.ability == 'echo_dir' and getattr(my_player, 'can_echo_dir', False):
                continue
            orb.draw(surface_virtual, camera_offset, ticks_render)

        # --- Lore signs ---
        key_interact = self.settings.get('controls', {}).get('interact', 'f')
        for sign in self.local_lore_signs.values():
            sign.update(ticks_render)
            if camera_rect.colliderect(sign.rect):
                sign.draw(surface_virtual, camera_offset, ticks_render,
                                  key_interact=key_interact)

        # --- Players ---
        for player in self.local_players.values():
            player.draw(surface_virtual, camera_offset)

        time_ms = pygame.time.get_ticks()

        # --- Enemies ---
        detection_sq = ENEMY_DETECTION_DISTANCE * ENEMY_DETECTION_DISTANCE
        for enemy in self.local_enemies.values():
            if not camera_rect.colliderect(enemy.rect):
                continue
            if my_player:
                dx   = enemy.rect.centerx - my_player.rect.centerx
                dy   = enemy.rect.centery - my_player.rect.centery
                dist_sq = dx*dx + dy*dy
            else:
                dist_sq = 9999 * 9999

            near             = dist_sq <= detection_sq

            if near:
                enemy.draw(surface_virtual, camera_offset)

        # --- Boss ---
        if self.boss_local and not getattr(self.boss_local, 'is_dead', False):
            off_x, off_y = camera_offset
            self.boss_local.pos.x -= off_x
            self.boss_local.pos.y -= off_y
            self.boss_local.draw(surface_virtual)
            self.boss_local.pos.x += off_x
            self.boss_local.pos.y += off_y

        if my_player and my_player.hp > 0:
            self._dead_since = None

        # --- Souls (with camera culling) ---
        for soul in self.local_lost_souls.values():
            if camera_rect.colliderect(soul.rect):
                soul.draw(surface_virtual, camera_offset, time_ms,
                             money_max=getattr(soul, '_money_max', None))
        for soul in self.local_free_souls.values():
            soul.update(time_ms)
            if camera_rect.colliderect(soul.rect):
                soul.draw(surface_virtual, camera_offset, time_ms)
        for soul in self.local_loot_souls.values():
            soul.update_visuals(time_ms, self.game_map)
            if camera_rect.colliderect(soul.rect):
                soul.draw(surface_virtual, camera_offset, time_ms)

        # --- Key (key image, not an orb) ---
        if self.local_key_item and not self.local_key_item.is_picked_up:
            self.local_key_item.update(time_ms)
            if camera_rect.colliderect(self.local_key_item.rect):
                self.local_key_item.draw(surface_virtual, camera_offset, time_ms)

        # --- Torch ---
        self.torch.update(time_ms)
        self.torch.draw(surface_virtual, camera_offset, time_ms)

        # --- Levers ---
        for lever in self.local_levers.values():
            lever.draw(surface_virtual, camera_offset, time_ms)

        # --- Paid wall ---
        if self.local_paid_wall and not self.paid_wall_unlocked:
            self.local_paid_wall.draw(surface_virtual, camera_offset,
                                           player_rect=my_player.rect)

        if self.torch.lit and my_player:
            dx   = my_player.rect.centerx - self.torch.x
            dy   = my_player.rect.centery - self.torch.y
            dist = (dx**2 + dy**2) ** 0.5
            music.torch_update_volume(dist)

        # --- Darkness layer ---
        if my_player and DARKNESS_ENABLED:
            sz = surface_virtual.get_size()
            if not hasattr(self, '_darkness') or self._darkness.get_size() != sz:
                self._darkness = pygame.Surface(sz, pygame.SRCALPHA)
            darkness = self._darkness
            lum = self.settings.get('video', {}).get('brightness', 0.3)
            alpha_base = int(220 * (1.0 - lum * 0.8))
            if getattr(self, '_halo_alpha_max', None) != alpha_base:
                self._mask_halo_player = create_mask_halo(PLAYER_HALO_RADIUS, HALO_GRADIENT_WIDTH, alpha_max=alpha_base)
                self._mask_halo_torch = create_mask_halo(TORCH_LIGHT_RADIUS, HALO_GRADIENT_WIDTH, alpha_max=alpha_base)
                self._halo_alpha_max = alpha_base
            darkness.fill((0, 0, 10, alpha_base))
            radius = PLAYER_HALO_RADIUS
            cx = my_player.rect.centerx - camera_offset[0]
            cy = my_player.rect.centery - camera_offset[1]
            darkness.blit(self._mask_halo_player,
                           (cx - radius - 1, cy - radius - 1),
                           special_flags=pygame.BLEND_RGBA_MIN)
            if self.torch.lit:
                radius_t = TORCH_LIGHT_RADIUS
                tx = self.torch.x + TILE_SIZE // 2 - camera_offset[0]
                ty = self.torch.y + TILE_SIZE     - camera_offset[1]
                darkness.blit(self._mask_halo_torch,
                               (tx - radius_t - 1, ty - radius_t - 1),
                               special_flags=pygame.BLEND_RGBA_MIN)
            surface_virtual.blit(darkness, (0, 0))

        # --- Echo distortion ---
        if ECHO_DISTORTION_ENABLED and getattr(self, '_distortions_echo', None):
            t_now_dist = pygame.time.get_ticks()
            self._distortions_echo = [
                o for o in self._distortions_echo
                if t_now_dist - o['start_ms'] < o['duration_ms']
            ]
            if self._distortions_echo:
                waves_screen = [{
                    'start_ms':  o['start_ms'],
                    'sx':        o['wx'] - camera_offset[0],
                    'sy':        o['wy'] - camera_offset[1],
                    'radius_max': o['radius_max'],
                    'duration_ms':  o['duration_ms'],
                } for o in self._distortions_echo]
                apply_distortion_echo(surface_virtual, waves_screen, t_now_dist)

        # --- Torch badge ---
        if self.torch.never_used and my_player:
            dx = my_player.rect.centerx - self.torch.x
            dy = my_player.rect.centery - self.torch.y
            if (dx**2 + dy**2)**0.5 <= TORCH_ECHO_DISTANCE * 3:
                self._draw_badge_torch(surface_virtual, camera_offset)

        if my_player and my_player.hp <= 0:
            if self._dead_since is None:
                music.play_sfx('dead')
            self._draw_death_screen(surface_virtual)
        elif my_player and my_player.hp > 0:
            self._dead_since = None

        surface_zoomed = pygame.transform.scale(
            surface_virtual, (self.width_screen, self.height_screen))
        self.screen.blit(surface_zoomed, (0, 0))

        # Nicknames are drawn directly on the final (post-scale) screen to stay sharp.
        for player in self.local_players.values():
            player.draw_nickname_on_screen(self.screen, camera_offset, zoom)

        self.draw_hud()

    # ==================================================================
    # NETWORK GAME LOOP
    # ==================================================================

    # ==================================================================
    #  IN-GAME LOOP
    # ==================================================================

    TICK_S = P.TICK_MS / 1000.0
    MAX_CATCH_UP_TICKS = 6

    def _run_prediction_ticks(self, held):
        """Advance the local simulation by the real time elapsed, then send inputs."""
        now = time.perf_counter()
        elapsed = 0.0 if self._last_frame_time is None else now - self._last_frame_time
        self._last_frame_time = now
        self._tick_accumulator = min(self._tick_accumulator + elapsed,
                                     self.TICK_S * self.MAX_CATCH_UP_TICKS)
        predictor = self.predictor
        if predictor is None:
            return
        ticks = 0
        while self._tick_accumulator >= self.TICK_S:
            self._tick_accumulator -= self.TICK_S
            predictor.step(held | self._latched_bits)
            self._latched_bits = 0
            ticks += 1
        if ticks:
            self.net.send_inputs(predictor.seq, list(predictor.recent_bits))

    def _play_predicted_sounds(self):
        me = self.local_players.get(self.my_id)
        if me is not None and me.sounds_to_play:
            for name in me.sounds_to_play:
                music.play_sfx(name)
            me.sounds_to_play.clear()

    def network_game_loop(self):
        if self.net is None:
            self.game_state = "MENU_MAIN"
            return
        music.start()
        self._tick_accumulator = 0.0
        self._last_frame_time = None
        self._latched_bits = 0

        while self.game_state == "IN_GAME" and self.running:
            if self.settings.get('video', {}).get('fullscreen', False):
                pygame.mouse.set_visible(
                    self.inner_game_state in ("PAUSE", "SETTINGS_GAME", "BRIGHTNESS_GAME"))

            pos_mouse = pygame.mouse.get_pos()
            held, actions = 0, []
            if self.inner_game_state == "GAME":
                held, actions = self.handle_game_events()
            elif self.inner_game_state == "PAUSE":
                self.handle_pause_events(pos_mouse)
            elif self.inner_game_state == "SETTINGS_GAME":
                if not self.settings_temp:
                    self.settings_temp = copy.deepcopy(self.settings)
                self.previous_game_state = "_BACK_PAUSE"
                self.handle_menu_settings(pos_mouse)
                if self.game_state == "_BACK_PAUSE":
                    self.game_state = "IN_GAME"
                    self.inner_game_state = "PAUSE"
            elif self.inner_game_state == "BRIGHTNESS_GAME":
                self.handle_menu_brightness(pos_mouse)

            if self.game_state != "IN_GAME" or not self.running:
                break

            for action in actions:
                self.net.send_action(action)
            self._run_prediction_ticks(held)
            self._apply_net_messages(self.net.poll())
            if self.net.error:
                print(f"[CLIENT] network error: {self.net.error}")
                self.message_error_connection = i18n.get_text("net_error_lost")
                self.cleanup_connection()
                self.game_state = "MENU_MAIN"
                break
            self._update_interpolation()
            self._play_predicted_sounds()

            self.draw_game()
            if self.inner_game_state == "PAUSE":
                self.draw_menu_pause()
            elif self.inner_game_state == "SETTINGS_GAME":
                self.draw_menu_settings()
            elif self.inner_game_state == "BRIGHTNESS_GAME":
                self.draw_menu_brightness()

            # Lore bubble / popups are drawn on the final screen (above the zoom)
            if self.bubble_lore and self.bubble_lore.visible:
                self.bubble_lore.draw(self.screen)
            if self.popup_payment and self.popup_payment.visible:
                self.popup_payment.draw(self.screen)
            if self.popup_shop_upgrades and self.popup_shop_upgrades.visible:
                self.popup_shop_upgrades.draw(self.screen)

            if self.journal_quest:
                self.journal_quest.update(
                    self.local_key_item,
                    next(iter(self.local_doors.values()), None),
                    self.boss_local,
                    enemies_killed=self._enemies_killed_total,
                    souls=self._souls_harvested_total)
                key_journal = self.settings.get('controls', {}).get('journal', 'i')
                self.journal_quest.draw(self.screen, key_journal=key_journal)

            pygame.display.flip()

            # Ending sequence once the exit door is open
            door = self.local_doors.get(0)
            if not self._sequence_end_triggered and door is not None and door.is_open:
                self._sequence_end_triggered = True
                self.play_sequence_end()
                return

            self.clock.tick(FPS)


from client.end_crystal_sequence import play_sequence_end as _play_sequence_end
GameLoopMixin.play_sequence_end = _play_sequence_end