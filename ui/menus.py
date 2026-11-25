# ui/menus.py
# Mixin that handles every menu of the game.
# Inherited by the Client class - every method accesses self.
# Includes the "interact" key in the controls.

import pygame
from utils import clipboard
from utils.paths import asset_path
import copy
import re
import time

from settings import *
from utils import i18n, music
from utils.cache import render_text
from ui.button import Button
from ui.slider import Slider
from ui.visual_effects import draw_background_echo, draw_title_neon, draw_separator_neon, draw_panel
from storage import settings_io, saves
from net.framing import list_local_ips, local_ip
from core.player import NUM_SKINS


class MenusMixin:
    """Methods that create, handle and draw every menu."""

    # ==================================================================
    # WIDGET CREATION
    # ==================================================================

    def create_widgets_menu_main(self):
        cx = self.cx
        lw = self._width_button()
        bh = self._height_button()
        esp = self._spacing_button() + bh

        num_buttons = 6
        height_group = num_buttons * esp - self._spacing_button()
        # Group of buttons vertically centered in the lower half
        y_start = int(self.height_screen * 0.67) - height_group // 2

        def _btn(i, text, style="normal"):
            y = y_start + i * esp
            return Button(cx - lw // 2, y, lw, bh, text, self.font_button, style=style)

        self.btn_new_game = _btn(0, i18n.get_text("menu_new_game"))
        self.btn_continue       = _btn(1, i18n.get_text("menu_continue"))
        self.btn_join       = _btn(2, i18n.get_text("menu_join"))
        self.btn_settings      = _btn(3, i18n.get_text("menu_settings"))
        self.btn_tutorial        = _btn(4, "Tutoriel", style="ghost")
        self.btn_quit         = _btn(5, i18n.get_text("menu_quit"), style="ghost")

        self.buttons_menu_main = [
            self.btn_new_game, self.btn_continue,
            self.btn_join, self.btn_settings,
            self.btn_tutorial, self.btn_quit
        ]
        self.btn_copy_ip_local = Button(0, 0, self._scale(300), self._scale(36), "", self.font_small)

    def create_widgets_menu_join(self):
        cx = self.cx
        lw = self._width_button()
        bh = self._height_button()
        cy = self.cy

        h_input = self._scale(46)

        self.input_box_ip   = pygame.Rect(cx - lw // 2, cy - 30, lw, h_input)
        self.input_ip_text = ""
        self.input_ip_active = False
        self.input_ip_cursor_pos = 0

        self.btn_connect       = Button(cx - lw // 2, cy + self._scale(40), lw, bh,
                                        i18n.get_text("join_connect"),
                                        self.font_button)
        self.btn_back_join = Button(cx - lw // 2, cy + self._scale(40) + bh + self._scale(12), lw, bh,
                                        i18n.get_text("join_back"),
                                        self.font_button, style="ghost")
        self.btn_error_ok = Button(cx - self._scale(60), cy + self._scale(90), self._scale(120), bh, "OK",
                                    self.font_button, style="danger")
        lw_paste = self._scale(90)
        self.btn_paste_ip = Button(
            cx + lw // 2 + self._scale(10), cy - 30, lw_paste, h_input,
            "Coller", self.font_button, style="ghost"
        )

    def create_widgets_menu_settings(self):
        cx = self.cx
        col_right = cx + self._scale(60)
        lw_param = max(200, self._scale(300))
        bh_param = max(34, self._scale(38))

        def _p(text=""):
            return Button(col_right, 0, lw_param, bh_param, text, self.font_small)

        self.btn_copy_ip_local    = _p()
        self.btn_change_language      = _p()
        self.btn_toggle_fullscreen  = _p()
        self.btn_change_screen       = _p()
        self.btn_change_resolution  = _p()

        # Navigation arrows for the resolution - integrated in the column
        arrow_w_res = bh_param
        gap_res = max(4, self._scale(4))
        self.btn_resolution_prev = Button(col_right, 0, arrow_w_res, bh_param,
                                          "<", self.font_button)
        self.btn_resolution_next = Button(col_right, 0, arrow_w_res, bh_param,
                                          ">", self.font_button)
        self.btn_change_resolution.rect.width = lw_param - 2 * (arrow_w_res + gap_res)
        self.btn_toggle_music      = _p()
        self.btn_toggle_sfx          = _p()
        self.btn_open_brightness   = _p()
        self.btn_change_left      = _p()
        self.btn_change_right      = _p()
        self.btn_change_jump        = _p()
        self.btn_change_echo        = _p()
        self.btn_change_attack     = _p()
        self.btn_change_dash        = _p()
        self.btn_change_echo_dir    = _p()
        self.btn_change_interact   = _p()
        self.btn_change_torch      = _p()
        self.btn_change_journal     = _p()

        lw = self._width_button()
        bh = self._height_button()
        y_bottom = self.height_screen - max(70, self.height_screen // 14)

        self.btn_apply_params = Button(cx - lw - 10, y_bottom, lw, bh,
                                        i18n.get_text("param_apply"),
                                        self.font_button, style="confirm")
        self.btn_back_params    = Button(cx + 10, y_bottom, lw, bh,
                                        i18n.get_text("param_back"),
                                        self.font_button, style="ghost")

        self.btn_change_skin   = _p()
        self.input_nickname_active = False
        self.input_nickname_rect  = pygame.Rect(col_right, 0, lw_param, bh_param)

        self.buttons_menu_params_scrollables = [
            self.btn_change_language,
            self.btn_toggle_fullscreen,
            self.btn_change_screen,
            self.btn_change_resolution,
            self.btn_resolution_prev,
            self.btn_resolution_next,
            self.btn_toggle_music,
            self.btn_toggle_sfx,
            self.btn_open_brightness,
            self.btn_change_left, self.btn_change_right,
            self.btn_change_jump, self.btn_change_echo,
            self.btn_change_attack, self.btn_change_dash,
            self.btn_change_interact,
            self.btn_change_torch,
            self.btn_change_journal,
            self.btn_change_skin,
            self.btn_copy_ip_local,
        ]
        self.buttons_menu_params_fixed = [
            self.btn_apply_params, self.btn_back_params
        ]

        self._ip_local_cache = None
        if not hasattr(self, '_feedback_copy'):
            self._feedback_copy = {}

        self.btn_change_skin   = _p()
        self.input_nickname_active = False
        self.input_nickname_rect  = pygame.Rect(col_right, 0, lw_param, bh_param)

    def create_widgets_menu_brightness(self):
        cx = self.cx
        lw = self._width_button()
        bh = self._height_button()

        width_slider = max(320, int(self.width_screen * 0.5))
        height_slider = max(14, self.height_screen // 60)
        y_slider = int(self.height_screen * 0.78)
        value_init = self.settings.get('video', {}).get('brightness', 0.3)
        self.slider_brightness = Slider(
            cx - width_slider // 2, y_slider,
            width_slider, height_slider,
            value=value_init, font=self.font_text
        )

        y_bottom = self.height_screen - max(70, self.height_screen // 14)
        self.btn_apply_brightness = Button(
            cx - lw - 10, y_bottom, lw, bh,
            i18n.get_text("param_apply"),
            self.font_button, style="confirm"
        )
        self.btn_back_brightness = Button(
            cx + 10, y_bottom, lw, bh,
            i18n.get_text("param_back"),
            self.font_button, style="ghost"
        )

        self._background_brightness = None
        self._preview_brightness_cache = None

    def create_widgets_menu_confirmation(self):
        cx = self.cx
        cy = self.cy
        w_popup = max(400, self._scale(520))
        h_popup = max(220, self._scale(280))
        self.rect_popup = pygame.Rect(cx - w_popup // 2, cy - h_popup // 2,
                                    w_popup, h_popup)
        bh = self._height_button()
        lw_btn = w_popup // 3
        margin = self._scale(10)
        margin_bottom = self._scale(16)
        self.btn_popup_yes = Button(cx - lw_btn - margin, cy + h_popup // 2 - bh - margin_bottom,
                                    lw_btn, bh,
                                    i18n.get_text("popup_yes"),
                                    self.font_button, style="confirm")
        self.btn_popup_not = Button(cx + margin, cy + h_popup // 2 - bh - margin_bottom,
                                    lw_btn, bh,
                                    i18n.get_text("popup_not"),
                                    self.font_button, style="danger")
        self.buttons_confirmation = [self.btn_popup_yes, self.btn_popup_not]

    def create_widgets_menu_pause(self):
        cx = self.cx
        lw = self._width_button()
        bh = self._height_button()
        esp = bh + self._spacing_button()
        y0 = self.cy - esp

        self.btn_pause_resume    = Button(cx - lw // 2, y0,            lw, bh,
                                            i18n.get_text("pause_resume"),
                                            self.font_button)
        self.btn_pause_settings   = Button(cx - lw // 2, y0 + esp,      lw, bh,
                                            i18n.get_text("pause_settings"),
                                            self.font_button)
        self.btn_pause_quit      = Button(cx - lw // 2, y0 + esp * 2,  lw, bh,
                                            i18n.get_text("pause_quit_session"),
                                            self.font_button, style="ghost")

        self.buttons_menu_pause = [
            self.btn_pause_resume, self.btn_pause_settings,
            self.btn_pause_quit
        ]

        self.surface_background_pause = pygame.Surface(
            (self.width_screen, self.height_screen), pygame.SRCALPHA)
        self.surface_background_pause.fill(COLOR_PAUSE_BACKGROUND)

    def create_widgets_menu_slots(self):
        self.info_slots  = []
        self.buttons_slots = []
        cx  = self.cx
        lw  = max(400, int(self.width_screen * 0.55))
        bh  = max(64, self.height_screen // 14)
        esp = bh + max(14, self.height_screen // 60)

        num = NUM_SAVE_SLOTS
        height_group = num * esp - (esp - bh)
        y_start = self.cy - height_group // 2

        for i in range(num):
            btn = Button(cx - lw // 2, y_start + i * esp, lw, bh,
                        f"Slot {i+1}", self.font_button)
            self.buttons_slots.append(btn)

        y_back = y_start + num * esp + 16
        self.btn_back_slots = Button(cx - self._width_button() // 2, y_back,
                                    self._width_button(), self._height_button(),
                                    i18n.get_text("join_back"),
                                    self.font_button, style="ghost")

    # ==================================================================
    # HANDLING + DRAWING - MAIN MENU
    # ==================================================================

    def handle_menu_main(self, pos_mouse):
        for btn in self.buttons_menu_main:
            btn.verify_hover(pos_mouse)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"
            if self.btn_new_game.verify_click(event):
                self.game_state = "MENU_NEW_GAME"
                self.info_slots = saves.get_info_slots()
            if self.btn_continue.verify_click(event):
                self.game_state = "MENU_CONTINUE"
                self.info_slots = saves.get_info_slots()
            if self.btn_join.verify_click(event):
                self.game_state = "MENU_JOIN"
            if self.btn_tutorial.verify_click(event):
                self._launch_tutorial()
            if self.btn_settings.verify_click(event):
                self.settings_temp = copy.deepcopy(self.settings)
                self.previous_game_state = "MENU_MAIN"
                self._ip_local_cache = local_ip()
                self.game_state = "MENU_SETTINGS"
            if self.btn_quit.verify_click(event):
                self.game_state = "QUIT"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                link_rect = self.font_small.render("florian-croiset.github.io/jeusite/", True, COLOR_CYAN_DARK).get_rect(bottomleft=(20, self.height_screen - 12))
                if link_rect.collidepoint(event.pos):
                    import webbrowser
                    webbrowser.open("https://florian-croiset.github.io/jeusite/")

    def draw_menu_main(self):
        # --- Background: illustrated PNG image ---
        if not hasattr(self, '_background_menu_cache') or self._background_menu_cache is None:
            import os
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(root, "assets", "background_menu.png")
            try:
                img = pygame.image.load(path).convert()
                self._background_menu_cache = pygame.transform.smoothscale(
                    img, (self.width_screen, self.height_screen))
            except Exception:
                # Fallback: procedural background if the image is missing
                self._background_menu_cache = None

        if self._background_menu_cache is not None:
            self.screen.blit(self._background_menu_cache, (0, 0))
        else:
            self._draw_background_menu2()

        # --- Buttons ---
        for btn in self.buttons_menu_main:
            btn.draw(self.screen)

        # --- Version ---
        size_bottom = max(22, self._scale(26))
        if getattr(self, '_font_bottom_size', None) != size_bottom:
            self._font_bottom = pygame.font.Font(None, size_bottom)
            self._font_bottom_size = size_bottom
        font_bottom = self._font_bottom
        ver = font_bottom.render("v2.2", True, COLOR_TEXT_DARK)
        self.screen.blit(ver, (self.width_screen - ver.get_width() - 20,
                            self.height_screen - ver.get_height() - 12))

        # --- Website link ---
        link_text = "https://florian-croiset.github.io/jeusite/"
        pos_mouse = pygame.mouse.get_pos()
        link_surf = font_bottom.render(link_text, True, COLOR_CYAN)
        link_rect = link_surf.get_rect(bottomleft=(20, self.height_screen - 12))
        if link_rect.collidepoint(pos_mouse):
            link_surf = font_bottom.render(link_text, True, COLOR_CYAN)
        self.screen.blit(link_surf, link_rect)
    
    def _draw_background_menu2(self):
        """Pixel-art cave background for the sub-menus."""
        if not hasattr(self, '_background_menu2_cache') or self._background_menu2_cache is None:
            import os
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(root, "assets", "background_menu2.png")
            try:
                img = pygame.image.load(path).convert()
                self._background_menu2_cache = pygame.transform.smoothscale(
                    img, (self.width_screen, self.height_screen))
            except Exception:
                self._background_menu2_cache = None

        if self._background_menu2_cache is not None:
            self.screen.blit(self._background_menu2_cache, (0, 0))
        else:
            draw_background_echo(self.screen, self.width_screen, self.height_screen, self.time_anim)

    # ==================================================================
    # HANDLING + DRAWING - JOIN MENU
    # ==================================================================

    def _try_connection_join(self):
        text = self.input_ip_text.strip()
        if RELAY_HOST and re.fullmatch(r"[A-Za-z]{6}", text):
            connected = self.connect_relay(text)          # 6 letters = relay room code
        else:
            connected = self.connect(text if text else local_ip())
        if connected:
            self.game_state = "IN_GAME"

    def _paste_clipboard(self):
        return clipboard.paste_text()

    def handle_menu_join(self, pos_mouse):
        if self.message_error_connection:
            self.btn_error_ok.verify_hover(pos_mouse)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.game_state = "QUIT"
                if self.btn_error_ok.verify_click(event):
                    self.message_error_connection = None
            return

        self.btn_connect.verify_hover(pos_mouse)
        self.btn_back_join.verify_hover(pos_mouse)
        self.btn_paste_ip.verify_hover(pos_mouse)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"

            if self.btn_back_join.verify_click(event):
                self.game_state = "MENU_MAIN"

            if self.btn_connect.verify_click(event):
                self._try_connection_join()

            if event.type == pygame.MOUSEBUTTONDOWN:
                self.input_ip_active = self.input_box_ip.collidepoint(event.pos)

            if self.btn_paste_ip.verify_click(event):
                text_pasted = self._paste_clipboard()
                if text_pasted:
                    self.input_ip_text = text_pasted
                    self.input_ip_active = True
                    self.input_ip_cursor_pos = len(self.input_ip_text)

            if event.type == pygame.KEYDOWN and self.input_ip_active:
                pos = self.input_ip_cursor_pos
                txt = self.input_ip_text
                if event.key == pygame.K_RETURN:
                    self._try_connection_join()
                elif event.key == pygame.K_LEFT:
                    self.input_ip_cursor_pos = max(0, pos - 1)
                elif event.key == pygame.K_RIGHT:
                    self.input_ip_cursor_pos = min(len(txt), pos + 1)
                elif event.key == pygame.K_HOME:
                    self.input_ip_cursor_pos = 0
                elif event.key == pygame.K_END:
                    self.input_ip_cursor_pos = len(txt)
                elif event.key == pygame.K_BACKSPACE and pos > 0:
                    self.input_ip_text = txt[:pos - 1] + txt[pos:]
                    self.input_ip_cursor_pos = pos - 1
                elif event.key == pygame.K_DELETE and pos < len(txt):
                    self.input_ip_text = txt[:pos] + txt[pos + 1:]
                elif event.unicode and event.unicode.isprintable():
                    self.input_ip_text = txt[:pos] + event.unicode + txt[pos:]
                    self.input_ip_cursor_pos = pos + 1

    def draw_menu_join(self):
        self._draw_background_menu2()
        draw_title_neon(self.screen, self.font_title,
                            i18n.get_text("join_title"),
                            self.cx, self.height_screen // 7)

        pan_w = self._width_button() + self._scale(80)
        pan_h = self._scale(260)
        pan_rect = pygame.Rect(self.cx - pan_w // 2,
                            self.cy - pan_h // 2 - self._scale(20),
                            pan_w, pan_h)
        draw_panel(self.screen, pan_rect)

        y_content = pan_rect.y + self._scale(36)

        label_text = i18n.get_text("join_label_ip")
        label = self.font_text.render(label_text, True, COLOR_TEXT)
        self.screen.blit(label, label.get_rect(center=(self.cx, y_content)))
        y_content += self._scale(28)

        input_box = self.input_box_ip
        input_box.y = y_content
        edge_color = COLOR_CYAN if self.input_ip_active else COLOR_CYAN_DARK
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, input_box, border_radius=6)
        pygame.draw.rect(self.screen, edge_color, input_box, width=1, border_radius=6)
        txt_surf = self.font_text.render(self.input_ip_text, True, COLOR_TEXT)
        self.screen.blit(txt_surf, (input_box.x + self._scale(12), input_box.y + self._scale(10)))
        if self.input_ip_active and int(time.time() * 2) % 2 == 0:
            pos_ip = max(0, min(len(self.input_ip_text), self.input_ip_cursor_pos))
            before_ip = self.font_text.render(self.input_ip_text[:pos_ip], True, COLOR_TEXT)
            cx_cur = input_box.x + self._scale(14) + before_ip.get_width()
            cy_cur = input_box.y + self._scale(8)
            pygame.draw.rect(self.screen, COLOR_CYAN,
                            pygame.Rect(cx_cur, cy_cur, 2,
                                        self.font_text.get_height() - 6))

        self.btn_paste_ip.rect.y = self.input_box_ip.y
        self.btn_paste_ip.draw(self.screen)

        y_btns = self.input_box_ip.y + self._scale(60)
        self.btn_connect.rect.y = y_btns
        self.btn_back_join.rect.y = y_btns + self._height_button() + self._scale(12)
        self.btn_connect.draw(self.screen)
        self.btn_back_join.draw(self.screen)

        if self.message_error_connection:
            self._draw_popup_error()

    def _draw_popup_error(self):
        cx, cy = self.cx, self.cy
        w_popup = max(440, self._scale(600))
        h_popup = max(200, self._scale(260))
        rect_popup = pygame.Rect(cx - w_popup // 2, cy - h_popup // 2,
                                w_popup, h_popup)

        overlay = pygame.Surface((self.width_screen, self.height_screen), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        draw_panel(self.screen, rect_popup, color_border=(220, 50, 50))
        title_surf = self.font_text.render("Erreur de connexion", True, (220, 50, 50))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, rect_popup.y + self._scale(36))))
        draw_separator_neon(self.screen,
                                rect_popup.x + self._scale(20), rect_popup.y + self._scale(58),
                                rect_popup.right - self._scale(20), color=(220, 50, 50))

        font_msg = self.font_small
        lines = self.message_error_connection.split('\n')
        line_h = self._scale(26)
        for i, line in enumerate(lines):
            s = font_msg.render(line, True, COLOR_TEXT)
            self.screen.blit(s, s.get_rect(center=(cx, rect_popup.y + self._scale(90) + i * line_h)))

        self.btn_error_ok.rect.center = (cx, rect_popup.bottom - self._scale(36))
        self.btn_error_ok.draw(self.screen)

    # ==================================================================
    # HANDLING + DRAWING - SLOTS MENU
    # ==================================================================

    def handle_menu_slots(self, pos_mouse):
        all = self.buttons_slots + [self.btn_back_slots]
        for btn in all:
            btn.verify_hover(pos_mouse)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"
            if self.btn_back_slots.verify_click(event):
                self.game_state = "MENU_MAIN"
            for id_slot, btn_slot in enumerate(self.buttons_slots):
                if btn_slot.verify_click(event):
                    if self.game_state == "MENU_NEW_GAME":
                        if not self.info_slots[id_slot]["is_empty"]:
                            self.id_slot_to_overwrite = id_slot
                            self.game_state = "MENU_CONFIRMATION"
                        else:
                            self.launch_local_game(id_slot, is_new_game=True)
                    elif self.game_state == "MENU_CONTINUE":
                        if not self.info_slots[id_slot]["is_empty"]:
                            self.launch_local_game(id_slot, is_new_game=False)

    def draw_menu_slots(self):
        self._draw_background_menu2()
        title_key_item = ("slots_title_new"
                    if self.game_state == "MENU_NEW_GAME"
                    else "slots_title_continue")
        draw_title_neon(self.screen, self.font_title,
                            i18n.get_text(title_key_item),
                            self.cx, self.height_screen // 7)

        for id_slot, btn_slot in enumerate(self.buttons_slots):
            info = self.info_slots[id_slot] if id_slot < len(self.info_slots) else None
            if not info:
                continue
            is_empty = info["is_empty"]
            mode_continue = (self.game_state == "MENU_CONTINUE")
            if mode_continue and is_empty:
                btn_slot.style = "ghost"
            else:
                btn_slot.style = "normal"
                btn_slot._define_style(btn_slot.style)
            btn_slot.text = ""
            btn_slot.draw(self.screen)
            hovered = btn_slot.is_hovered
            color_name = btn_slot.color_text_hover if hovered else btn_slot.color_text
            name_surf = self.font_button.render(info["name"], True, color_name)
            if info["description"]:
                offset = name_surf.get_height() // 2 + 4
                self.screen.blit(name_surf, name_surf.get_rect(
                    center=(btn_slot.rect.centerx,
                            btn_slot.rect.centery - offset)))
                desc_c = COLOR_TEXT_DARK if (mode_continue and is_empty) else COLOR_TEXT
                desc = self.font_small.render(info["description"], True, desc_c)
                self.screen.blit(desc, desc.get_rect(
                    center=(btn_slot.rect.centerx,
                            btn_slot.rect.centery + offset)))
            else:
                self.screen.blit(name_surf, name_surf.get_rect(center=btn_slot.rect.center))
        self.btn_back_slots.draw(self.screen)

    # ==================================================================
    # HANDLING + DRAWING - CONFIRMATION MENU
    # ==================================================================

    def handle_menu_confirmation(self, pos_mouse):
        for btn in self.buttons_confirmation:
            btn.verify_hover(pos_mouse)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"
            if self.btn_popup_yes.verify_click(event):
                self.launch_local_game(self.id_slot_to_overwrite,
                                        is_new_game=True)
            if self.btn_popup_not.verify_click(event):
                self.id_slot_to_overwrite = None
                self.game_state = "MENU_NEW_GAME"

    def draw_menu_confirmation(self):
        self.draw_menu_slots()
        overlay = pygame.Surface((self.width_screen, self.height_screen),
                                pygame.SRCALPHA)
        overlay.fill((0, 0, 10, 180))
        self.screen.blit(overlay, (0, 0))
        draw_panel(self.screen, self.rect_popup,
                        color_border=COLOR_VIOLET, alpha_background=245)
        title = self.font_button.render(
            i18n.get_text("popup_title"), True, COLOR_VIOLET_LIGHT)
        self.screen.blit(title, title.get_rect(
            center=(self.rect_popup.centerx, self.rect_popup.y + self._scale(50))))
        draw_separator_neon(self.screen,
                                self.rect_popup.x + self._scale(20), self.rect_popup.y + self._scale(76),
                                self.rect_popup.right - self._scale(20),
                                color=COLOR_VIOLET_DARK, alpha=140)
        msg = self.font_text.render(
            i18n.get_text("popup_message"), True, COLOR_TEXT)
        self.screen.blit(msg, msg.get_rect(
            center=(self.rect_popup.centerx, self.rect_popup.centery - self._scale(10))))
        self.btn_popup_yes.draw(self.screen)
        self.btn_popup_not.draw(self.screen)

    # ==================================================================
    # HANDLING + DRAWING - SETTINGS MENU
    # ==================================================================

    def handle_menu_settings(self, pos_mouse):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"
            if event.type == pygame.MOUSEWHEEL:
                self.scroll_y_params += event.y * 20
                self.scroll_y_params = max(-500, min(0, self.scroll_y_params))
            if self.key_to_modify:
                if event.type == pygame.KEYDOWN:
                    if event.key not in [pygame.K_ESCAPE, pygame.K_RETURN]:
                        name_key = pygame.key.name(event.key)
                        self.settings_temp['controls'][self.key_to_modify] = name_key
                        self.key_to_modify = None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.settings_temp['controls'][self.key_to_modify] = f"mouse_{event.button}"
                    self.key_to_modify = None
            else:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.settings_temp = {}
                    self.game_state = self.previous_game_state
                if self.btn_back_params.verify_click(event):
                    self.settings_temp = {}
                    self.key_to_modify = None
                    self.scroll_y_params = 0
                    self.game_state = self.previous_game_state
                if self.btn_apply_params.verify_click(event):
                    self.settings = copy.deepcopy(self.settings_temp)
                    settings_io.save_settings(self.settings)
                    if hasattr(self, '_profile_nickname'):
                        self._profile_nickname = self.settings.get('profile', {}).get('nickname', 'Player')
                        self._profile_skin   = self.settings.get('profile', {}).get('skin', 0)
                    self.apply_settings_video()
                    self._recompute_codes_keys()
                    music.toggle(self.settings['video'].get('music', True))
                    music.activate_sfx(self.settings['sounds'].get('enable_sfx', True))
                    self.refresh_languages_widgets()
                    self.key_to_modify = None
                    self.scroll_y_params = 0
                    self.game_state = self.previous_game_state
                if self.btn_toggle_fullscreen.verify_click(event):
                    self.settings_temp['video']['fullscreen'] = \
                        not self.settings_temp['video']['fullscreen']
                if self.btn_change_screen.verify_click(event):
                    num = len(getattr(self, '_desktop_sizes', [(0, 0)]))
                    if num > 1:
                        cur = self.settings_temp['video'].get('display_index', 0)
                        new_idx = (cur + 1) % num
                        self.settings_temp['video']['display_index'] = new_idx
                        if self.settings_temp['video']['fullscreen']:
                            w_e, h_e = self._desktop_sizes[new_idx]
                            self.settings_temp['video']['resolution'] = [w_e, h_e]
                def _cycle_resolution(direction):
                    if self.settings_temp['video']['fullscreen']:
                        return
                    idx_screen = self.settings_temp['video'].get('display_index', 0)
                    sizes = getattr(self, '_desktop_sizes', [self.resolution_native])
                    if idx_screen < 0 or idx_screen >= len(sizes):
                        idx_screen = 0
                    resolutions = get_compatible_resolutions(sizes[idx_screen])
                    current = tuple(self.settings_temp['video'].get(
                        'resolution', [SCREEN_WIDTH, SCREEN_HEIGHT]))
                    try:
                        idx = resolutions.index(current)
                        new = resolutions[(idx + direction) % len(resolutions)]
                    except ValueError:
                        new = resolutions[0]
                    self.settings_temp['video']['resolution'] = list(new)

                if self.btn_change_resolution.verify_click(event):
                    _cycle_resolution(1)
                if self.btn_resolution_prev.verify_click(event):
                    _cycle_resolution(-1)
                if self.btn_resolution_next.verify_click(event):
                    _cycle_resolution(1)
                if self.btn_toggle_music.verify_click(event):
                    self.settings_temp['video']['music'] = not self.settings_temp['video'].get('music', True)
                if self.btn_toggle_sfx.verify_click(event):
                    self.settings_temp['sounds']['enable_sfx'] = not self.settings_temp['sounds'].get('enable_sfx', True)
                if self.btn_open_brightness.verify_click(event):
                    self._open_menu_brightness()
                if self.btn_change_language.verify_click(event):
                    languages = ['fr', 'en']
                    current = self.settings_temp['gameplay']['language']
                    try:
                        idx = languages.index(current)
                        new = languages[(idx + 1) % len(languages)]
                    except ValueError:
                        new = 'fr'
                    self.settings_temp['gameplay']['language'] = new
                if self.btn_change_left.verify_click(event):
                    self.key_to_modify = "left"
                if self.btn_change_right.verify_click(event):
                    self.key_to_modify = "right"
                if self.btn_change_jump.verify_click(event):
                    self.key_to_modify = "jump"
                if self.btn_change_echo.verify_click(event):
                    self.key_to_modify = "echo"
                if self.btn_change_attack.verify_click(event):
                    self.key_to_modify = "attack"
                if self.btn_change_dash.verify_click(event):
                    self.key_to_modify = 'dash'
                if self.btn_change_echo_dir.verify_click(event):
                    self.key_to_modify = 'echo_dir'
                if self.btn_change_interact.verify_click(event):
                    self.key_to_modify = 'interact'
                if self.btn_change_torch.verify_click(event):
                    self.key_to_modify = 'torch'
                if self.btn_change_journal.verify_click(event):
                    self.key_to_modify = 'journal'
                if self.btn_copy_ip_local.verify_click(event):
                    ip = local_ip()
                    if self.copy_in_clipboard(ip):
                        self._feedback_copy['ip_local'] = pygame.time.get_ticks()
                # Click on the nickname field
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.input_nickname_active = self.input_nickname_rect.collidepoint(event.pos)

                # Nickname input
                if self.input_nickname_active and event.type == pygame.KEYDOWN:
                    nickname_current = self.settings_temp.get('profile', {}).get('nickname', '')
                    if event.key == pygame.K_BACKSPACE:
                        self.settings_temp.setdefault('profile', {})['nickname'] = nickname_current[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        self.input_nickname_active = False
                    elif event.unicode.isprintable() and len(nickname_current) < 16:
                        self.settings_temp.setdefault('profile', {})['nickname'] = nickname_current + event.unicode

                # Skin cycling
                if self.btn_change_skin.verify_click(event):
                    skin_current = self.settings_temp.get('profile', {}).get('skin', 0)
                    self.settings_temp.setdefault('profile', {})['skin'] = (skin_current + 1) % NUM_SKINS
        for btn in self.buttons_menu_params_fixed + self.buttons_menu_params_scrollables:
            btn.verify_hover(pos_mouse)

    def draw_menu_settings(self):
        self._draw_background_menu2()
        size_title_params = max(48, self.height_screen // 14)
        if getattr(self, '_font_title_params_size', None) != size_title_params:
            self._font_title_params = pygame.font.Font(None, size_title_params)
            self._font_title_params_size = size_title_params
        draw_title_neon(self.screen, self._font_title_params,
                            i18n.get_text("param_title"),
                            self.cx, self.height_screen // 14)

        y = int(self.height_screen * 0.12) + self.scroll_y_params
        params = self.settings_temp if self.settings_temp else self.settings
        col_right = self.cx + self._scale(60)
        col_left = 100
        esp_line = max(44, self.height_screen // 22)

        def section(title_text):
            nonlocal y
            draw_separator_neon(self.screen, col_left, y,
                                    self.width_screen - col_left, alpha=100)
            y += 6
            s = render_text(self.font_button, title_text, COLOR_VIOLET_LIGHT)
            self.screen.blit(s, (col_left, y))
            y += esp_line

        _names_mouse = {'mouse_1': 'Clic G', 'mouse_2': 'Clic M', 'mouse_3': 'Clic D',
                        'mouse_4': 'Souris 4', 'mouse_5': 'Souris 5'}

        def _fmt_key(val):
            return _names_mouse.get(val, val.upper() if val else '?')

        def line_control(label, key_item_json, btn):
            nonlocal y
            lbl = render_text(self.font_text, label, COLOR_TEXT)
            self.screen.blit(lbl, (col_left + 20, y + 6))
            btn.rect.y = y
            txt = _fmt_key(params['controls'][key_item_json])
            if self.key_to_modify == key_item_json:
                txt = i18n.get_text("param_waiting_key")
                btn.style = "confirm"
            else:
                btn.style = "normal"
                btn._define_style(btn.style)
            btn.text = txt
            btn.draw(self.screen)
            y += esp_line

        def line_toggle(label, value_bool, btn, txt_true, txt_false):
            nonlocal y
            lbl = render_text(self.font_text, label, COLOR_TEXT)
            self.screen.blit(lbl, (col_left + 20, y + 6))
            btn.rect.y = y
            btn.text = txt_true if value_bool else txt_false
            btn.style = "confirm" if value_bool else "normal"
            btn._define_style(btn.style)
            btn.draw(self.screen)
            y += esp_line

        def line_ip(label, text_btn, btn):
            nonlocal y
            lbl = render_text(self.font_text, label, COLOR_TEXT)
            self.screen.blit(lbl, (col_left + 20, y + 6))
            btn.rect.y = y
            btn.text = text_btn
            btn.draw(self.screen)
            y += esp_line

        section(i18n.get_text("param_section_gameplay"))
        lbl_lang = render_text(self.font_text, i18n.get_text("param_language"), COLOR_TEXT)
        self.screen.blit(lbl_lang, (col_left + 20, y + 6))
        self.btn_change_language.rect.y = y
        self.btn_change_language.text = params['gameplay']['language'].upper()
        self.btn_change_language.draw(self.screen)
        y += esp_line

        section(i18n.get_text("param_section_profile"))

        # Nickname
        lbl_ps = render_text(self.font_text, i18n.get_text("param_nickname"), COLOR_TEXT)
        self.screen.blit(lbl_ps, (col_left + 20, y + 6))
        self.input_nickname_rect.topleft = (col_right, y)
        edge_ps = COLOR_CYAN if self.input_nickname_active else COLOR_CYAN_DARK
        pygame.draw.rect(self.screen, COLOR_INPUT_BOX, self.input_nickname_rect, border_radius=6)
        pygame.draw.rect(self.screen, edge_ps, self.input_nickname_rect, width=1, border_radius=6)
        nickname_val = params.get('profile', {}).get('nickname', '')
        txt_ps = self.font_text.render(nickname_val, True, COLOR_TEXT)
        self.screen.blit(txt_ps, (self.input_nickname_rect.x + 8, self.input_nickname_rect.y + 6))
        if self.input_nickname_active and int(time.time() * 2) % 2 == 0:
            cx_cur = self.input_nickname_rect.x + 10 + txt_ps.get_width()
            pygame.draw.rect(self.screen, COLOR_CYAN,
                             pygame.Rect(cx_cur, self.input_nickname_rect.y + 6,
                                         2, self.font_text.get_height() - 4))
        y += esp_line

        # Skin
        skin_val = params.get('profile', {}).get('skin', 0)
        lbl_sk = render_text(self.font_text, i18n.get_text("param_appearance"), COLOR_TEXT)
        self.screen.blit(lbl_sk, (col_left + 20, y + 6))
        self.btn_change_skin.rect.topleft = (col_right, y)
        skin_name = (i18n.get_text("skin_scout") if skin_val == 0
                     else i18n.get_text("skin_specter") if skin_val == 1 else "?")
        self.btn_change_skin.text = f"{skin_name}  ({skin_val + 1}/{NUM_SKINS})"
        self.btn_change_skin.draw(self.screen)
        y += esp_line
        # ^ END OF INSERTION

        section(i18n.get_text("param_section_video"))
        line_toggle(i18n.get_text("param_fullscreen"),
                    params['video']['fullscreen'],
                    self.btn_toggle_fullscreen,
                    i18n.get_text("param_yes"),
                    i18n.get_text("param_not"))

        num_screens = len(getattr(self, '_desktop_sizes', [(0, 0)]))
        if num_screens > 1:
            idx_screen = params['video'].get('display_index', 0)
            if idx_screen < 0 or idx_screen >= num_screens:
                idx_screen = 0
            w_e, h_e = self._desktop_sizes[idx_screen]
            lbl_screen = render_text(self.font_text,
                i18n.get_text("param_screen"), COLOR_TEXT)
            self.screen.blit(lbl_screen, (col_left + 20, y + 6))
            self.btn_change_screen.rect.y = y
            self.btn_change_screen.text = f"{idx_screen + 1}/{num_screens}  ({w_e}x{h_e})"
            self.btn_change_screen.style = "normal"
            self.btn_change_screen._define_style("normal")
            self.btn_change_screen.draw(self.screen)
            y += esp_line

            # Warning if the chosen screen is not the one currently active
            # (the change is only applied at the next launch)
            idx_active = getattr(self, '_display_index_active', idx_screen)
            if idx_screen != idx_active:
                txt_warn = i18n.get_text("param_screen_redemarrage")
                lbl_warn = render_text(self.font_small, txt_warn, (255, 200, 80))
                self.screen.blit(lbl_warn, (col_left + 20, y))
                y += int(esp_line * 0.6)

        is_fullscreen = params['video']['fullscreen']
        style_res = "disabled" if is_fullscreen else "normal"
        if is_fullscreen:
            res_txt = f"{self.resolution_native[0]}x{self.resolution_native[1]}"
        else:
            res = params['video'].get('resolution', [SCREEN_WIDTH, SCREEN_HEIGHT])
            res_txt = f"{res[0]}x{res[1]}"
        for _btn in (self.btn_change_resolution,
                     self.btn_resolution_prev,
                     self.btn_resolution_next):
            _btn.style = style_res
            _btn._define_style(style_res)
        lbl_res_color = COLOR_TEXT_DARK if is_fullscreen else COLOR_TEXT
        lbl_res = render_text(self.font_text,
            i18n.get_text("param_resolution"), lbl_res_color)
        self.screen.blit(lbl_res, (col_left + 20, y + 6))

        # Layout: [<] [resolution] [>] aligned in the column
        gap_res = max(4, self._scale(4))
        arrow_w_res = self.btn_resolution_prev.rect.width
        self.btn_resolution_prev.rect.topleft = (col_right, y)
        self.btn_change_resolution.rect.topleft = (
            col_right + arrow_w_res + gap_res, y)
        self.btn_resolution_next.rect.topleft = (
            col_right + arrow_w_res + gap_res
            + self.btn_change_resolution.rect.width + gap_res, y)
        self.btn_change_resolution.text = res_txt
        self.btn_resolution_prev.draw(self.screen)
        self.btn_change_resolution.draw(self.screen)
        self.btn_resolution_next.draw(self.screen)
        y += esp_line

        line_toggle("Musique",
                    params['video'].get('music', True),
                    self.btn_toggle_music,
                    i18n.get_text("param_yes"),
                    i18n.get_text("param_not"))
        line_toggle("Sons (SFX)",
            params['sounds'].get('enable_sfx', True),
            self.btn_toggle_sfx,
            i18n.get_text("param_yes"),
            i18n.get_text("param_not"))

        lbl_lum = render_text(self.font_text,
            i18n.get_text("param_brightness"), COLOR_TEXT)
        self.screen.blit(lbl_lum, (col_left + 20, y + 6))
        self.btn_open_brightness.rect.y = y
        value_lum = params['video'].get('brightness', 0.3)
        self.btn_open_brightness.text = f"{int(round(value_lum * 100))} %"
        self.btn_open_brightness.draw(self.screen)
        y += esp_line

        section(i18n.get_text("param_section_controls"))
        line_control(i18n.get_text("param_left"),   'left',    self.btn_change_left)
        line_control(i18n.get_text("param_right"),   'right',    self.btn_change_right)
        line_control(i18n.get_text("param_jump"),     'jump',      self.btn_change_jump)
        line_control(i18n.get_text("param_echo"),     'echo',      self.btn_change_echo)
        line_control(i18n.get_text("param_attack"),  'attack',   self.btn_change_attack)
        line_control(i18n.get_text("param_dash"),     'dash',      self.btn_change_dash)
        line_control(i18n.get_text("param_echo_dir"), 'echo_dir',  self.btn_change_echo_dir)
        line_control(i18n.get_text("menu_ctrl_interact"),  'interact', self.btn_change_interact)
        line_control(i18n.get_text("menu_ctrl_torch"),                'torch',    self.btn_change_torch)
        line_control(i18n.get_text("menu_ctrl_journal"),    'journal',   self.btn_change_journal)

        section(i18n.get_text("param_section_net"))

        def _label_copy(key_item, val):
            suffix = i18n.get_text("menu_copied") if pygame.time.get_ticks() - self._feedback_copy.get(key_item, 0) < 1500 else i18n.get_text("menu_copy")
            return f"{val}   {suffix}"

        line_ip(i18n.get_text("menu_ip_local"),
                _label_copy('ip_local', self._ip_local_cache or '...'),
                self.btn_copy_ip_local)

        help = render_text(self.font_small,
            i18n.get_text("menu_click_copy"), COLOR_TEXT_DARK)
        self.screen.blit(help, (col_left + 20, y))

        self.btn_apply_params.draw(self.screen)
        self.btn_back_params.draw(self.screen)

    # ==================================================================
    # HANDLING + DRAWING - BRIGHTNESS MENU
    # ==================================================================

    def _load_preview_brightness(self):
        if self._preview_brightness_cache is not None:
            return self._preview_brightness_cache
        path = asset_path("preview_brightness.png")
        try:
            img = pygame.image.load(path).convert()
            img = pygame.transform.smoothscale(
                img, (self.width_screen, self.height_screen))
            self._preview_brightness_cache = img
            return img
        except Exception:
            background = pygame.Surface((self.width_screen, self.height_screen))
            self._draw_background_menu2()
            self._preview_brightness_cache = background
            return background

    def _open_menu_brightness(self):
        value = self.settings_temp['video'].get('brightness', 0.3)
        self.slider_brightness.value = value
        self._brightness_value_initial = value
        if self.game_state == "IN_GAME":
            self._background_brightness = getattr(self, '_last_frame_game', None)
            if self._background_brightness is None:
                self._background_brightness = self._load_preview_brightness()
            self.inner_game_state = "BRIGHTNESS_GAME"
        else:
            self._background_brightness = self._load_preview_brightness()
            self.game_state = "MENU_BRIGHTNESS"

    def _close_menu_brightness(self, apply):
        if apply and self.settings_temp.get('video') is not None:
            self.settings_temp['video']['brightness'] = self.slider_brightness.value
        if self.game_state == "IN_GAME":
            self.inner_game_state = "SETTINGS_GAME"
        else:
            self.game_state = "MENU_SETTINGS"

    def handle_menu_brightness(self, pos_mouse):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.game_state = "QUIT"
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._close_menu_brightness(apply=False)
                return
            self.slider_brightness.handle_event(event)
            if self.btn_apply_brightness.verify_click(event):
                self._close_menu_brightness(apply=True)
                return
            if self.btn_back_brightness.verify_click(event):
                self._close_menu_brightness(apply=False)
                return
        self.slider_brightness.verify_hover(pos_mouse)
        self.btn_apply_brightness.verify_hover(pos_mouse)
        self.btn_back_brightness.verify_hover(pos_mouse)

    def draw_menu_brightness(self):
        self._draw_background_menu2()

        overlay = pygame.Surface(
            (self.width_screen, self.height_screen), pygame.SRCALPHA)
        alpha = int(220 * (1.0 - self.slider_brightness.value * 0.8))
        overlay.fill((0, 0, 10, alpha))
        self.screen.blit(overlay, (0, 0))

        h_banner = int(self.height_screen * 0.30)
        banner = pygame.Surface(
            (self.width_screen, h_banner), pygame.SRCALPHA)
        banner.fill((4, 4, 15, 200))
        self.screen.blit(banner, (0, self.height_screen - h_banner))

        draw_title_neon(self.screen, self.font_button,
                            i18n.get_text("param_brightness_title"),
                            self.cx,
                            self.height_screen - h_banner + 30)

        help = self.font_small.render(
            i18n.get_text("param_brightness_help"),
            True, COLOR_TEXT_DARK)
        rect_help = help.get_rect(
            midtop=(self.cx, self.slider_brightness.rect.y - 44))
        self.screen.blit(help, rect_help)

        self.slider_brightness.draw(self.screen)
        self.btn_apply_brightness.draw(self.screen)
        self.btn_back_brightness.draw(self.screen)

    # ==================================================================
    # HANDLING + DRAWING - PAUSE MENU
    # ==================================================================

    def draw_menu_pause(self):
        self.screen.blit(self.surface_background_pause, (0, 0))
        draw_title_neon(self.screen, self.font_title,
                            i18n.get_text("pause_title"),
                            self.cx,
                            self.cy - int(self.height_screen * 0.22))
        for btn in self.buttons_menu_pause:
            btn.draw(self.screen)
        self._draw_host_info()

    def _draw_host_info(self):
        """Show the addresses (and relay room code) friends can join when we host."""
        if getattr(self, '_server_instance', None) is None:
            return
        if getattr(self, '_host_ips_cache', None) is None:
            self._host_ips_cache = ", ".join(list_local_ips()) or "127.0.0.1"
        lines = [i18n.get_text("pause_host_ip").format(ip=self._host_ips_cache)]
        if self.room_code:
            lines.append(f"{i18n.get_text('param_code_room_label')} {self.room_code}")
        y = self.height_screen - self._scale(40) * (len(lines) + 1)
        for line in lines:
            surf = self.font_text.render(line, True, COLOR_TEXT)
            self.screen.blit(surf, surf.get_rect(midtop=(self.cx, y)))
            y += surf.get_height() + 4

    def handle_pause_events(self, pos_mouse):
        for btn in self.buttons_menu_pause:
            btn.verify_hover(pos_mouse)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.inner_game_state = "GAME"
                music.resume()
            if self.btn_pause_resume.verify_click(event):
                self.inner_game_state = "GAME"
                music.resume()
            if self.btn_pause_settings.verify_click(event):
                self.previous_game_state = "IN_GAME"
                self.settings_temp = copy.deepcopy(self.settings)
                self._ip_local_cache = local_ip()
                self.inner_game_state = "SETTINGS_GAME"
            if self.btn_pause_quit.verify_click(event):
                self.game_state = "MENU_MAIN"

    def _launch_tutorial(self):
        from ui.tutorial import Tutorial
        controls = self.settings.get('controls', {})
        tutorial = Tutorial(
            self.screen,
            self.width_screen,
            self.height_screen,
            controls,
            self.font_title,
            self.font_text,
            self.font_button,
            self.font_small,
        )
        tutorial.launch()
        # Transparent return: the main menu is simply shown again
        # (the main loop resumes without any state change)