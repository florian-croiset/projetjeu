# ui/quest.py
# Journal icon (top left, replaces the HUD widget) + quest journal.

import pygame
import math
import random

from utils.i18n import get_text


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

STEPS = [
    {"id": "enemies"},
    {"id": "souls"},
    {"id": "key_item"},
    {"id": "door"},
]


def _step_text(step):
    return get_text(f"quest_{step['id']}_text")


def _step_detail(step):
    return get_text(f"quest_{step['id']}_detail")

# --- HUD palette ---
_CYAN  = (0,   220, 255)
_VERT  = (80,  240, 120)
_GRAY  = (80,   70, 110)
_WHITE = (210, 200, 255)
_BACKGROUND  = (6,    4,  18)

# --- Parchment palette ---
_PC_BASE  = (222, 203, 158)   # warm cream
_PC_EDGE  = (170, 145, 100)   # darker edge
_PC_LIGHT = (240, 226, 188)   # slight highlight
_INK      = ( 52,  30,  10)   # dark brown ink
_INK_FADE = (110,  85,  50)   # secondary ink
_INK_DONE = ( 55, 100,  45)   # green ink (done)
_INK_GREY = (145, 120,  75)   # gray ink (inactive)
_INK_RED  = (130,  40,  25)   # red ink (accent)


def _formatter_key_journal(key_name):
    if not key_name:
        return "I"
    text = str(key_name)
    if text.startswith("mouse_"):
        return "M" + text.split("_", 1)[1]
    alias = {
        "space": "ESPACE",
        "return": "ENTREE",
        "escape": "ECHAP",
        "left shift": "LSHIFT",
        "right shift": "RSHIFT",
    }
    return alias.get(text.lower(), text).upper()


# ---------------------------------------------------------------------------
# Parchment helpers
# ---------------------------------------------------------------------------

def _edges_torn(surf: pygame.Surface, seed: int = 7):
    """Irregular torn edges - transparent cut-out only."""
    rng  = random.Random(seed)
    w, h = surf.get_size()
    T    = (0, 0, 0, 0)
    step  = 10
    profile = 6

    def teeth_h(y0, outer_y):
        pts = [(-2, outer_y)]
        xi  = 0
        while xi <= w + step:
            dy = rng.randint(0, profile)
            pts.append((xi, y0 + dy * (1 if outer_y < y0 else -1)))
            xi += step + rng.randint(-2, 3)
        pts.append((w + 2, outer_y))
        return pts

    def teeth_v(x0, outer_x):
        pts = [(outer_x, -2)]
        yi  = 0
        while yi <= h + step:
            dx = rng.randint(0, profile)
            pts.append((x0 + dx * (1 if outer_x < x0 else -1), yi))
            yi += step + rng.randint(-2, 3)
        pts.append((outer_x, h + 2))
        return pts

    pygame.draw.polygon(surf, T, teeth_h(0,   -2)   + [(-2, -2)])
    pygame.draw.polygon(surf, T, teeth_h(h,  h+2)   + [(-2, h+2)])
    pygame.draw.polygon(surf, T, teeth_v(0,   -2)   + [(-2, h+2), (-2, -2)])
    pygame.draw.polygon(surf, T, teeth_v(w,  w+2)   + [(w+2, h+2), (w+2, -2)])


def _background_parchment(surf: pygame.Surface):
    """Parchment background: edge gradient, no BLEND nor intensive set_at."""
    w, h = surf.get_size()
    surf.fill(_PC_BASE)

    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    profile  = min(55, w // 7)
    for i in range(profile):
        a = int(100 * (1 - i / profile) ** 1.6)
        col = (*_PC_EDGE, a)
        pygame.draw.line(shadow, col, (i,     0), (i,     h))
        pygame.draw.line(shadow, col, (w-1-i, 0), (w-1-i, h))
    profile2 = min(45, h // 7)
    for i in range(profile2):
        a = int(85 * (1 - i / profile2) ** 1.6)
        col = (*_PC_EDGE, a)
        pygame.draw.line(shadow, col, (0, i),     (w, i))
        pygame.draw.line(shadow, col, (0, h-1-i), (w, h-1-i))
    surf.blit(shadow, (0, 0))

    hl = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(min(80, w // 5)):
        a = int(28 * (1 - i / (w // 5)))
        pygame.draw.line(hl, (*_PC_LIGHT, a), (i, 0), (0, i))
    surf.blit(hl, (0, 0))

    rng = random.Random(99)
    num  = (w * h) // 120
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(num):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        a = rng.randint(8, 28)
        tmp.set_at((x, y), (90, 65, 30, a))
    surf.blit(tmp, (0, 0))

    rng2 = random.Random(42)
    for _ in range(rng2.randint(4, 7)):
        tx = rng2.randint(30, w - 30)
        ty = rng2.randint(30, h - 30)
        tr = rng2.randint(8, 22)
        ta = rng2.randint(18, 42)
        ts = pygame.Surface((tr * 2, tr * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ts, (*_PC_EDGE, ta), ts.get_rect())
        surf.blit(ts, (tx - tr, ty - tr))


def _line_ink(surf, x1, y1, x2, y2, col=None, ep=1):
    col = col or _INK_FADE
    pygame.draw.line(surf, col, (x1, y1), (x2, y2), ep)


def _ornament(surf, cx, y, width, col):
    """Small centered decorative line with a diamond in the middle."""
    aw = width // 2 - 10
    _line_ink(surf, cx - aw, y, cx - 8, y, col, 1)
    _line_ink(surf, cx + 8,  y, cx + aw, y, col, 1)
    pygame.draw.polygon(surf, col, [
        (cx, y - 4), (cx + 5, y), (cx, y + 4), (cx - 5, y)
    ])


# ---------------------------------------------------------------------------
# Journal icon (replaces the HUD widget)
# ---------------------------------------------------------------------------

def _draw_icon_journal(surf: pygame.Surface, x: int, y: int,
                             font_label: pygame.font.Font,
                             font_hint: pygame.font.Font,
                             ticks: int,
                             num_complete: int, num_total: int,
                             key_journal="i"):
    W, H = 32, 36
    cx   = x + W // 2

    pulse = 0.6 + 0.4 * math.sin(ticks / 600)
    edge_alpha = int(180 * pulse) if num_complete < num_total else 220

    pages_col  = (210, 192, 148)
    cover_col  = (90,  60,  30)
    spine_col  = (65,  42,  18)
    line_col   = (160, 138, 95)

    pygame.draw.rect(surf, cover_col,  pygame.Rect(x + 4, y + 1, W - 4, H - 1), border_radius=3)
    pygame.draw.rect(surf, spine_col,  pygame.Rect(x, y + 1, 6, H - 1), border_radius=2)
    pygame.draw.rect(surf, pages_col,  pygame.Rect(x + 6, y + 3, W - 10, H - 5), border_radius=1)

    for i in range(3):
        ly = y + 9 + i * 7
        pygame.draw.line(surf, line_col, (x + 9, ly), (x + W - 7, ly), 1)

    if num_complete == num_total:
        edge_col = (*_VERT,  edge_alpha)
    elif num_complete > 0:
        edge_col = (*_CYAN,  edge_alpha)
    else:
        edge_col = (160, 130, 80, edge_alpha)

    edge_surf = pygame.Surface((W + 2, H + 2), pygame.SRCALPHA)
    pygame.draw.rect(edge_surf, edge_col,
                     edge_surf.get_rect(), width=1, border_radius=3)
    surf.blit(edge_surf, (x - 1, y))

    f_count = pygame.font.Font(None, max(14, font_hint.get_height() - 2))
    count_s = f_count.render(f"{num_complete}/{num_total}", True, pages_col)
    surf.blit(count_s, (x + W // 2 - count_s.get_width() // 2 + 2,
                        y + H - count_s.get_height() - 3))

    y_after_book = y + H + 4

    f_quests = pygame.font.Font(None, max(13, font_hint.get_height()))
    label_s = f_quests.render(get_text("quest_label"), True, (140, 190, 210))
    surf.blit(label_s, (cx - label_s.get_width() // 2, y_after_book))
    y_after_book += label_s.get_height() + 2

    hint_alpha = int(160 + 95 * math.sin(ticks / 400))
    hint_col   = (max(0, min(255, hint_alpha)),) * 3
    hint_s = font_hint.render(f"[{_formatter_key_journal(key_journal)}]", True, hint_col)
    surf.blit(hint_s, (cx - hint_s.get_width() // 2, y_after_book))
    y_after_book += hint_s.get_height()

    return y_after_book - y


class IconJournal:
    """
    Replaces QuestWidget: shows only a small journal icon with the label
    'QUESTS' and the configured key to indicate how to open it.
    """

    def __init__(self, font_label: pygame.font.Font, font_hint: pygame.font.Font):
        self.font_label = font_label
        self.font_hint  = font_hint
        self._state        = {e["id"]: False for e in STEPS}
        self._ticks       = 0
        self._door_view   = False
        self.key_journal = "i"

    def update(self, key_item, door, boss, enemies_killed=0, souls=0):
        self._ticks = pygame.time.get_ticks()

        def _note(eid, done):
            new = bool(done)
            if new != self._state.get(eid):
                self._state[eid] = new

        _note("enemies", enemies_killed >= 5)
        _note("souls",    souls >= 50)
        _note("key_item",     bool(key_item and getattr(key_item, 'is_picked_up', False)))

        if door and (getattr(door, 'opening', False) or
                      getattr(door, 'open',      False)):
            self._door_view = True
        _note("door", self._door_view)

    def draw(self, screen: pygame.Surface, y_offset: int, key_journal=None, x_offset: int = 30):
        if key_journal is not None:
            self.key_journal = key_journal
        num_total     = len(STEPS)
        num_complete = sum(1 for e in STEPS if self._state.get(e["id"]) is True)

        surf_w = 80
        surf_h = 80
        surf   = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

        height = _draw_icon_journal(
            surf, x=8, y=0,
            font_label=self.font_label,
            font_hint=self.font_hint,
            ticks=self._ticks,
            num_complete=num_complete,
            num_total=num_total,
            key_journal=self.key_journal,
        )

        screen.blit(surf, (x_offset, y_offset))
        return height


# Alias for backward compatibility
QuestWidget = IconJournal


# ---------------------------------------------------------------------------
# Quest journal - parchment
# ---------------------------------------------------------------------------

class QuestJournal:
    _FADE_MS = 200

    def __init__(self, width_screen, height_screen,
                 font_title, font_text, font_small):
        self.width = width_screen
        self.top = height_screen
        h = height_screen
        self._p_title  = pygame.font.Font(None, max(48, h // 17))
        self._p_sub   = pygame.font.Font(None, max(26, h // 38))
        self._p_step  = pygame.font.Font(None, max(32, h // 26))
        self._p_detail = pygame.font.Font(None, max(24, h // 40))
        self._p_hint   = pygame.font.Font(None, max(20, h // 48))

        self.is_open     = False
        self._alpha     = 0
        self._open_ms = 0
        self._closed_ms  = 0

        self._state          = {e["id"]: False for e in STEPS}
        self._completion_ms = {}
        self._ticks         = 0
        self._door_view     = False
        self.key_journal = "i"

        # Progress counters (shown in the journal)
        self._enemies_killed = 0
        self._souls_total   = 0

        self._pw = min(660, int(width_screen * 0.58))
        self._ph = min(560, int(height_screen * 0.72))
        self._px = (width_screen  - self._pw) // 2
        self._py = (height_screen  - self._ph) // 2

        self._surf_parchment  = None
        self._surf_content = None
        self._state_hash    = -1
        self._build_parchment()

    # --- toggle ---

    def toggle(self):
        self.is_open = not self.is_open
        now = pygame.time.get_ticks()
        if self.is_open: self._open_ms = now
        else:           self._closed_ms  = now

    # --- state ---

    def update(self, key_item, door, boss, enemies_killed=0, souls=0):
        self._ticks = pygame.time.get_ticks()
        now = self._ticks

        # Remember the counters for display
        if enemies_killed != self._enemies_killed or souls != self._souls_total:
            self._enemies_killed = enemies_killed
            self._souls_total   = souls
            self._state_hash    = -1

        def _note(eid, done):
            old = self._state.get(eid)
            new = bool(done)
            if new != old:
                if done: self._completion_ms[eid] = now
                self._state[eid] = new
                self._state_hash = -1

        _note("enemies", enemies_killed >= 5)
        _note("souls",    souls >= 50)
        _note("key_item",     bool(key_item and getattr(key_item, 'is_picked_up', False)))

        if door and (getattr(door, 'opening', False) or
                      getattr(door, 'open',      False)):
            self._door_view = True
        _note("door", self._door_view)

        if self.is_open:
            el = now - self._open_ms
            self._alpha = min(255, int(255 * el / self._FADE_MS))
        else:
            el = now - self._closed_ms
            self._alpha = max(0,   int(255 * (1 - el / self._FADE_MS)))

    # --- rendering ---

    def draw(self, screen, key_journal=None):
        if key_journal is not None and key_journal != self.key_journal:
            self.key_journal = key_journal
            self._state_hash = -1
        if self._alpha <= 0:
            return

        ov = pygame.Surface((self.width, self.top), pygame.SRCALPHA)
        ov.fill((0, 0, 0, int(self._alpha * 0.60)))
        screen.blit(ov, (0, 0))

        px, py = self._px, self._py

        sh = pygame.Surface((self._pw + 20, self._ph + 20), pygame.SRCALPHA)
        sh.fill((0, 0, 0, int(self._alpha * 0.45)))
        screen.blit(sh, (px - 6, py + 10))

        tmp = self._surf_parchment.copy()
        tmp.set_alpha(self._alpha)
        screen.blit(tmp, (px, py))

        hsh = hash((
            tuple(self._state.get(e["id"]) for e in STEPS),
            self._enemies_killed,
            self._souls_total,
        ))
        if hsh != self._state_hash or self._surf_content is None:
            self._surf_content = self._build_content()
            self._state_hash    = hsh
        ct = self._surf_content.copy()
        ct.set_alpha(self._alpha)
        screen.blit(ct, (px, py))

    # --- parchment construction (static) ---

    def _build_parchment(self):
        pw, ph = self._pw, self._ph
        surf   = pygame.Surface((pw, ph), pygame.SRCALPHA)
        _background_parchment(surf)
        _edges_torn(surf, seed=7)
        self._surf_parchment = surf

    # --- content construction (dynamic) ---

    def _build_content(self):
        pw, ph = self._pw, self._ph
        surf   = pygame.Surface((pw, ph), pygame.SRCALPHA)
        padx   = max(32, pw // 11)
        pady   = max(22, ph // 16)
        cx     = pw // 2
        y      = pady

        # -- Title --
        t_s = self._p_title.render(get_text("quest_title"), True, _INK)
        surf.blit(t_s, t_s.get_rect(centerx=cx, top=y))
        y += t_s.get_height() + 3

        sub_s = self._p_sub.render(get_text("quest_sub"), True, _INK_FADE)
        surf.blit(sub_s, sub_s.get_rect(centerx=cx, top=y))
        y += sub_s.get_height() + 10

        _ornament(surf, cx, y + 5, pw - padx * 2, _INK_FADE)
        y += 18

        # -- Steps --
        lh_e  = self._p_step.get_height()
        lh_d  = self._p_detail.get_height()
        gap   = max(18, ph // 26)

        for i, step in enumerate(STEPS):
            state  = self._state.get(step["id"])
            active = all(self._state.get(e["id"]) is True
                        for e in STEPS[:i])

            # Subtle background for the active step
            if active and state is False:
                block_h = lh_e + 8 + lh_d * len(_step_detail(step)) + gap
                background   = pygame.Surface((pw - padx * 2, block_h + 6), pygame.SRCALPHA)
                background.fill((*_PC_EDGE, 35))
                pygame.draw.rect(background, (*_INK, 40), background.get_rect(), 1, border_radius=3)
                surf.blit(background, (padx - 4, y - 4))

            # Icon + step text
            if state is True:
                ic_txt = "✓"; c_ic = _INK_DONE; c_et = _INK_DONE
            elif active:
                ic_txt = "▶"; c_ic = _INK;      c_et = _INK
            else:
                ic_txt = "○"; c_ic = _INK_GREY; c_et = _INK_GREY

            # Step text with a progressive counter for enemies/souls
            text_step = _step_text(step)
            if step["id"] == "enemies" and state is False:
                text_step = get_text("quest_enemies_progress").format(n=min(self._enemies_killed, 5))
            elif step["id"] == "souls" and state is False:
                text_step = get_text("quest_souls_progress").format(n=min(self._souls_total, 50))

            ic_s  = self._p_step.render(ic_txt, True, c_ic)
            et_s  = self._p_step.render(text_step, True, c_et)
            line_w = ic_s.get_width() + 8 + et_s.get_width()
            x_start = cx - line_w // 2
            tx      = x_start + ic_s.get_width() + 8
            surf.blit(ic_s, (x_start, y))
            surf.blit(et_s, (tx, y))

            if state is True:
                my = y + lh_e // 2
                pygame.draw.line(surf, _INK_DONE, (tx, my), (tx + et_s.get_width(), my), 1)

            y += lh_e + 8

            # Detail
            c_det = _INK_FADE if active else _INK_GREY
            for line in _step_detail(step):
                d_s = self._p_detail.render(line, True, c_det)
                surf.blit(d_s, d_s.get_rect(centerx=cx, top=y))
                y += lh_d + 3
            y += gap

            # Separator
            if i < len(STEPS) - 1:
                sep_x1 = padx + 20
                sep_x2 = pw - padx - 20
                sep_y  = y - gap // 2
                for xi in range(sep_x1, sep_x2):
                    t = (xi - sep_x1) / max(sep_x2 - sep_x1 - 1, 1)
                    fade = math.sin(t * math.pi)
                    a = max(0, int(fade * 80))
                    surf.set_at((xi, sep_y), (*_INK_GREY, a))

        # -- Bottom hint --
        key_name = _formatter_key_journal(self.key_journal)
        hint = self._p_hint.render(f"[ {key_name} ]  Fermer le journal", True, _INK_GREY)
        surf.blit(hint, hint.get_rect(centerx=cx, bottom=ph - pady // 2))

        return surf
