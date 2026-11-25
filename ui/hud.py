# ui/hud.py
# Mixin for the in-game HUD.
# Redesigned Echo indicator: large, readable, with an explicit label and an activation animation.

import pygame
from utils.paths import asset_path
import math

from settings import *
from utils.cache import render_text, create_texts_echo_hud
from utils.i18n import get_text


class HudMixin:
    """In-game HUD drawing methods."""

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _format_key_hud(key: str) -> str:
        """Convert a key name into a short label for the HUD circles."""
        _MAP = {
            'space': 'SP', 'mouse_1': 'M1', 'mouse_2': 'M2', 'mouse_3': 'M3',
            'left': '←', 'right': '→', 'up': '↑', 'down': '↓',
            'return': 'RT', 'backspace': 'BS', 'tab': 'TB',
            'escape': 'EC', 'lshift': 'SH', 'rshift': 'SH',
            'lctrl': 'CT', 'rctrl': 'CT', 'lalt': 'AL', 'ralt': 'AL',
        }
        k = key.lower()
        if k in _MAP:
            return _MAP[k]
        return key[0].upper() if key else '?'

    # ------------------------------------------------------------------
    # HUD CACHE (fonts + reusable surfaces)
    # ------------------------------------------------------------------

    def _init_hud_cache(self):
        """Initialise the cached fonts and surfaces of the HUD. Rebuild the caches
        if the screen resolution changed since the last call.
        """
        h = self.height_screen
        w = self.width_screen
        if getattr(self, '_hud_cache_res', None) == (w, h):
            return
        self._font_echo_icon    = pygame.font.Font(None, max(32, h // 28))
        self._font_label_small  = pygame.font.Font(None, max(22, h // 45))
        self._font_label_medium = pygame.font.Font(None, max(32, h // 32))
        self._font_ability     = pygame.font.Font(None, max(20, h // 50))
        # Adaptive dimensions of the Echo widget
        self._echo_radius   = max(18, h // 36)
        self._echo_bar_w   = max(50, h // 12)
        widget_w = self._echo_radius * 2 + 12 + self._echo_bar_w + 8
        widget_h = self._echo_radius * 2 + 4
        self._widget_surf_cache = pygame.Surface((widget_w, widget_h), pygame.SRCALPHA)
        self._surf_c_cache      = pygame.Surface((self._echo_radius * 2 + 2,
                                                  self._echo_radius * 2 + 2),
                                                 pygame.SRCALPHA)
        # Mini cooldown (dash / echo_dir) - same size as the echo
        self._mini_radius = self._echo_radius
        mini_r = self._mini_radius
        mini_w = mini_r * 2 + 12 + self._echo_bar_w + 8
        mini_h = mini_r * 2 + 4
        self._mini_widget_cache  = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
        self._mini_circle_cache  = pygame.Surface((mini_r * 2 + 2, mini_r * 2 + 2), pygame.SRCALPHA)
        # Enemy flash halo surface (60x60)
        self._flash_halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        # Cache of the flash tmp surfaces per enemy size
        self._flash_tmp_cache = {}
        # Debug overlay surface
        self._debug_panel_cache = None
        # Death overlay surface
        self._dead_overlay_cache = None
        self._dead_overlay_size  = None
        # Pre-rendered static texts of the Echo widget (centralised)
        self._txt_echo = create_texts_echo_hud(
            self._font_label_small,
            self._font_label_medium,
            self._font_echo_icon,
        )
        self._hud_cache_res = (w, h)

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------

    def draw_hud(self):
        """Draw the whole HUD."""
        self._init_hud_cache()
        my_player = self.local_players.get(self.my_id)
        if not my_player:
            return

        x0 = 24
        y0 = 24

        # HP
        lc  = max(24, self.width_screen // 60)   # heart width
        hc  = max(20, self.height_screen // 45)   # heart height
        pad = 6
        for i in range(my_player.max_hp):
            rx = x0 + i * (lc + pad)
            pygame.draw.rect(self.screen, COLOR_HP_LOST,
                             pygame.Rect(rx, y0, lc, hc), border_radius=4)
            pygame.draw.rect(self.screen, COLOR_CYAN_DARK,
                             pygame.Rect(rx, y0, lc, hc), width=1, border_radius=4)
        for i in range(my_player.hp):
            rx = x0 + i * (lc + pad)
            pygame.draw.rect(self.screen, COLOR_HP,
                             pygame.Rect(rx, y0, lc, hc), border_radius=4)

        # Boss bar
        if hasattr(self, '_last_data_boss') and self._last_data_boss:
            d = self._last_data_boss
            if d.get('fight_started') and not d.get('boss_defeated'):
                bd = d['boss']
                self._draw_bar_boss(bd['hp'], bd['hp_max'])

        # Money - counter animated one by one
        target = my_player.money
        if not hasattr(self, '_money_displayed'):
            self._money_displayed = target
            self._t_money_ms = 0
        now_hud = pygame.time.get_ticks()
        if self._money_displayed < target:
            if now_hud - self._t_money_ms >= 50:
                self._money_displayed += 1
                self._t_money_ms = now_hud
        else:
            self._money_displayed = target  # sync when money was spent
        money_surf = self.font_text.render(
            get_text("hud_souls").format(n=self._money_displayed), True, COLOR_VIOLET_LIGHT)
        self.screen.blit(money_surf, (x0, y0 + hc + 10))

        # Key
        y_cur = y0 + hc + 10 + money_surf.get_height() + 6
        if getattr(my_player, 'have_key', False):
            self._draw_icon_key_item(x0, y_cur)
            y_cur += 24

        # Echo indicator (the most important after HP)
        y_cur += 4
        self._draw_indicator_echo(x0, y_cur, my_player)
        y_cur += self._echo_radius * 2 + 10

        # Ability mini-cooldowns (dash + directional echo) + double jump dot
        y_cur = self._draw_indicators_abilities(x0, y_cur, my_player)

        # Journal icon - top right
        if hasattr(self, 'widget_quest') and self.widget_quest:
            self.widget_quest.update(
                self.local_key_item,
                next(iter(self.local_doors.values()), None),
                self.boss_local,
                enemies_killed=getattr(self, '_enemies_killed_total', 0),
                souls=getattr(self, '_souls_harvested_total', 0))
            key_journal = self.settings.get('controls', {}).get('journal', 'i')
            x_journal = self.width_screen - 100
            self.widget_quest.draw(self.screen, y_offset=24, key_journal=key_journal,
                                       x_offset=x_journal)

        self._draw_notification_ability()

        if DEV_MODE:
            self._draw_debug_hud()


    # ------------------------------------------------------------------
    # ECHO COOLDOWN INDICATOR - FULL WIDGET
    # ------------------------------------------------------------------

    def _draw_indicator_echo(self, x, y, player):
        """
        Echo cooldown indicator widget.

        Layout:
            [ 28px circle ]  [ label ]
                             ECHO
                             READY  <- green when available
                             or
                             1.8s   <- countdown red -> yellow -> green

        The circle is an arc that fills clockwise from the top (12 o'clock).
        Empty = just used, full = ready. A flash animation pulses briefly on
        activation.
        """
        now = pygame.time.get_ticks()
        radius        = self._echo_radius
        cx_circle    = x + radius
        cy_circle    = y + radius

        last_echo = getattr(player, 'last_echo_time', 0)
        elapsed      = now - last_echo
        ratio        = max(0.0, min(1.0, elapsed / COOLDOWN_ECHO))  # 0 = just used, 1 = ready
        ready         = ratio >= 1.0

        # ---- Widget background (semi-transparent panel) ----
        widget_surf = self._widget_surf_cache
        widget_surf.fill((0, 0, 0, 0))
        widget_surf.fill((8, 6, 20, 160))
        pygame.draw.rect(widget_surf, (30, 20, 60, 180),
                         widget_surf.get_rect(), width=1, border_radius=6)
        self.screen.blit(widget_surf, (x - 2, y - 2))

        # ---- Cooldown circle ----
        surf_c = self._surf_c_cache
        surf_c.fill((0, 0, 0, 0))
        scx    = radius + 1
        scy    = radius + 1

        # Background track (gray ring)
        pygame.draw.circle(surf_c, (25, 18, 45, 220), (scx, scy), radius)
        pygame.draw.circle(surf_c, (50, 35, 80, 255), (scx, scy), radius, width=2)

        if ready:
            # Pulsing filled cyan circle
            pulse = 0.82 + 0.18 * math.sin(now / 450)
            r, g, b = COLOR_CYAN
            # Semi-transparent inner fill
            pygame.draw.circle(surf_c, (r, g, b, int(60 * pulse)), (scx, scy), radius - 3)
            # Glowing ring
            pygame.draw.circle(surf_c, (r, g, b, 255), (scx, scy), radius, width=3)
            # Pulsing outer halo
            halo_r = int((radius + 5) * pulse)
            pygame.draw.circle(surf_c, (r, g, b, int(40 * pulse)), (scx, scy), halo_r, width=2)
        else:
            # Progress arc - draws N small sectors to simulate the arc
            self._draw_arc_cooldown(surf_c, scx, scy, radius - 2, ratio)
            # Fixed edge of the track
            pygame.draw.circle(surf_c, (55, 38, 85, 200), (scx, scy), radius, width=1)

        # Activation flash (within 200 ms after use)
        if 0 <= elapsed < 200:
            flash_alpha = min(255, int(180 * (1.0 - elapsed / 200)))
            pygame.draw.circle(surf_c, (255, 255, 255, flash_alpha), (scx, scy), radius - 4)

        # Central icon: activation key read from the settings
        _key_echo = self.settings.get('controls', {}).get('echo', 'e')
        _label_echo = self._format_key_hud(_key_echo)
        color_icon = COLOR_CYAN if ready else (100, 80, 140)
        icon_e = render_text(self._font_echo_icon, _label_echo, color_icon)
        surf_c.blit(icon_e, icon_e.get_rect(center=(scx, scy)))

        self.screen.blit(surf_c, (cx_circle - radius - 1, cy_circle - radius - 1))

        # ---- Labels on the right of the circle ----
        lx = cx_circle + radius + 10
        ly = cy_circle - 18

        # Line 1: the word "ECHO" in small gray - pre-rendered
        label_title = self._txt_echo['echo_label']
        self.screen.blit(label_title, (lx, ly))
        ly += label_title.get_height() + 2

        # Line 2: main status - large, readable
        if ready:
            # "READY" in bright green/cyan - pre-rendered
            state_surf = self._txt_echo['echo_ready']
        else:
            # Countdown in seconds with progressive color
            remaining   = max(0.0, (COOLDOWN_ECHO - elapsed) / 1000)
            t_ratio   = 1.0 - ratio           # 1 = just used, 0 = almost ready
            r_c = int(220 * t_ratio + 0   * (1 - t_ratio))
            g_c = int(60  * t_ratio + 200 * (1 - t_ratio))
            b_c = int(60  * t_ratio + 80  * (1 - t_ratio))
            # render_text memoises by (font, text, color) - ~25 distinct values
            # for a 2.5 s cooldown shown to the tenth.
            state_surf = render_text(self._font_label_medium, f"{remaining:.1f}s", (r_c, g_c, b_c))

        self.screen.blit(state_surf, (lx, ly))
        ly += state_surf.get_height() + 2

        # Line 3: thin linear progress bar under the text
        bar_w   = self._echo_bar_w
        bar_h   = max(3, self.height_screen // 360)
        bar_rect = pygame.Rect(lx, ly, bar_w, bar_h)
        pygame.draw.rect(self.screen, (40, 28, 60), bar_rect, border_radius=2)
        if ratio > 0:
            fill_w = int(bar_w * ratio)
            r_b = int(180 * (1 - ratio) + 0   * ratio)
            g_b = int(60  * (1 - ratio) + 210 * ratio)
            b_b = int(60  * (1 - ratio) + 190 * ratio)
            pygame.draw.rect(self.screen, (r_b, g_b, b_b),
                             pygame.Rect(lx, ly, fill_w, bar_h), border_radius=2)

    def _draw_arc_cooldown(self, surf, cx, cy, radius, ratio):
        """
        Draw a progress arc from 0 degrees to ratio*360 degrees, clockwise from 12 o'clock.
        Used during the cooldown. Color: bright red -> yellow -> cyan.
        """
        if ratio <= 0:
            return

        num_points = max(4, int(ratio * 16))  # arc resolution
        thickness  = 4                         # thickness of the colored track
        angle_start = -math.pi / 2             # 12 o'clock = -90 degrees

        for i in range(num_points):
            t_local = i / num_points             # 0 to 1 over the arc portion
            angle   = angle_start + t_local * ratio * 2 * math.pi

            # Color: bright red (start) -> orange -> yellow -> cyan (end)
            # interpolated over the arc progress
            r_c = int(220 * (1 - t_local * ratio) + 0   * (t_local * ratio))
            g_c = int(50  * (1 - t_local * ratio) + 200 * (t_local * ratio))
            b_c = int(50  * (1 - t_local * ratio) + 195 * (t_local * ratio))

            # Small circles are drawn along the arc to avoid gaps
            px = int(cx + math.cos(angle) * radius)
            py = int(cy + math.sin(angle) * radius)
            pygame.draw.circle(surf, (r_c, g_c, b_c, 240), (px, py), thickness // 2 + 1)

        # Head point (end of the arc) - brighter
        angle_end = angle_start + ratio * 2 * math.pi
        px_end    = int(cx + math.cos(angle_end) * radius)
        py_end    = int(cy + math.sin(angle_end) * radius)
        pygame.draw.circle(surf, (255, 255, 255, 200), (px_end, py_end), thickness // 2)

    # ------------------------------------------------------------------
    # UNLOCKED ABILITIES
    # ------------------------------------------------------------------

    def _draw_indicators_abilities(self, x, y, player):
        """Double jump dot + dash and directional echo mini-cooldowns."""
        radius  = max(10, self.height_screen // 60)
        space = max(6, radius // 2)
        cx     = x + radius
        cy     = y + radius

        def _dot(surface, cx, cy, r, color):
            pygame.draw.circle(surface, color, (cx, cy), r)
            r2, g2, b2 = min(color[0]+60, 255), min(color[1]+60, 255), min(color[2]+60, 255)
            pygame.draw.circle(surface, (r2, g2, b2), (cx, cy), r, 2)

        def _icon_double_jump(surface, cx, cy, r):
            ep = max(1, r // 5)
            w  = max(4, r // 2)
            for dy_off in (-r // 4, r // 3):
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off + w//2), (cx, cy + dy_off - w//2), ep)
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off - w//2), (cx - w//2, cy + dy_off), ep)
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off - w//2), (cx + w//2, cy + dy_off), ep)

        y_cur = y

        # Double jump dot (no cooldown to show)
        if getattr(player, 'can_double_jump', False):
            _dot(self.screen, cx, cy, radius, (80, 160, 255))
            _icon_double_jump(self.screen, cx, cy, radius)
            y_cur = cy + radius + space

        # Dash mini cooldown
        if getattr(player, 'can_dash', False):
            _dash_key = self.settings.get('controls', {}).get('dash', 'c')
            y_cur = self._draw_mini_cooldown(
                x, y_cur,
                key_label=self._format_key_hud(_dash_key),
                title='DASH',
                color_dot=(180, 80, 255),
                last_time=getattr(player, 'last_dash_time', 0),
                cooldown_ms=COOLDOWN_DASH,
                icon_fn=self._draw_icon_mini_dash,
            )
            y_cur += space

        # Directional echo mini cooldown
        if getattr(player, 'can_echo_dir', False):
            _echo_dir_key = self.settings.get('controls', {}).get('echo_dir', 'y')
            y_cur = self._draw_mini_cooldown(
                x, y_cur,
                key_label=self._format_key_hud(_echo_dir_key),
                title=get_text("hud_echo_dir_title"),
                color_dot=(0, 200, 180),
                last_time=getattr(player, 'last_echo_dir_time', 0),
                cooldown_ms=COOLDOWN_ECHO_DIR,
                icon_fn=self._draw_icon_mini_echo_dir,
            )
            y_cur += space

        return y_cur

    # ------------------------------------------------------------------
    # MINI COOLDOWN WIDGET (dash / echo dir)
    # ------------------------------------------------------------------

    def _draw_mini_cooldown(self, x, y, key_label, title,
                                color_dot, last_time, cooldown_ms, icon_fn):
        """
        Compact cooldown widget for dash / directional echo.
        Returns y + the widget height.
        """
        now = pygame.time.get_ticks()
        r   = self._mini_radius
        cx  = x + r
        cy  = y + r
        elapsed = now - last_time
        ratio   = max(0.0, min(1.0, elapsed / cooldown_ms))
        ready    = ratio >= 1.0

        # Background
        surf = self._mini_widget_cache
        surf.fill((0, 0, 0, 0))
        surf.fill((8, 6, 20, 140))
        pygame.draw.rect(surf, (30, 20, 60, 160),
                         surf.get_rect(), width=1, border_radius=5)
        self.screen.blit(surf, (x - 2, y - 2))

        # Circle
        sc = self._mini_circle_cache
        sc.fill((0, 0, 0, 0))
        scx = r + 1
        scy = r + 1
        pygame.draw.circle(sc, (25, 18, 45, 200), (scx, scy), r)
        pygame.draw.circle(sc, (50, 35, 80, 220), (scx, scy), r, width=2)

        if ready:
            pulse = 0.82 + 0.18 * math.sin(now / 450)
            rc, gc, bc = color_dot
            pygame.draw.circle(sc, (rc, gc, bc, int(55 * pulse)), (scx, scy), r - 2)
            pygame.draw.circle(sc, (rc, gc, bc, 255), (scx, scy), r, width=2)
        else:
            self._draw_arc_cooldown(sc, scx, scy, r - 2, ratio)
            pygame.draw.circle(sc, (55, 38, 85, 180), (scx, scy), r, width=1)

        if 0 <= elapsed < 200:
            flash_a = min(255, int(160 * (1.0 - elapsed / 200)))
            pygame.draw.circle(sc, (255, 255, 255, flash_a), (scx, scy), r - 3)

        # Key letter at the center of the circle (same style as the "E" of the echo)
        color_letter = COLOR_CYAN if ready else (100, 80, 140)
        letter_surf = render_text(self._font_echo_icon, key_label, color_letter)
        sc.blit(letter_surf, letter_surf.get_rect(center=(scx, scy)))
        self.screen.blit(sc, (cx - r - 1, cy - r - 1))

        # Labels on the right - same layout as the echo
        lx = cx + r + 10
        ly = cy - 18

        title_surf = render_text(self._font_label_small, title, (100, 85, 130))
        self.screen.blit(title_surf, (lx, ly))
        ly += title_surf.get_height() + 2

        if ready:
            state_surf = render_text(self._font_label_medium, get_text("hud_ready"), COLOR_CYAN)
        else:
            remaining  = max(0.0, (cooldown_ms - elapsed) / 1000)
            t_ratio  = 1.0 - ratio
            r_c = int(220 * t_ratio + 0   * (1 - t_ratio))
            g_c = int(60  * t_ratio + 200 * (1 - t_ratio))
            b_c = int(60  * t_ratio + 80  * (1 - t_ratio))
            state_surf = render_text(self._font_label_medium, f"{remaining:.1f}s", (r_c, g_c, b_c))
        self.screen.blit(state_surf, (lx, ly))
        ly += state_surf.get_height() + 2

        # Progress bar
        bar_w  = self._echo_bar_w
        bar_h  = max(3, self.height_screen // 360)
        pygame.draw.rect(self.screen, (40, 28, 60), pygame.Rect(lx, ly, bar_w, bar_h), border_radius=2)
        if ratio > 0:
            fill_w = int(bar_w * ratio)
            r_b = int(180 * (1 - ratio))
            g_b = int(60  * (1 - ratio) + 210 * ratio)
            b_b = int(60  * (1 - ratio) + 190 * ratio)
            pygame.draw.rect(self.screen, (r_b, g_b, b_b),
                             pygame.Rect(lx, ly, fill_w, bar_h), border_radius=2)

        return y + r * 2 + 4

    @staticmethod
    def _draw_icon_mini_dash(surf, cx, cy, r, ready):
        """Horizontal arrow (dash)."""
        color = COLOR_CYAN if ready else (100, 80, 140)
        ep = max(1, r // 4)
        w  = max(4, r * 2 // 3)
        pygame.draw.line(surf, color, (cx - w//2, cy), (cx + w//2, cy), ep)
        pygame.draw.line(surf, color,
                         (cx + w//2, cy), (cx + w//2 - w//3, cy - w//3), ep)
        pygame.draw.line(surf, color,
                         (cx + w//2, cy), (cx + w//2 - w//3, cy + w//3), ep)

    @staticmethod
    def _draw_icon_mini_echo_dir(surf, cx, cy, r, ready):
        """Small ring + side strokes (directional echo)."""
        color = COLOR_CYAN if ready else (100, 80, 140)
        ep = max(1, r // 5)
        ri = max(3, r // 2)
        pygame.draw.circle(surf, color, (cx, cy), ri, ep)
        pygame.draw.line(surf, color, (cx - r + 1, cy), (cx - ri - 1, cy), ep)
        pygame.draw.line(surf, color, (cx + ri + 1, cy), (cx + r - 1, cy), ep)

    def _draw_notification_ability(self):
        if not hasattr(self, 'notif_ability') or not self.notif_ability:
            return
        time_ms = pygame.time.get_ticks()
        self.notif_ability.update(time_ms)
        self.notif_ability.draw(self.screen, time_ms)

    # ------------------------------------------------------------------
    # KEY
    # ------------------------------------------------------------------

    def _draw_icon_key_item(self, x, y):
        if not hasattr(self, '_sprite_key_item_hud'):
            try:
                img  = pygame.image.load(asset_path('key_item.png')).convert_alpha()
                self._sprite_key_item_hud = pygame.transform.scale(img, (18, 18))
            except Exception:
                self._sprite_key_item_hud = None

        if self._sprite_key_item_hud:
            self.screen.blit(self._sprite_key_item_hud, (x, y))
        else:
            pygame.draw.rect(self.screen, (255, 215, 0),
                             pygame.Rect(x, y, 14, 14), border_radius=3)
        lbl = self.font_text.render(get_text("hud_key"), True, (255, 215, 0))
        self.screen.blit(lbl, (x + 20, y + 1))


    def _draw_message_end(self, surface):
        """Show the end message with a progressive fade."""
        if self._end_message_since is None:
            return
        elapsed = pygame.time.get_ticks() - self._end_message_since
        # Fade-in over 1500 ms
        alpha = min(255, int(255 * min(elapsed, 1500) / 1500))
        sw, sh = surface.get_size()

        size_title = max(48, sh // 14)
        if (not hasattr(self, '_font_end')
                or getattr(self, '_font_end_size', None) != size_title):
            self._font_end = pygame.font.Font(None, size_title)
            self._font_end_size = size_title

        # Dark veil to make the text stand out
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(alpha * 0.5)))
        surface.blit(overlay, (0, 0))

        txt = self._font_end.render(get_text("hud_end"), True, (0, 212, 255))
        txt.set_alpha(alpha)
        rect = txt.get_rect(center=(sw // 2, sh // 2))
        surface.blit(txt, rect)

    # ------------------------------------------------------------------
    # DEBUG
    # ------------------------------------------------------------------

    def _draw_debug_hud(self):
        fps = self.clock.get_fps()
        color_fps = ((0, 220, 120) if fps >= FPS * 0.85
                       else (255, 180, 0) if fps >= FPS * 0.5
                       else (255, 60, 60))
        my_player = self.local_players.get(self.my_id)
        lines = [
            (f"FPS : {fps:.0f} / {FPS}", color_fps),
            (f"Pos: {my_player.rect.x}, {my_player.rect.y}" if my_player else "Pos: -",
             COLOR_TEXT_DARK),
            (f"Players: {len(self.local_players)}",  COLOR_TEXT_DARK),
            (f"Ennemis : {len(self.local_enemies)}",  COLOR_TEXT_DARK),
            (f"Entities: {len(self.local_players)+len(self.local_enemies)+len(self.local_lost_souls)+len(self.local_free_souls)}",
             COLOR_TEXT_DARK),
            (f"Torche : {'ON' if self.torch.lit else 'OFF'}",
             (255, 160, 30) if self.torch.lit else COLOR_TEXT_DARK),
        ]
        p      = self.font_small
        lh     = p.get_height() + 4
        pad    = 8
        lw_pan = 160
        ht_pan = len(lines) * lh + pad * 2
        x0     = self.width_screen - lw_pan - 12
        y0     = 12
        if self._debug_panel_cache is None or self._debug_panel_cache.get_size() != (lw_pan, ht_pan):
            self._debug_panel_cache = pygame.Surface((lw_pan, ht_pan), pygame.SRCALPHA)
        panel = self._debug_panel_cache
        panel.fill((8, 8, 20, 180))
        pygame.draw.rect(panel, COLOR_CYAN_DARK,
                         panel.get_rect(), width=1, border_radius=6)
        self.screen.blit(panel, (x0, y0))
        for i, (text, color) in enumerate(lines):
            self.screen.blit(p.render(text, True, color),
                            (x0 + pad, y0 + pad + i * lh))

    # ------------------------------------------------------------------
    # DEATH
    # ------------------------------------------------------------------

    def _draw_death_screen(self, surface):
        if self._dead_since is None:
            self._dead_since = pygame.time.get_ticks()
        elapsed = pygame.time.get_ticks() - self._dead_since
        alpha   = min(200, int(200 * min(elapsed, 800) / 800))
        sz = surface.get_size()
        if self._dead_overlay_cache is None or self._dead_overlay_size != sz:
            self._dead_overlay_cache = pygame.Surface(sz, pygame.SRCALPHA)
            self._dead_overlay_size = sz
        self._dead_overlay_cache.fill((80, 0, 0, alpha))
        surface.blit(self._dead_overlay_cache, (0, 0))
        if elapsed > 600:
            lw, lh = sz
            # Sizes proportional to the height of the surface (the virtual
            # surface = screen_height / zoom). Lets the death screen
            # adapt to every resolution.
            size_title = max(32, lh // 8)
            size_sub   = max(20, lh // 14)
            if (not hasattr(self, '_font_dead')
                    or getattr(self, '_font_dead_size', None) != size_title):
                self._font_dead = pygame.font.Font(None, size_title)
                self._font_sub  = pygame.font.Font(None, size_sub)
                self._font_dead_size = size_title
            t1 = self._font_dead.render("VOUS ETES MORT", True, (220, 50, 50))
            t2 = self._font_sub.render("Respawn en cours...", True, (160, 100, 100))
            offset = max(10, lh // 40)
            surface.blit(t1, t1.get_rect(center=(lw // 2, lh // 2 - offset)))
            surface.blit(t2, t2.get_rect(center=(lw // 2, lh // 2 + offset)))

    # ------------------------------------------------------------------
    # BOSS
    # ------------------------------------------------------------------

    def _draw_bar_boss(self, hp, hp_max):
        bar_w = 400
        bar_h = 16
        bar_x = self.width_screen // 2 - bar_w // 2
        bar_y = 20
        ratio = max(0.0, hp / hp_max)
        pygame.draw.rect(self.screen, (40, 10, 10),  (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4))
        pygame.draw.rect(self.screen, (90, 20, 20),  (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.screen, (200, 50, 50), (bar_x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(self.screen, (220, 180, 180), (bar_x, bar_y, bar_w, bar_h), 1)
        name = self.font_small.render("Demon Slime", True, (220, 180, 180))
        self.screen.blit(name, (bar_x, bar_y - 18))

    def _draw_badge_torch(self, surface, camera_offset):
        """
        Draw a small [L] badge above the torch to show the interaction key,
        before its first use.
        """
        if not hasattr(self, '_font_badge_torch'):
            self._font_badge_torch = pygame.font.Font(None, 32)

        off_x, off_y = camera_offset
        time_ms = pygame.time.get_ticks()

        # Position: centered above the torch sprite, with a floating motion
        floating = math.sin(time_ms / 400) * 3
        bx = self.torch.x + TILE_SIZE // 2 - off_x
        by = self.torch.y - 18 + int(floating) - off_y

        # Key name (from the settings, fallback "L")
        name_key = self.settings.get('controls', {}).get('torch', 'l').upper()

        # Rounded background
        label = self._font_badge_torch.render(name_key, True, (255, 255, 255))
        pad_x, pad_y = 6, 3
        w = label.get_width() + pad_x * 2
        h = label.get_height() + pad_y * 2
        badge = pygame.Surface((w, h), pygame.SRCALPHA)
        badge.fill((0, 0, 0, 0))
        pygame.draw.rect(badge, (30, 20, 60, 210),
                        badge.get_rect(), border_radius=4)
        pygame.draw.rect(badge, COLOR_CYAN_DARK,
                        badge.get_rect(), width=1, border_radius=4)
        badge.blit(label, (pad_x, pad_y))

        surface.blit(badge, (bx - w // 2, by - h))

        # Small arrow pointing at the torch
        arrow_x = bx
        arrow_y = by + 2
        pygame.draw.polygon(surface, COLOR_CYAN_DARK, [
            (arrow_x - 4, arrow_y),
            (arrow_x + 4, arrow_y),
            (arrow_x,     arrow_y + 5),
        ])
