# core/lore_sign.py
# Ancient lore stele: stone engraved with incomprehensible runes.
# Interaction -> payment in souls -> translation of the Scout's message.

import pygame
import math
import os
import sys
import random
from settings import PLAYER_MAX_HP
from utils.i18n import get_text


# -- Lore texts live in utils/i18n.py (lore_* keys) ---
COST_SOULS = 0
COST_DASH = 50
COST_UPGRADE_DAMAGE   = 75
COST_UPGRADE_HP       = 20
COST_UPGRADE_ECHO_DIR = 10
MAX_PURCHASES_HP         = 5

WIDTH_SIGN = 48
HEIGHT_SIGN = 56

# -- Hand-drawn rune shapes -------------------------------------------------
# Each rune is a list of segments (x1, y1, x2, y2) on an 8x12 grid.
_RUNES_SHAPES = [
    [(4, 0, 4, 12), (2, 3, 6, 3), (2, 9, 6, 9)],           # 0: branched I
    [(1, 1, 7, 11), (7, 1, 1, 11)],                          # 1: X
    [(2, 0, 7, 6), (7, 6, 2, 12)],                           # 2: zigzag
    [(4, 0, 4, 12), (4, 4, 1, 1), (4, 4, 7, 1)],             # 3: up arrow
    [(2, 0, 2, 12), (2, 3, 7, 1), (2, 7, 7, 5)],             # 4: stem with branches
    [(4, 0, 7, 4), (7, 4, 4, 8), (4, 8, 1, 4), (1, 4, 4, 0)], # 5: diamond
    [(2, 0, 2, 12), (7, 0, 7, 12), (2, 0, 7, 12)],           # 6: N
    [(4, 0, 4, 12), (1, 4, 7, 4)],                           # 7: T
    [(3, 0, 3, 12), (3, 5, 7, 2), (3, 5, 7, 8)],             # 8: right arrow
    [(3, 0, 3, 12), (3, 4, 7, 7), (7, 7, 3, 10)],            # 9: snake
]

# Rune sequences of each inscription line (indices into _RUNES_SHAPES)
_LINES_INSCRIPTION = [
    [4, 7, 0, 2, 8],
    [1, 3, 9, 6, 4],
    [7, 0, 5, 8, 3],
]

# Stone colors
_STONE      = (72,  68,  80)
_STONE_EDGE = (38,  35,  46)
_STONE_LUM  = (108, 103, 120)
_STONE_SHADOW = (50,  47,  58)


def _draw_rune(surf, shapes, x, y, scale, color):
    """Draw a rune (list of segments) at (x, y) with the given scale."""
    ep = max(1, scale // 7)
    for x1, y1, x2, y2 in shapes:
        sx1 = x + x1 * scale // 8
        sy1 = y + y1 * scale // 12
        sx2 = x + x2 * scale // 8
        sy2 = y + y2 * scale // 12
        pygame.draw.line(surf, color, (sx1, sy1), (sx2, sy2), ep)


def _load_sprite_parchment():
    try:
        base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
        img = pygame.image.load(os.path.join(base, 'assets', 'parchment_64x64.png')).convert_alpha()
        return img
    except Exception as e:
        print(f'[LORE_SIGN] parchment sprite not found: {e}')
        return None


class LoreSign:
    """
    Stone stele engraved with incomprehensible runes.
    - Interaction -> payment -> translation unlocked.
    - Interacting once unlocked -> reading the Scout's message.
    """

    RANGE_INTERACTION = 80
    _sprite_parchment = None  # cache shared between all instances
    # (rune_idx, rgb_color) -> pre-rendered Surface
    _runes_particles_cache: "dict[tuple[int, tuple[int, int, int]], pygame.Surface]" = {}
    # (rgb_color, size, state) -> base Surface at max alpha
    _halo_sign_cache: "dict[tuple[tuple[int, int, int], int, str], pygame.Surface]" = {}
    # size -> reusable scratch SRCALPHA Surface
    _halo_scratch: "dict[int, pygame.Surface]" = {}

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, WIDTH_SIGN, HEIGHT_SIGN)
        self.is_unlocked = False
        self._phase = 0.0
        self._font_lore  = None
        self._font_title = None
        self._font_ui    = None
        self._font_indicator = None
        self._font_star_stele = None
        self._surf_cache = None
        self._surf_state  = None

    # -- Network ---------------------------------------------------------------

    def get_state(self, id_sign: int = None) -> dict:
        d = {'x': self.x, 'y': self.y, 'is_unlocked': self.is_unlocked, 'type_sign': getattr(self, 'type_sign', 'lore'),}
        if id_sign is not None:
            d['id'] = id_sign
        return d

    def set_state(self, data: dict):
        self.x             = data['x']
        self.y             = data['y']
        self.is_unlocked = data['is_unlocked']
        self.type_sign = data.get('type_sign', 'lore')
        self.rect.topleft  = (self.x, self.y)
        self._surf_cache   = None

    # -- Server logic -----------------------------------------------------------

    def try_pay(self, player, shop_item: str = None) -> str:
        type_p = getattr(self, 'type_sign', 'lore')
        if type_p == 'shop_upgrades':
            return self._try_payment_upgrade(player, shop_item or '')
        if self.is_unlocked:
            return 'already_unlocked'
        if type_p == 'shop_dash':
            if player.money < COST_DASH:
                return 'pauvre'
            if player.can_dash:
                return 'already_unlocked'
            player.money -= COST_DASH
            player.can_dash = True
            self.is_unlocked = True
            player.sounds_to_play.append('free_soul')
            return 'unlocked'
        self.is_unlocked = True
        player.sounds_to_play.append('lost_soul')
        return 'unlocked'

    def _try_payment_upgrade(self, player, shop_item: str) -> str:
        if shop_item == 'damage':
            if player.damage_bonus >= 1:
                return 'already_unlocked'
            if player.money < COST_UPGRADE_DAMAGE:
                return 'pauvre'
            player.money -= COST_UPGRADE_DAMAGE
            player.damage_bonus = 1
            player.sounds_to_play.append('free_soul')
            return 'unlocked'
        elif shop_item == 'max_hp':
            if player.max_hp_bonus >= MAX_PURCHASES_HP:
                return 'already_unlocked'
            if player.money < COST_UPGRADE_HP:
                return 'pauvre'
            player.money -= COST_UPGRADE_HP
            player.max_hp_bonus += 1
            player.max_hp = PLAYER_MAX_HP + player.max_hp_bonus
            player.hp = min(player.hp + 1, player.max_hp)
            player.sounds_to_play.append('free_soul')
            return 'unlocked'
        elif shop_item == 'echo_dir':
            if player.can_echo_dir:
                return 'already_unlocked'
            if player.money < COST_UPGRADE_ECHO_DIR:
                return 'pauvre'
            player.money -= COST_UPGRADE_ECHO_DIR
            player.can_echo_dir = True
            player.sounds_to_play.append('free_soul')
            return 'unlocked'
        return 'error'

    def update(self, time_ms: int):
        self._phase = (time_ms / 1200.0) % (2 * math.pi)

    # -- Client rendering -------------------------------------------------------

    def _init_fonts(self):
        if self._font_lore is not None:
            return
        self._font_lore  = pygame.font.Font(None, 28)
        self._font_title = pygame.font.Font(None, 34)
        self._font_ui    = pygame.font.Font(None, 28)
        self._font_indicator = pygame.font.Font(None, 26)
        self._font_star_stele = pygame.font.Font(None, 30)

    def draw(self, surface: pygame.Surface, camera_offset=(0, 0),
                 time_ms: int = 0, key_interact: str = 'F'):
        self._init_fonts()
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        type_p = getattr(self, 'type_sign', 'lore')

        if type_p == 'letter':
            self._draw_letter(surface, sx, sy, time_ms, key_interact)
            return

        # Ambient halo
        self._draw_halo(surface, sx, sy)

        # Stele surface (cached)
        state_current = 'unlocked' if self.is_unlocked else 'locked'
        if self._surf_cache is None or self._surf_state != state_current:
            self._surf_cache = self._build_surface_sign(state_current)
            self._surf_state  = state_current
        # The surface is 8px wider and 12px taller than the rect
        surface.blit(self._surf_cache, (sx - 4, sy - 6))

        # Rune particles
        self._draw_particles(surface, sx, sy, time_ms)

        # Interaction badge
        self._draw_indicator(surface, sx, sy, time_ms, key_interact)

    def _draw_letter(self, surface: pygame.Surface, sx: int, sy: int,
                         time_ms: int, key_interact: str):
        # Lazy loading of the parchment sprite
        if LoreSign._sprite_parchment is None:
            LoreSign._sprite_parchment = _load_sprite_parchment()

        # Discreet warm halo (pulsing off-white) - base cached
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        sz = 80
        cx, cy = sz // 2, sz // 2
        col = (240, 220, 160)
        key_item = (col, sz, 'letter')
        base = LoreSign._halo_sign_cache.get(key_item)
        if base is None:
            base = pygame.Surface((sz, sz), pygame.SRCALPHA)
            for r, a in [(32, 6), (22, 14), (12, 28)]:
                pygame.draw.circle(base, (*col, a), (cx, cy), r)
            LoreSign._halo_sign_cache[key_item] = base
        base.set_alpha(int(pulse * 255))
        surface.blit(base, (sx + WIDTH_SIGN // 2 - cx,
                            sy + HEIGHT_SIGN // 2 - cy))

        # Parchment sprite centered on the rect
        img = LoreSign._sprite_parchment
        if img is not None:
            # Slight vertical float
            flow = int(3 * math.sin(self._phase))
            iw, ih = img.get_size()
            bx = sx + WIDTH_SIGN // 2 - iw // 2
            by = sy + HEIGHT_SIGN // 2 - ih // 2 + flow
            surface.blit(img, (bx, by))
        else:
            # Fallback: beige rectangle if the image is missing
            pygame.draw.rect(surface, (210, 185, 130),
                             pygame.Rect(sx, sy, WIDTH_SIGN, HEIGHT_SIGN),
                             border_radius=4)

        # Interaction badge
        self._draw_indicator(surface, sx, sy, time_ms, key_interact)

    # -- Building the stele surface --------------------------------------------

    def _build_surface_sign(self, state: str) -> pygame.Surface:
        W = WIDTH_SIGN + 8   # 56
        H = HEIGHT_SIGN + 12  # 68
        surf = pygame.Surface((W, H), pygame.SRCALPHA)

        rng_t = random.Random(314)

        # -- Base / pedestal --
        base = pygame.Rect(W // 2 - 12, H - 10, 24, 8)
        pygame.draw.rect(surf, _STONE_SHADOW, base, border_radius=2)
        pygame.draw.rect(surf, _STONE_EDGE, base, 1, border_radius=2)

        # -- Stele body (slightly rounded at the top) --
        stele = pygame.Rect(2, 2, W - 4, H - 12)
        pygame.draw.rect(surf, _STONE, stele, border_radius=5)

        # Stone grain texture (random points, cached, fixed Random)
        for _ in range(220):
            gx = rng_t.randint(3, W - 4)
            gy = rng_t.randint(3, H - 13)
            ga = rng_t.randint(10, 35)
            gc = rng_t.choice((_STONE_SHADOW, _STONE_LUM))
            surf.set_at((gx, gy), (*gc, ga))

        # Diagonal crack (decorative)
        for fi in range(stele.top + 8, stele.bottom - 6):
            fx = W // 3 + int(math.sin(fi * 0.25) * 2)
            if 3 <= fx < W - 3:
                surf.set_at((fx, fi), (*_STONE_EDGE, 160))

        # Stele edges
        pygame.draw.rect(surf, _STONE_EDGE, stele, 2, border_radius=5)
        # Left and top highlight (light effect)
        pygame.draw.line(surf, (*_STONE_LUM, 100), (3, 6), (3, H - 14), 1)
        pygame.draw.line(surf, (*_STONE_LUM, 70),  (4, 4), (W - 5, 4),  1)

        # -- Engraved inscription area --
        margin  = 7
        zone   = pygame.Rect(margin, margin + 4, W - margin * 2, H - margin * 2 - 10)
        zone_s = pygame.Surface((zone.w, zone.h), pygame.SRCALPHA)
        zone_s.fill((*_STONE_SHADOW, 80))
        surf.blit(zone_s, zone.topleft)
        pygame.draw.rect(surf, (*_STONE_EDGE, 180), zone, 1)

        # Engraved corners of the area
        sz = 3
        for cx, cy in [(zone.x, zone.y), (zone.right - sz, zone.y),
                       (zone.x, zone.bottom - sz), (zone.right - sz, zone.bottom - sz)]:
            pygame.draw.rect(surf, (*_STONE_LUM, 120), pygame.Rect(cx, cy, sz, sz))

        type_p = getattr(self, 'type_sign', 'lore')

        if state == 'locked':
            # Incomprehensible runes engraved in the stone
            if type_p == 'shop_dash':
                color_rune = (70, 210, 225)
                color_shadow = (15, 55, 65, 180)
            else:
                color_rune = (145, 85, 255)
                color_shadow = (25, 10, 55, 180)

            scale  = 7
            rune_w = scale + 4
            rune_h = scale + 5
            num_cols = max(1, (zone.w - 6) // rune_w)
            num_rows = len(_LINES_INSCRIPTION)
            tot_w  = num_cols * rune_w
            tot_h  = num_rows * rune_h
            sx0    = zone.x + (zone.w - tot_w) // 2
            sy0    = zone.y + (zone.h - tot_h) // 2

            for li, line in enumerate(_LINES_INSCRIPTION):
                for ri in range(num_cols):
                    ridx  = line[ri % len(line)]
                    rx    = sx0 + ri * rune_w
                    ry    = sy0 + li * rune_h
                    frome = _RUNES_SHAPES[ridx % len(_RUNES_SHAPES)]
                    # Engraving shadow (+1 offset)
                    _draw_rune(surf, frome, rx + 1, ry + 1, scale, color_shadow)
                    # Main rune
                    _draw_rune(surf, frome, rx, ry, scale, (*color_rune, 215))

        else:
            # Unlocked state: golden runic mandala
            cx_s = W // 2
            cy_s = zone.y + zone.h // 2

            # Engraved base circle
            pygame.draw.circle(surf, _STONE_SHADOW, (cx_s, cy_s), 14)
            pygame.draw.circle(surf, (110, 85, 22), (cx_s, cy_s), 14, 2)

            # 6 small runes in a crown
            for i in range(6):
                a = i * math.pi / 3
                rx = int(cx_s + math.cos(a) * 20) - 3
                ry = int(cy_s + math.sin(a) * 20) - 5
                f  = _RUNES_SHAPES[i % len(_RUNES_SHAPES)]
                _draw_rune(surf, f, rx + 1, ry + 1, 6, (40, 30, 5, 160))
                _draw_rune(surf, f, rx, ry, 6, (185, 145, 40))

            # Central star
            self._init_fonts()
            star   = self._font_star_stele.render("✦", True, (255, 200, 55))
            surf.blit(star, star.get_rect(center=(cx_s, cy_s)))

        return surf

    # -- Ambient halo ----------------------------------------------------------

    def _draw_halo(self, surface, sx, sy):
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        sz    = 64
        cx, cy = sz // 2, sz // 2

        type_p = getattr(self, 'type_sign', 'lore')
        if type_p == 'shop_upgrades':
            col = (60, 200, 100)
            rings = ((26, 10), (18, 22), (10, 42))
            state = 'shop_upgrades'
        elif self.is_unlocked:
            col = (255, 190, 50)
            rings = ((26, 8), (18, 18), (10, 35))
            state = 'unlocked'
        elif type_p == 'shop_dash':
            col = (60, 200, 220)
            rings = ((26, 10), (18, 22), (10, 42))
            state = 'shop_dash'
        else:
            col = (130, 70, 255)
            rings = ((26, 10), (18, 22), (10, 42))
            state = 'lore'

        cache = LoreSign._halo_sign_cache
        key_item = (col, sz, state)
        base = cache.get(key_item)
        if base is None:
            base = pygame.Surface((sz, sz), pygame.SRCALPHA)
            for r, a in rings:
                pygame.draw.circle(base, (*col, a), (cx, cy + 10), r)
            cache[key_item] = base

        scratch = LoreSign._halo_scratch.get(sz)
        if scratch is None:
            scratch = pygame.Surface((sz, sz), pygame.SRCALPHA)
            LoreSign._halo_scratch[sz] = scratch
        scratch.fill((0, 0, 0, 0))
        base.set_alpha(int(pulse * 255))
        scratch.blit(base, (0, 0))

        # Rising light particles (time-dependent motion, drawn on a SRCALPHA scratch)
        for i in range(3):
            ph  = self._phase + i * 2.1
            hpx = int(cx + math.cos(ph * 0.8) * 9)
            hpy = int(cy + 4 - (i * 6) - (math.sin(ph) * 4))
            ha  = max(0, int(70 * math.sin(ph + 1.5)))
            if ha > 0 and 0 <= hpx < sz and 0 <= hpy < sz:
                pygame.draw.circle(scratch, (*col, ha), (hpx, hpy), 2)

        surface.blit(scratch, (sx + WIDTH_SIGN // 2 - cx,
                               sy + HEIGHT_SIGN // 2 - cy))

    # -- Floating rune particles -----------------------------------------------

    def _draw_particles(self, surface, sx, sy, time_ms):
        """Small runes floating around the stele."""
        type_p  = getattr(self, 'type_sign', 'lore')
        col_r   = (60, 200, 220) if type_p == 'shop_dash' else (130, 70, 255)
        col_u   = (255, 195, 50)
        color = col_u if self.is_unlocked else col_r
        num      = 4 if not self.is_unlocked else 3

        cache = LoreSign._runes_particles_cache
        for i in range(num):
            ph  = self._phase + i * (2 * math.pi / num)
            px  = sx + WIDTH_SIGN // 2 + math.cos(ph) * (20 + i * 3)
            py  = sy + HEIGHT_SIGN // 2 + math.sin(ph * 0.7) * 9 - i * 4
            a   = max(0, int(90 + 80 * math.sin(ph * 2)))
            ridx = (i * 3) % len(_RUNES_SHAPES)
            key_item = (ridx, color)
            tmp = cache.get(key_item)
            if tmp is None:
                tmp = pygame.Surface((9, 11), pygame.SRCALPHA)
                _draw_rune(tmp, _RUNES_SHAPES[ridx], 0, 0, 5, (*color, 255))
                cache[key_item] = tmp
            tmp.set_alpha(a)
            surface.blit(tmp, (int(px) - 4, int(py) - 5))

    # -- Interaction badge -----------------------------------------------------

    def _draw_indicator(self, surface, sx, sy, time_ms, key_name: str = 'F'):
        self._init_fonts()
        f  = self._font_indicator
        tk = (key_name or 'F').upper()
        type_p = getattr(self, 'type_sign', 'lore')
        if type_p == 'shop_upgrades':
            label = get_text("lore_sign_upgrades").format(key=tk)
            color  = (80, 220, 120)
        elif not self.is_unlocked:
            if type_p == 'shop_dash':
                label = get_text("lore_sign_shop_dash").format(key=tk, cost=COST_DASH)
            else:
                label = get_text("lore_sign_read").format(key=tk)
            color  = (80, 210, 230) if type_p == 'shop_dash' else (160, 100, 255)
        else:
            label = get_text("lore_sign_read").format(key=tk)
            color  = (255, 200, 70)

        s = f.render(label, True, color)
        flow = int(3 * math.sin(self._phase * 2))
        bx   = sx + WIDTH_SIGN // 2 - s.get_width() // 2
        by   = sy - 24 + flow

        bg = pygame.Surface((s.get_width() + 10, s.get_height() + 6), pygame.SRCALPHA)
        # Dark stone background
        pygame.draw.rect(bg, (22, 18, 35, 200), bg.get_rect(), border_radius=4)
        pygame.draw.rect(bg, (*color, 160), bg.get_rect(), 1, border_radius=4)
        bg.blit(s, (5, 3))
        surface.blit(bg, (bx - 5, by - 3))


# -- Lore dialogue bubble ---------------------------------------------------

class LoreBubble:
    """
    Translation panel: shows the Scout's message once the inscription
    has been deciphered.
    Style: dark stone tablet with engraved golden text.
    """

    WIDTH = 640
    HEIGHT = 460
    MARGIN   = 34

    def __init__(self, width_screen: int, height_screen: int):
        self.lw   = width_screen
        self.lh   = height_screen
        self.rect = pygame.Rect(
            width_screen  // 2 - self.WIDTH // 2,
            height_screen  // 2 - self.HEIGHT // 2,
            self.WIDTH, self.HEIGHT,
        )
        self.visible    = False
        self._scroll    = 0
        self._time_open = 0

        self._font_text  = pygame.font.Font(None, 27)
        self._font_title  = pygame.font.Font(None, 34)
        self._font_close = pygame.font.Font(None, 24)

        # Pre-built background surface (static)
        self._surf_background   = None
        self._build_background()

    def _build_background(self):
        W, H = self.WIDTH, self.HEIGHT
        surf  = pygame.Surface((W, H), pygame.SRCALPHA)

        # Dark vertical gradient (deep granite)
        for y in range(H):
            t = y / H
            r = int(24 + t * 14)
            g = int(20 + t * 10)
            b = int(32 + t * 18)
            pygame.draw.line(surf, (r, g, b, 248), (0, y), (W, y))

        # Stone grain
        rng = random.Random(555)
        for _ in range(500):
            gx = rng.randint(0, W - 1)
            gy = rng.randint(0, H - 1)
            ga = rng.randint(6, 22)
            surf.set_at((gx, gy), (90, 85, 105, ga))

        # Gold-brown outer border
        pygame.draw.rect(surf, (115, 88, 22), pygame.Rect(0, 0, W, H), 3, border_radius=7)
        # Thin inner border
        pygame.draw.rect(surf, (75, 57, 12), pygame.Rect(6, 6, W - 12, H - 12), 1, border_radius=5)

        # Ornate corners: small engraved runes
        for cx, cy in [(10, 10), (W - 22, 10), (10, H - 22), (W - 22, H - 22)]:
            # Corner background
            pygame.draw.rect(surf, (50, 45, 60), pygame.Rect(cx, cy, 12, 12))
            pygame.draw.rect(surf, (100, 78, 18), pygame.Rect(cx, cy, 12, 12), 1)
            # Mini rune
            _draw_rune(surf, _RUNES_SHAPES[5], cx + 1, cy, 8, (160, 125, 35))

        # Horizontal separator under the title (y=56)
        for px in range(self.MARGIN, W - self.MARGIN):
            t = (px - self.MARGIN) / max(W - self.MARGIN * 2 - 1, 1)
            fade = math.sin(t * math.pi)
            a = int(180 * fade)
            surf.set_at((px, 55), (115, 88, 22, a))
            surf.set_at((px, 56), (55,  42, 10, a // 2))

        # Small decorative runes along the separator
        for i, ridx in enumerate([2, 7, 5, 0, 7, 2]):
            rx = self.MARGIN + i * ((W - self.MARGIN * 2) // 6) - 3
            _draw_rune(surf, _RUNES_SHAPES[ridx], rx, 47, 7, (130, 100, 28))

        # Bottom separator (above the hint)
        sep_bot = H - 28
        for px in range(self.MARGIN, W - self.MARGIN):
            t = (px - self.MARGIN) / max(W - self.MARGIN * 2 - 1, 1)
            fade = math.sin(t * math.pi)
            a = int(100 * fade)
            surf.set_at((px, sep_bot), (115, 88, 22, a))

        self._surf_background = surf

    def open(self, text=None, title=None, sub_title=None):
        self.visible    = True
        self._scroll    = 0
        self._time_open = pygame.time.get_ticks()
        self._pages         = None
        self._page_current = 0
        self._text     = text if text is not None else get_text("lore_stele")
        self._title_bubble    = title if title is not None else get_text("lore_title_inscription")
        self._sub_title_bubble = sub_title if sub_title is not None else get_text("lore_sub_inscription")

    def open_multi(self, pages: list):
        """pages: list of dicts with keys 'text', 'title', 'sub_title'"""
        self.visible        = True
        self._scroll        = 0
        self._time_open     = pygame.time.get_ticks()
        self._pages         = pages
        self._page_current = 0
        self._apply_page()

    def _apply_page(self):
        p = self._pages[self._page_current]
        self._text            = p.get('text') or get_text("lore_stele")
        self._title_bubble      = p.get('title', get_text("lore_title_inscription"))
        self._sub_title_bubble = p.get('sub_title', "")
        self._scroll           = 0

    def close(self):
        self.visible = False

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close(); return True
            pages = getattr(self, '_pages', None)
            if pages and len(pages) > 1:
                if event.key == pygame.K_LEFT:
                    if self._page_current > 0:
                        self._page_current -= 1
                        self._apply_page()
                    return True
                if event.key == pygame.K_RIGHT:
                    if self._page_current < len(pages) - 1:
                        self._page_current += 1
                        self._apply_page()
                    return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(event.pos):
                self.close(); return True
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - event.y * 18)
            return True
        return False

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        time_ms = pygame.time.get_ticks()
        elapsed  = time_ms - self._time_open

        # Dark overlay (fade)
        ov = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, min(185, int(185 * elapsed / 350))))
        surface.blit(ov, (0, 0))

        # Drop shadow
        sh = pygame.Surface((self.WIDTH + 18, self.HEIGHT + 18), pygame.SRCALPHA)
        sh.fill((0, 0, 0, min(130, int(130 * elapsed / 350))))
        surface.blit(sh, (self.rect.x - 4, self.rect.y + 12))

        # Tablet background
        surface.blit(self._surf_background, self.rect.topleft)

        # -- Title ------------------------------------------------------
        title_txt = getattr(self, '_title_bubble', "✦   Inscription Traduite   ✦")
        title = self._font_title.render(title_txt, True, (220, 178, 58))
        surface.blit(title, title.get_rect(center=(self.rect.centerx, self.rect.y + 32)))

        # Attribution subtitle
        f_sub = pygame.font.Font(None, 22)
        sub_title_txt = getattr(self, '_sub_title_bubble', get_text("lore_sub_inscription"))
        sub   = f_sub.render(sub_title_txt, True, (120, 92, 28))
        surface.blit(sub, sub.get_rect(center=(self.rect.centerx, self.rect.y + 49)))

        # -- Scrollable text area ---------------------------------------
        zone_y  = self.rect.y + 66
        zone_h  = self.HEIGHT - 92
        zone_rect = pygame.Rect(
            self.rect.x + self.MARGIN, zone_y,
            self.WIDTH - self.MARGIN * 2, zone_h,
        )

        clip_orig = surface.get_clip()
        surface.set_clip(zone_rect)

        lh       = self._font_text.get_height() + 5
        y_cursor = zone_y + 10 - self._scroll

        text = self._text if hasattr(self, '_text') else get_text("lore_stele")
        for line in text:
            if line == "":
                y_cursor += lh // 2
                continue
            if line.startswith("  ") or line.startswith("«"):
                color = (210, 178, 100)   # quotation: warmer gold
            elif line.startswith("—"):
                color = (175, 138, 62)    # attribution: duller gold
                y_cursor += 4
            else:
                color = (238, 215, 150)   # body: golden cream

            s = self._font_text.render(line, True, color)
            surface.blit(s, (zone_rect.x + 6, y_cursor))
            y_cursor += lh

        surface.set_clip(clip_orig)

        # -- Multi-page navigation -------------------------------------
        pages = getattr(self, '_pages', None)
        if pages and len(pages) > 1:
            f_nav   = pygame.font.Font(None, 26)
            btn_w, btn_h = 72, 24
            cy_nav = self.rect.bottom - 30

            # Left button  < Prev.
            can_prev = self._page_current > 0
            r_prev = pygame.Rect(self.rect.centerx - 100 - btn_w // 2, cy_nav - btn_h // 2, btn_w, btn_h)
            pygame.draw.rect(surface, (50, 38, 12) if can_prev else (25, 22, 15), r_prev, border_radius=4)
            pygame.draw.rect(surface, (140, 108, 28) if can_prev else (55, 48, 28), r_prev, 1, border_radius=4)
            s_prev = f_nav.render("< Prec.", True, (210, 168, 55) if can_prev else (80, 68, 35))
            surface.blit(s_prev, s_prev.get_rect(center=r_prev.center))

            # Page counter
            s_cnt = f_nav.render(f"{self._page_current + 1} / {len(pages)}", True, (175, 138, 55))
            surface.blit(s_cnt, s_cnt.get_rect(center=(self.rect.centerx, cy_nav)))

            # Right button  Next >
            can_next = self._page_current < len(pages) - 1
            r_next = pygame.Rect(self.rect.centerx + 100 - btn_w // 2, cy_nav - btn_h // 2, btn_w, btn_h)
            pygame.draw.rect(surface, (50, 38, 12) if can_next else (25, 22, 15), r_next, border_radius=4)
            pygame.draw.rect(surface, (140, 108, 28) if can_next else (55, 48, 28), r_next, 1, border_radius=4)
            s_next = f_nav.render("Suiv. >", True, (210, 168, 55) if can_next else (80, 68, 35))
            surface.blit(s_next, s_next.get_rect(center=r_next.center))

        # -- Closing hint ----------------------------------------------
        hint = self._font_close.render(
            get_text("lore_hint_close"), True, (95, 72, 22))
        surface.blit(hint, hint.get_rect(
            center=(self.rect.centerx, self.rect.bottom - 14)))


# -- Payment / confirmation popup ------------------------------------------

class PaymentPopup:
    """
    Confirmation popup for paying in souls (stone style).
    """

    WIDTH = 400
    HEIGHT = 210

    def __init__(self, width_screen: int, height_screen: int):
        self.lw   = width_screen
        self.lh   = height_screen
        self.rect = pygame.Rect(
            width_screen  // 2 - self.WIDTH // 2,
            height_screen  // 2 - self.HEIGHT // 2,
            self.WIDTH, self.HEIGHT,
        )
        self.visible   = False
        self.mode      = 'confirm'
        self._callback = None
        self._font     = pygame.font.Font(None, 29)
        self._font_btn = pygame.font.Font(None, 33)
        self._font_sub = pygame.font.Font(None, 24)
        self._time_msg = 0
        self._btn_yes   = pygame.Rect(0, 0, 118, 38)
        self._btn_not   = pygame.Rect(0, 0, 118, 38)

    def open_confirmation(self, player_money: int, callback, cost: int = COST_SOULS):
        self.mode      = 'confirm' if player_money >= cost else 'pauvre'
        self._callback = callback
        self.visible   = True
        self._cost     = cost

    def open_message(self, mode: str):
        self.mode       = mode
        self._callback  = None
        self.visible    = True
        self._time_msg = pygame.time.get_ticks()

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False
        if self._time_msg and pygame.time.get_ticks() - self._time_msg > 2500:
            self.visible = False; self._time_msg = 0
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False; return True
            if event.key == pygame.K_RETURN and self.mode == 'confirm':
                self._confirm(); return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == 'confirm':
                if self._btn_yes.collidepoint(event.pos):
                    self._confirm(); return True
                if self._btn_not.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
                    self.visible = False; return True
            else:
                self.visible = False; return True
        return self.visible

    def _confirm(self):
        if self._callback:
            self._callback()
        self.visible = False

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        # Overlay
        ov = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        surface.blit(ov, (0, 0))

        # Stone popup background
        background = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        for y in range(self.HEIGHT):
            t = y / self.HEIGHT
            r = int(26 + t * 10)
            g = int(22 + t * 8)
            b = int(36 + t * 14)
            pygame.draw.line(background, (r, g, b, 245), (0, y), (self.WIDTH, y))

        color_edge = (200, 50, 50) if self.mode == 'pauvre' else (115, 88, 22)
        pygame.draw.rect(background, color_edge, background.get_rect(), 2, border_radius=8)
        pygame.draw.rect(background, (50, 38, 10), pygame.Rect(5, 5, self.WIDTH - 10, self.HEIGHT - 10),
                         1, border_radius=6)

        # Runic corners
        for cx, cy in [(8, 8), (self.WIDTH - 20, 8)]:
            _draw_rune(background, _RUNES_SHAPES[7], cx, cy, 8, (120, 92, 20))

        surface.blit(background, self.rect.topleft)

        cx = self.rect.centerx
        cy = self.rect.centery

        if self.mode == 'confirm':
            title = getattr(self, '_title_popup', get_text("lore_popup_stele"))
            t1 = self._font.render(title, True, (215, 175, 58))
            surface.blit(t1, t1.get_rect(center=(cx, self.rect.y + 30)))

            msg = getattr(self, '_message_popup', get_text("lore_popup_pay_msg").format(cost=COST_SOULS))
            t2 = self._font.render(msg, True, (200, 188, 150))
            surface.blit(t2, t2.get_rect(center=(cx, cy - 12)))

            t3 = self._font_sub.render(get_text("lore_popup_echo"), True, (130, 110, 70))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 12)))

            btn_y = self.rect.bottom - 54
            self._btn_yes.center = (cx - 68, btn_y)
            self._btn_not.center = (cx + 68, btn_y)
            mx, my = pygame.mouse.get_pos()

            # Pay button
            hover = self._btn_yes.collidepoint(mx, my)
            pygame.draw.rect(surface, (35, 28, 8) if not hover else (60, 48, 12),
                             self._btn_yes, border_radius=5)
            pygame.draw.rect(surface, (140, 108, 28), self._btn_yes, 1, border_radius=5)
            s = self._font_btn.render(get_text("lore_btn_pay"), True, (220, 180, 60))
            surface.blit(s, s.get_rect(center=self._btn_yes.center))

            # Give-up button
            hover2 = self._btn_not.collidepoint(mx, my)
            pygame.draw.rect(surface, (35, 12, 12) if not hover2 else (60, 20, 20),
                             self._btn_not, border_radius=5)
            pygame.draw.rect(surface, (180, 50, 50), self._btn_not, 1, border_radius=5)
            s2 = self._font_btn.render(get_text("lore_btn_give_up"), True, (220, 80, 80))
            surface.blit(s2, s2.get_rect(center=self._btn_not.center))

            hint = self._font_sub.render(get_text("lore_hint_confirm"), True, (80, 65, 30))
            surface.blit(hint, hint.get_rect(center=(cx, self.rect.bottom - 14)))

        elif self.mode == 'pauvre':
            t1 = self._font.render(get_text("lore_poor_title"), True, (220, 80, 80))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 22)))
            t2 = self._font.render(get_text("lore_poor_need").format(cost=self._cost), True, (180, 100, 100))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 2)))
            t3 = self._font_sub.render(get_text("lore_poor_keep_going"), True, (130, 80, 80))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 22)))

        elif self.mode == 'unlocked':
            t1 = self._font.render(get_text("lore_unlocked_title"), True, (220, 178, 58))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 14)))
            t2 = self._font_sub.render(get_text("lore_unlocked_sub"), True, (175, 148, 80))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 10)))



# -- Upgrade shop ----------------------------------------------------------

class UpgradeShopPopup:
    """Three-item shop popup. Keyboard navigation and purchase (1 / 2 / 3)."""

    WIDTH = 500
    HEIGHT = 320

    def __init__(self, width_screen: int, height_screen: int):
        self.lw = width_screen
        self.lh = height_screen
        self.rect = pygame.Rect(
            width_screen  // 2 - self.WIDTH // 2,
            height_screen  // 2 - self.HEIGHT // 2,
            self.WIDTH, self.HEIGHT,
        )
        self.visible       = False
        self._callback     = None
        self._money       = 0
        self._damage_bonus = 0
        self._max_hp_bonus = 0
        self._echo_dir     = False
        self._font_title = pygame.font.Font(None, 32)
        self._font       = pygame.font.Font(None, 27)
        self._font_small = pygame.font.Font(None, 22)

    def open(self, money: int, damage_bonus: int, max_hp_bonus: int,
               echo_dir: bool, callback):
        self.visible       = True
        self._money       = money
        self._damage_bonus = damage_bonus
        self._max_hp_bonus = max_hp_bonus
        self._echo_dir     = echo_dir
        self._callback     = callback

    def close(self):
        self.visible = False

    def _buy(self, item: str):
        ok = False
        if item == 'damage':
            ok = self._damage_bonus < 1 and self._money >= COST_UPGRADE_DAMAGE
        elif item == 'max_hp':
            ok = self._max_hp_bonus < MAX_PURCHASES_HP and self._money >= COST_UPGRADE_HP
        elif item == 'echo_dir':
            ok = not self._echo_dir and self._money >= COST_UPGRADE_ECHO_DIR
        if ok and self._callback:
            self._callback(item)
            self.close()

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close(); return True
            if event.key in (pygame.K_1, pygame.K_KP1):
                self._buy('damage'); return True
            if event.key in (pygame.K_2, pygame.K_KP2):
                self._buy('max_hp'); return True
            if event.key in (pygame.K_3, pygame.K_KP3):
                self._buy('echo_dir'); return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.close(); return True
        return self.visible

    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        # Overlay
        ov = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        surface.blit(ov, (0, 0))

        # Stone background
        background = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        for fy in range(self.HEIGHT):
            t = fy / self.HEIGHT
            r, g, b = int(22 + t * 12), int(18 + t * 10), int(30 + t * 15)
            pygame.draw.line(background, (r, g, b, 248), (0, fy), (self.WIDTH, fy))
        pygame.draw.rect(background, (80, 200, 100), background.get_rect(), 2, border_radius=8)
        pygame.draw.rect(background, (40, 100, 55),
                         pygame.Rect(5, 5, self.WIDTH - 10, self.HEIGHT - 10),
                         1, border_radius=6)
        surface.blit(background, self.rect.topleft)

        cx = self.rect.centerx

        # Title
        title = self._font_title.render(get_text("lore_shop_title"), True, (80, 220, 120))
        surface.blit(title, title.get_rect(center=(cx, self.rect.y + 26)))
        pygame.draw.line(surface, (40, 120, 60),
                         (self.rect.x + 20, self.rect.y + 46),
                         (self.rect.right - 20, self.rect.y + 46))

        def _draw_line(y_base, key_name, label, sub_label, available, bought_txt):
            # Key badge
            badge_rect = pygame.Rect(self.rect.x + 16, y_base, 32, 32)
            badge_col  = (30, 100, 50) if available else (40, 40, 40)
            badge_brd  = (80, 200, 100) if available else (60, 60, 60)
            pygame.draw.rect(surface, badge_col, badge_rect, border_radius=5)
            pygame.draw.rect(surface, badge_brd, badge_rect, 1, border_radius=5)
            tk_s = self._font.render(key_name, True, (80, 220, 120) if available else (70, 70, 70))
            surface.blit(tk_s, tk_s.get_rect(center=badge_rect.center))
            # Text
            col_label = (200, 200, 200) if available else (90, 90, 90)
            col_sub  = (130, 130, 130) if available else (70, 70, 70)
            surface.blit(self._font.render(label, True, col_label),
                         (self.rect.x + 58, y_base + 1))
            surface.blit(self._font_small.render(sub_label, True, col_sub),
                         (self.rect.x + 58, y_base + 22))
            # Status on the right
            col_stat = (120, 120, 120) if not available else (80, 220, 120)
            s_stat = self._font_small.render(bought_txt, True, col_stat)
            surface.blit(s_stat, s_stat.get_rect(midright=(self.rect.right - 16, y_base + 16)))

        # Line 1 - Strike force
        available1 = self._damage_bonus < 1 and self._money >= COST_UPGRADE_DAMAGE
        bought1_txt = (get_text("lore_shop_bought") if self._damage_bonus >= 1
                        else get_text("lore_shop_buy").format(n=1) if available1
                        else get_text("lore_shop_no_funds"))
        _draw_line(self.rect.y + 62, "1",
                        get_text("lore_shop_damage"),
                        get_text("lore_shop_once").format(cost=COST_UPGRADE_DAMAGE),
                        available1, bought1_txt)

        pygame.draw.line(surface, (35, 55, 40),
                         (self.rect.x + 16, self.rect.y + 138),
                         (self.rect.right - 16, self.rect.y + 138))

        # Line 2 - Max HP
        available2 = self._max_hp_bonus < MAX_PURCHASES_HP and self._money >= COST_UPGRADE_HP
        if self._max_hp_bonus >= MAX_PURCHASES_HP:
            bought2_txt = get_text("lore_shop_max")
        elif available2:
            bought2_txt = get_text("lore_shop_buy").format(n=2)
        else:
            bought2_txt = get_text("lore_shop_no_funds")
        _draw_line(self.rect.y + 152, "2",
                        get_text("lore_shop_hp"),
                        get_text("lore_shop_hp_count").format(cost=COST_UPGRADE_HP, n=self._max_hp_bonus, max=MAX_PURCHASES_HP),
                        available2, bought2_txt)

        pygame.draw.line(surface, (35, 55, 40),
                         (self.rect.x + 16, self.rect.y + 228),
                         (self.rect.right - 16, self.rect.y + 228))

        # Line 3 - Directional echo
        available3 = not self._echo_dir and self._money >= COST_UPGRADE_ECHO_DIR
        bought3_txt = (get_text("lore_shop_bought") if self._echo_dir
                        else get_text("lore_shop_buy").format(n=3) if available3
                        else get_text("lore_shop_no_funds"))
        _draw_line(self.rect.y + 242, "3",
                        get_text("lore_shop_echo_dir"),
                        get_text("lore_shop_once").format(cost=COST_UPGRADE_ECHO_DIR),
                        available3, bought3_txt)

        # Closing hint
        hint = self._font_small.render(
            get_text("lore_shop_hint"),
            True, (60, 90, 65))
        surface.blit(hint, hint.get_rect(center=(cx, self.rect.bottom - 12)))


# -- Ability unlocked notification -----------------------------------------

class AbilityNotification:
    """
    Banner shown when an ability is unlocked.
    Style: translucent dark stone, runes, golden text.
    """
    DURATION_MS    = 4500
    FADE_MS    = 600
    WIDTH     = 420
    HEIGHT     = 72

    _ICONS = {
        'dash':        [((-10,0),(10,0)), ((0,-8),(10,0)), ((0,8),(10,0)), ((-14,-5),(-6,0)), ((-14,5),(-6,0))],
        'double_jump': [((-8,8),(0,-8)), ((0,-8),(8,8)), ((-8,-2),(0,-12)), ((0,-12),(8,-2))],
    }

    def __init__(self, width_screen: int, height_screen: int):
        self.lw = width_screen
        self.lh = height_screen
        self._queue   = []   # pending dicts
        self._current  = None
        self._start   = 0
        self._font_title = pygame.font.Font(None, 28)
        self._font_sub   = pygame.font.Font(None, 22)
        self._font_key = pygame.font.Font(None, 24)

    def notify(self, ability: str, key_name: str = ''):
        """Add a notification to the queue."""
        labels = {
            'dash':        (get_text("notif_dash_title"), get_text("notif_dash_sub")),
            'double_jump': (get_text("notif_double_jump_title"), get_text("notif_double_jump_sub")),
            'key_item':         (get_text("notif_key_title"), get_text("notif_key_sub")),
            'echo_dir':    (get_text("notif_echo_dir_title"), get_text("notif_echo_dir_sub")),
        }
        title, sub = labels.get(ability, (get_text("notif_default_title"), ability))
        self._queue.append({
            'ability': ability,
            'title':    title,
            'sub':     sub,
            'key':   key_name.upper(),
        })

    def queue_custom(self, ability, title, sub, key_name=''):
        """Queue a free-form notification (e.g. the end-of-quests reward)."""
        self._queue.append({'ability': ability, 'title': title, 'sub': sub, 'key': key_name})

    def update(self, time_ms: int):
        if self._current is None and self._queue:
            self._current = self._queue.pop(0)
            self._start  = time_ms
        if self._current:
            if time_ms - self._start > self.DURATION_MS:
                self._current = None

    def draw(self, surface: pygame.Surface, time_ms: int):
        if self._current is None:
            return

        elapsed = time_ms - self._start
        # Alpha computation (fade in + fade out)
        if elapsed < self.FADE_MS:
            alpha = int(255 * elapsed / self.FADE_MS)
        elif elapsed > self.DURATION_MS - self.FADE_MS:
            alpha = int(255 * (self.DURATION_MS - elapsed) / self.FADE_MS)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        W, H = self.WIDTH, self.HEIGHT
        # Position: bottom of the screen, centered
        x = self.lw // 2 - W // 2
        y = self.lh - H - 32

        # Dark stone background
        background = pygame.Surface((W, H), pygame.SRCALPHA)
        for fy in range(H):
            t = fy / H
            r = int(18 + t * 10)
            g = int(14 + t * 8)
            b = int(26 + t * 14)
            a = int(210 * alpha / 255)
            pygame.draw.line(background, (r, g, b, a), (0, fy), (W, fy))

        # Golden border
        color_edge = (115, 88, 22, alpha)
        pygame.draw.rect(background, color_edge, pygame.Rect(0, 0, W, H), 2, border_radius=6)
        pygame.draw.rect(background, (75, 57, 12, alpha // 2),
                         pygame.Rect(3, 3, W - 6, H - 6), 1, border_radius=4)

        # Golden line on the left (accent)
        for fy in range(6, H - 6):
            a_line = int(180 * alpha / 255)
            background.set_at((4, fy), (180, 140, 40, a_line))

        # Decorative runes in the corners
        _draw_rune(background, _RUNES_SHAPES[5], 8, 8, 8,
                       (140, 108, 28, int(160 * alpha / 255)))
        _draw_rune(background, _RUNES_SHAPES[2], W - 18, 8, 8,
                       (140, 108, 28, int(160 * alpha / 255)))

        surface.blit(background, (x, y))

        # Ability icon (hand drawn)
        cap = self._current['ability']
        icon_x = x + 28
        icon_y = y + H // 2

        # Icon background circle
        circ = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(circ, (40, 35, 55, int(200 * alpha / 255)), (18, 18), 17)
        pygame.draw.circle(circ, (100, 78, 18, int(180 * alpha / 255)), (18, 18), 17, 2)
        surface.blit(circ, (icon_x - 18, icon_y - 18))

        # Icon segments
        segs = self._ICONS.get(cap, [])
        col_icon = (80, 210, 230) if cap == 'dash' else (180, 130, 255)
        if segs:
            tmp_icon = pygame.Surface((36, 36), pygame.SRCALPHA)
            for (x1, y1), (x2, y2) in segs:
                pygame.draw.line(tmp_icon, (*col_icon, int(220 * alpha / 255)),
                                (18 + x1, 18 + y1), (18 + x2, 18 + y2), 2)
            surface.blit(tmp_icon, (icon_x - 18, icon_y - 18))

        # Text
        tx = x + 56

        # Title
        s_title = self._font_title.render(self._current['title'], True, (220, 178, 58))
        tmp = pygame.Surface(s_title.get_size(), pygame.SRCALPHA)
        tmp.blit(s_title, (0, 0))
        tmp.set_alpha(alpha)
        surface.blit(tmp, (tx, y + 12))

        # Subtitle
        s_sub = self._font_sub.render(self._current['sub'], True, (160, 135, 80))
        tmp2 = pygame.Surface(s_sub.get_size(), pygame.SRCALPHA)
        tmp2.blit(s_sub, (0, 0))
        tmp2.set_alpha(alpha)
        surface.blit(tmp2, (tx, y + 36))

        # Key
        if self._current['key']:
            tk_label = f"[ {self._current['key']} ]"
            s_tk = self._font_key.render(tk_label, True, (80, 210, 230))
            tmp3 = pygame.Surface(s_tk.get_size(), pygame.SRCALPHA)
            tmp3.blit(s_tk, (0, 0))
            tmp3.set_alpha(alpha)
            surface.blit(tmp3, (x + W - s_tk.get_width() - 16, y + H // 2 - s_tk.get_height() // 2))