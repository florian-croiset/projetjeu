# ui/tutorial.py
# Refactored tutorial - visually improved version.
# Slide 0 - Gameplay mechanics
# Slide 1 - Lore and narrative context

import pygame
import math
import random
from settings import *
from ui.visual_effects import draw_background_echo
from ui.button import Button
from utils.i18n import get_text


# ---------------------------------------------------------------------------
# Rendering utilities
# ---------------------------------------------------------------------------

def _surface_rounded(w, h, radius, color, alpha):
    """Return a SRCALPHA Surface with a rounded rect."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (*color, alpha), surf.get_rect(), border_radius=radius)
    return surf

def _badge(screen, font, text, x, y, bg_color, text_color, alpha_bg=35, alpha_edge=90):
    """Draw a small colored badge and return the height it takes."""
    s  = font.render(text, True, text_color)
    pw = s.get_width() + 20
    ph = s.get_height() + 8

    background = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(background, (*bg_color, alpha_bg), background.get_rect(), border_radius=4)
    pygame.draw.rect(background, (*bg_color, alpha_edge), background.get_rect(), 1, border_radius=4)
    screen.blit(background, (x, y))
    screen.blit(s, (x + 10, y + 4))
    return ph + 10


def _line_kv(screen, font_key_item, font_val, x, y, key_item, val,
              color_key_item=(180, 150, 255), color_val=(180, 170, 220)):
    """Draw a [KEY] description pair on one line."""
    # Key background
    ks = font_key_item.render(key_item, True, color_key_item)
    kw = ks.get_width() + 14
    kh = ks.get_height() + 6
    kfond = pygame.Surface((kw, kh), pygame.SRCALPHA)
    pygame.draw.rect(kfond, (255, 255, 255, 18), kfond.get_rect(), border_radius=3)
    pygame.draw.rect(kfond, (255, 255, 255, 35), kfond.get_rect(), 1, border_radius=3)
    # Low shadow
    pygame.draw.line(kfond, (255, 255, 255, 50), (1, kh - 1), (kw - 2, kh - 1))
    screen.blit(kfond, (x, y))
    screen.blit(ks, (x + 7, y + 3))

    vs = font_val.render(val, True, color_val)
    screen.blit(vs, (x + kw + 10, y + (kh - vs.get_height()) // 2))
    return y + kh + 6


def _text_wrap(screen, font, text, x, y, max_w, color, line_spacing=5):
    """Draw multi-line text (split on \\n)."""
    for line in text.split('\n'):
        if line.strip() == '':
            y += font.get_height() // 2
            continue
        s = font.render(line, True, color)
        screen.blit(s, (x, y))
        y += s.get_height() + line_spacing
    return y + 4


def _block_highlight(screen, x, y, w, h,
                    edge_color=(120, 60, 255), bg_alpha=20, edge_alpha=180):
    """Block with a colored left border."""
    background = pygame.Surface((w, h), pygame.SRCALPHA)
    background.fill((*edge_color, bg_alpha))
    pygame.draw.rect(background, (*edge_color, 0),   background.get_rect(), border_radius=4)
    pygame.draw.rect(background, (*edge_color, bg_alpha), background.get_rect(), border_radius=4)
    pygame.draw.rect(background, (*edge_color, edge_alpha), (0, 0, 2, h))
    screen.blit(background, (x, y))


def _separator_gradient(screen, x, y, w,
                          c1=(120, 60, 255), c2=(0, 220, 255)):
    """Horizontal separator with a gradient made of points."""
    for i in range(w):
        t = i / max(w - 1, 1)
        # Fade-in then fade-out
        fade = math.sin(t * math.pi)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        a = int(fade * 100)
        screen.set_at((x + i, y), (r, g, b, a))   # needs a SRCALPHA surface or direct drawing
    # An intermediate surface is used for blending
    surf = pygame.Surface((w, 2), pygame.SRCALPHA)
    for i in range(w):
        t = i / max(w - 1, 1)
        fade = math.sin(t * math.pi)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        a = int(fade * 90)
        surf.set_at((i, 0), (r, g, b, a))
        surf.set_at((i, 1), (r, g, b, a // 3))
    screen.blit(surf, (x, y))


# ---------------------------------------------------------------------------
# Particles / background echo rings
# ---------------------------------------------------------------------------

class _Ring:
    def __init__(self, cx, cy, radius_max, speed, color):
        self.cx = cx
        self.cy = cy
        self.r  = random.uniform(0, radius_max * 0.3)
        self.rmax = radius_max
        self.v  = speed
        self.col = color

    def update(self, dt):
        self.r += self.v * dt
        return self.r < self.rmax

    def draw(self, screen):
        prog = self.r / self.rmax
        alpha = int((1 - prog) * 55)
        if alpha <= 0:
            return
        surf = pygame.Surface((int(self.r * 2 + 2), int(self.r * 2 + 2)), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.col, alpha),
                           (int(self.r + 1), int(self.r + 1)), int(self.r), 1)
        screen.blit(surf, (self.cx - int(self.r) - 1, self.cy - int(self.r) - 1))


class _StarAmbient:
    def __init__(self, w, h):
        self.x = random.randint(0, w)
        self.y = random.randint(0, h)
        self.r = random.uniform(0.5, 1.8)
        self.phase = random.uniform(0, math.pi * 2)
        self.speed = random.uniform(0.5, 1.5)

    def draw(self, screen, time_ms):
        flicker = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(time_ms / 700 * self.speed + self.phase))
        alpha = int(flicker * 80)
        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (160, 140, 255, alpha), (2, 2), int(self.r))
        screen.blit(surf, (self.x - 2, self.y - 2))


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Tutorial:
    """
    Tutorial made of 2 visually improved slides.

    Usage:
        tutorial = Tutorial(screen, width, height, controls_settings,
                            font_title, font_text, font_button, font_small)
        tutorial.launch()
    """

    # Color palette
    CYAN   = (0,  220, 255)
    VIOLET = (120, 60, 255)
    MAUVE  = (179, 136, 255)
    OR     = (255, 200,  70)
    PINK   = (255,  80, 140)

    def __init__(self, screen, width, height, params_controls,
                 font_title, font_text, font_button, font_small=None):
        self.screen   = screen
        self.width = width
        self.height = height
        self.cx      = width // 2
        self.cy      = height // 2

        self.font_title  = font_title
        self.font_text  = font_text
        self.font_button = font_button
        self.font_small  = font_small or font_text

        self.params_controls = params_controls

        self.index   = 0
        self.total   = 2
        self.clock = pygame.time.Clock()

        # Fade transition
        self._alpha_transition = 255   # 0 = opaque -> 255 = transparent
        self._transition_dir   = -1    # -1 = fade in, +1 = fade out
        self._next_slide  = None
        self._FADE_SPEED     = 18

        # Particles
        self._rings  = []
        self._stars  = [_StarAmbient(width, height) for _ in range(60)]
        self._timer_ring = 0

        # --- Buttons ---
        bh  = max(38, height // 22)
        bw  = max(150, width //  9)
        bot = height - bh - 28

        self.btn_next   = Button(self.cx + 15,    bot, bw, bh, get_text("tuto_btn_next"),   font_button)
        self.btn_previous = Button(self.cx - bw - 15, bot, bw, bh, get_text("tuto_btn_back"), font_button, style="ghost")
        self.btn_close    = Button(self.cx + 15,    bot, bw, bh, get_text("tuto_btn_start"),  font_button)
        self.btn_pass    = Button(width - 200,   22,  175, bh - 10, get_text("tuto_btn_skip"),
                                    font_small or font_button, style="ghost")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def launch(self):
        self._alpha_transition = 0     # starts opaque (fade in)
        self._transition_dir   = -1   # fade in

        running = True
        while running:
            dt  = self.clock.tick(FPS) / 16.67   # normalised to 60 fps
            tms = pygame.time.get_ticks()
            pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys; sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                        if self.index < self.total - 1:
                            self._launch_transition(self.index + 1)
                        else:
                            running = False
                    elif event.key == pygame.K_LEFT and self.index > 0:
                        self._launch_transition(self.index - 1)
                    elif event.key == pygame.K_ESCAPE:
                        running = False

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_pass.rect.collidepoint(event.pos):
                        running = False
                    elif self.index == self.total - 1:
                        if self.btn_close.rect.collidepoint(event.pos):
                            running = False
                    else:
                        if self.btn_next.rect.collidepoint(event.pos):
                            self._launch_transition(self.index + 1)
                    if self.index > 0 and self.btn_previous.rect.collidepoint(event.pos):
                        self._launch_transition(self.index - 1)

            for btn in [self.btn_next, self.btn_previous,
                        self.btn_close, self.btn_pass]:
                btn.verify_hover(pos)

            # Update the rings
            self._update_particles(dt, tms)
            # Update the transition
            self._update_transition()

            self._draw(tms)
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Transition handling
    # ------------------------------------------------------------------

    def _launch_transition(self, next):
        if self._next_slide is None:
            self._next_slide = next
            self._transition_dir  = 1      # fade out
            self._alpha_transition = 0

    def _update_transition(self):
        if self._transition_dir == 1:      # fade out
            self._alpha_transition = min(255, self._alpha_transition + self._FADE_SPEED)
            if self._alpha_transition >= 255 and self._next_slide is not None:
                self.index = self._next_slide
                self._next_slide = None
                self._transition_dir  = -1
        elif self._transition_dir == -1:   # fade in
            self._alpha_transition = max(0, self._alpha_transition - self._FADE_SPEED)

    # ------------------------------------------------------------------
    # Particles
    # ------------------------------------------------------------------

    def _update_particles(self, dt, tms):
        INTERVAL_MS = 1800
        if tms - self._timer_ring > INTERVAL_MS:
            self._timer_ring = tms
            # A ring centered on the panel, slightly random
            cx = self.cx + random.randint(-self.width // 5, self.width // 5)
            cy = self.cy + random.randint(-self.height // 5, self.height // 5)
            col = random.choice([self.CYAN, self.VIOLET, self.MAUVE])
            rmax = max(self.width, self.height) * 0.55
            self._rings.append(_Ring(cx, cy, rmax, random.uniform(0.8, 1.4), col))

        self._rings = [a for a in self._rings if a.update(dt)]

    # ------------------------------------------------------------------
    # Main rendering
    # ------------------------------------------------------------------

    def _draw(self, tms):
        # Base animated background (existing import)
        draw_background_echo(self.screen, self.width, self.height, tms)

        # Ambient stars
        for e in self._stars:
            e.draw(self.screen, tms)

        # Echo rings
        for a in self._rings:
            a.draw(self.screen)

        # Peripheral vignette
        self._vignette()

        # Central panel
        pw = int(self.width * 0.88)
        ph = int(self.height * 0.82)
        px = (self.width - pw) // 2
        py = int(self.height * 0.05)
        self._panel(px, py, pw, ph, tms)

        if self.index == 0:
            self._slide_gameplay(px, py, pw, ph, tms)
        else:
            self._slide_lore(px, py, pw, ph, tms)

        self._navigation(tms)
        self._indicator()

        # Transition overlay
        if self._alpha_transition > 0:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((4, 2, 14, self._alpha_transition))
            self.screen.blit(overlay, (0, 0))

    # ------------------------------------------------------------------
    # Panel
    # ------------------------------------------------------------------

    def _panel(self, x, y, w, h, tms):
        # Body
        background = pygame.Surface((w, h), pygame.SRCALPHA)
        background.fill((8, 5, 22, 210))
        self.screen.blit(background, (x, y))

        # Pulsing border
        pulse = 0.6 + 0.4 * math.sin(tms / 1100)
        edge  = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(edge, (*self.VIOLET, int(120 * pulse)), edge.get_rect(), 1, border_radius=10)
        self.screen.blit(edge, (x, y))

        # Decorative top line with a gradient
        _separator_gradient(self.screen, x + 30, y, w - 60, self.VIOLET, self.CYAN)

        # Decorative corners
        coin_l = 14
        alpha_c = 160
        for dx, dy, hflip, vflip in [(0,0,1,1),(w-coin_l,0,-1,1),(0,h-coin_l,1,-1),(w-coin_l,h-coin_l,-1,-1)]:
            cs = pygame.Surface((coin_l, coin_l), pygame.SRCALPHA)
            pygame.draw.line(cs, (*self.CYAN, alpha_c), (0 if hflip>0 else coin_l-1, 0),
                             (0 if hflip>0 else coin_l-1, coin_l-1), 1)
            pygame.draw.line(cs, (*self.CYAN, alpha_c), (0, 0 if vflip>0 else coin_l-1),
                             (coin_l-1, 0 if vflip>0 else coin_l-1), 1)
            self.screen.blit(cs, (x + dx, y + dy))

    # ------------------------------------------------------------------
    # Peripheral vignette
    # ------------------------------------------------------------------

    def _vignette(self):
        v = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for i, alpha in [(0, 160), (1, 80), (2, 40)]:
            edge_w = (i + 1) * 38
            pygame.draw.rect(v, (0, 0, 0, alpha),
                             (0, 0, self.width, self.height),
                             edge_w)
        self.screen.blit(v, (0, 0))

    # ------------------------------------------------------------------
    # Slide 0 - Mechanics
    # ------------------------------------------------------------------

    def _slide_gameplay(self, px, py, pw, ph, tms):
        mh = int(pw * 0.042)
        mv = int(ph * 0.048)
        col_w = (pw - mh * 3) // 2
        c1x = px + mh
        c2x = px + mh * 2 + col_w
        y0  = py + mv

        # Title
        title = self.font_title.render(get_text("tuto_gameplay_title"), True, self.CYAN)
        self.screen.blit(title, (c1x, y0))
        y0 += title.get_height() + 3

        sub = self.font_text.render(
            get_text("tuto_gameplay_sub"),
            True, (80, 65, 120))
        self.screen.blit(sub, (c1x, y0))
        y0 += sub.get_height() + 10

        _separator_gradient(self.screen, c1x, y0, pw - mh * 2, self.VIOLET, self.CYAN)
        y0 += 14

        self._col_controls(c1x, y0, col_w, tms)
        self._col_systems(c2x, y0, col_w, tms)

    def _key(self, key_item):
        return self.params_controls.get(key_item, '?').upper()

    def _col_controls(self, x, y, w, tms):
        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_controls"), x, y, self.CYAN, self.CYAN, 25, 80)

        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('left')} / {self._key('right')} ]",
                      get_text("tuto_ctrl_move"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('jump')} ]",
                      get_text("tuto_ctrl_jump"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('dash')} ]",
                      get_text("tuto_ctrl_dash"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('echo')} ]",
                      get_text("tuto_ctrl_echo"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('echo_dir')} ]",
                      get_text("tuto_ctrl_echo_dir"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      f"[ {self._key('attack')} ]",
                      get_text("tuto_ctrl_attack"))
        y = _line_kv(self.screen, self.font_text, self.font_text, x, y,
                      get_text("tuto_key_escape"), get_text("tuto_ctrl_pause"))
        y += 16

        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_combat"), x, y, self.PINK, self.PINK, 20, 70)

        p = self.font_text
        lines = get_text("tuto_hp_lines")
        for before, bold, after in lines:
            surf_av = p.render(before, True, (155, 145, 200))
            surf_g  = p.render(bold,  True, (220, 180, 255))
            surf_ap = p.render(after, True, (155, 145, 200))
            self.screen.blit(surf_av, (x, y))
            self.screen.blit(surf_g,  (x + surf_av.get_width(), y))
            self.screen.blit(surf_ap, (x + surf_av.get_width() + surf_g.get_width(), y))
            y += surf_g.get_height() + 6
        y += 6

        # Highlight block with the enemies' HP
        lines_hp = get_text("tuto_enemy_hp_lines")
        line_h = p.get_height() + 8
        block_h = len(lines_hp) * line_h + 12
        _block_highlight(self.screen, x, y, w - 10, block_h, self.VIOLET, 18, 150)
        yb = y + 8
        for hp, desc in lines_hp:
            sv = p.render(hp,   True, (200, 175, 255))
            sd = p.render(desc, True, (140, 130, 180))
            self.screen.blit(sv, (x + 12, yb))
            self.screen.blit(sd, (x + 12 + sv.get_width() + 10, yb))
            yb += line_h

    def _col_systems(self, x, y, w, tms):
        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_echolocation"), x, y, self.CYAN, self.CYAN, 25, 80)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_echo_intro"),
                        x, y, w, (155, 145, 200))
        info_s = self.font_text.render(get_text("tuto_echo_radial_info"),
                                          True, (80, 160, 200))
        self.screen.blit(info_s, (x, y))
        y += info_s.get_height() + 4
        info_dir = self.font_text.render(get_text("tuto_echo_dir_info"),
                                            True, (80, 160, 200))
        self.screen.blit(info_dir, (x, y))
        y += info_dir.get_height() + 14

        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_lost_souls"), x, y, self.MAUVE, self.MAUVE, 22, 75)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_lost_souls_text"),
                        x, y, w, (155, 145, 200))
        y += 12

        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_progress"), x, y, self.OR, self.OR, 20, 70)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_progress_text"),
                        x, y, w, (155, 145, 200))

    # ------------------------------------------------------------------
    # Slide 1 - Lore
    # ------------------------------------------------------------------

    def _slide_lore(self, px, py, pw, ph, tms):
        mh = int(pw * 0.045)
        mv = int(ph * 0.048)
        x  = px + mh
        y  = py + mv
        tw = pw - mh * 2

        title = self.font_title.render(get_text("tuto_lore_title"), True, self.MAUVE)
        self.screen.blit(title, (x, y))
        y += title.get_height() + 3

        sub = self.font_text.render(get_text("tuto_lore_sub"),
                                        True, (70, 55, 110))
        self.screen.blit(sub, (x, y))
        y += sub.get_height() + 10

        _separator_gradient(self.screen, x, y, tw, self.MAUVE, self.VIOLET)
        y += 14

        col_w  = (tw - mh) // 2
        col2_x = x + col_w + mh

        self._lore_left(x, y, col_w)
        self._lore_right(col2_x, y, col_w)

    def _lore_left(self, x, y, w):
        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_silence"), x, y, self.MAUVE, self.MAUVE, 22, 75)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_silence_text"),
                        x, y, w, (155, 145, 200))
        y += 12

        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_gate"), x, y, self.OR, self.OR, 20, 70)
        _text_wrap(self.screen, self.font_text,
                    get_text("tuto_gate_text"),
                    x, y, w, (155, 145, 200))

    def _lore_right(self, x, y, w):
        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_scout"), x, y, self.CYAN, self.CYAN, 25, 80)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_scout_text"),
                        x, y, w, (155, 145, 200))
        y += 10

        y = y + _badge(self.screen, self.font_button,
                       get_text("tuto_badge_wandering"), x, y, self.PINK, self.PINK, 20, 70)
        y = _text_wrap(self.screen, self.font_text,
                        get_text("tuto_wandering_text"),
                        x, y, w, (155, 145, 200))
        y += 12

        # Final call to action
        block_h = self.font_text.get_height() * 3 + 26
        _block_highlight(self.screen, x, y, w - 10, block_h, self.CYAN, 15, 200)
        cta_lines = get_text("tuto_cta_lines")
        yb = y + 10
        for line in cta_lines:
            s = self.font_text.render(line, True, self.CYAN)
            self.screen.blit(s, (x + 14, yb))
            yb += s.get_height() + 6

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigation(self, tms):
        is_last = (self.index == self.total - 1)
        if is_last:
            self.btn_close.draw(self.screen)
        else:
            self.btn_next.draw(self.screen)
        if self.index > 0:
            self.btn_previous.draw(self.screen)
        self.btn_pass.draw(self.screen)

    def _indicator(self):
        radius  = 5
        space = 18
        total_w = self.total * radius * 2 + (self.total - 1) * space
        x0 = self.cx - total_w // 2
        y  = self.height - 14

        for i in range(self.total):
            cx = x0 + i * (radius * 2 + space) + radius
            if i == self.index:
                # Active dot with a halo
                halo = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(halo, (*self.CYAN, 40), (radius * 2, radius * 2), radius * 2)
                self.screen.blit(halo, (cx - radius * 2, y - radius * 2))
                pygame.draw.circle(self.screen, self.CYAN, (cx, y), radius)
            else:
                pygame.draw.circle(self.screen, (50, 40, 80), (cx, y), radius - 1)
                pygame.draw.circle(self.screen, (80, 65, 120), (cx, y), radius - 1, 1)