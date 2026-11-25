# utils/cache.py
# Centralised caches and precomputations used to optimise the game.
#
# Contents:
# +- pygame caches ----------------------------------------------------+
# |  flip_h(surface)               -> horizontally flipped surface      |
# |  render_text(font, txt, color) -> memoised font.render()            |
# |  get_font_default(size_px)     -> pygame.font.Font(None, size)      |
# |  get_font_nickname(size_px)    -> alias of get_font_default         |
# |  create_texts_echo_hud(fonts)  -> static surfaces of the Echo widget|
# |  label_bg(w, h, alpha=120)     -> semi-transparent background       |
# +--------------------------------------------------------------------+
# +- Precomputed constants --------------------------------------------+
# |  DIRECTIONS_ECHO_RADIAL        -> radial ray vectors                |
# |  DIRECTIONS_ECHO_RIGHT/LEFT    -> directional cone vectors          |
# |  TRACKER_HEARING_RADIUS_SQ     -> squared radius for fast compares  |
# +--------------------------------------------------------------------+

import math
import pygame

from utils.i18n import get_text

from settings import (
    COLOR_CYAN,
    ECHO_DIR_HALF_ANGLE,
    ECHO_RAY_COUNT,
    TRACKER_HEARING_RADIUS,
)


# ======================================================================
# CACHE - HORIZONTALLY FLIPPED SURFACES
# ======================================================================
# Key: id(source_surface). As long as the source surface stays referenced
# elsewhere (by the animator), the id() will not be reused.
# If the cache ever grows too large, it is purged entirely.

_FLIP_H_CACHE: dict = {}
_FLIP_H_MAX = 512


def flip_h(surface: pygame.Surface) -> pygame.Surface:
    """Return the horizontally flipped version of `surface`, memoised."""
    key = id(surface)
    cached = _FLIP_H_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_FLIP_H_CACHE) >= _FLIP_H_MAX:
        _FLIP_H_CACHE.clear()
    flipped = pygame.transform.flip(surface, True, False)
    _FLIP_H_CACHE[key] = flipped
    return flipped


# ======================================================================
# CACHE - TEXT RENDERS
# ======================================================================
# Key: (id(font), text, color). Avoids font.render() for static texts
# re-rendered on every frame (HUD, menu labels).

_TEXT_CACHE: dict = {}
_TEXT_CACHE_MAX = 256


def render_text(font: pygame.font.Font, text: str, color) -> pygame.Surface:
    """Memoised font.render. Use it for repeated static texts."""
    color_key = tuple(color) if not isinstance(color, tuple) else color
    key = (id(font), text, color_key)
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_TEXT_CACHE) >= _TEXT_CACHE_MAX:
        _TEXT_CACHE.clear()
    surf = font.render(text, True, color)
    _TEXT_CACHE[key] = surf
    return surf


# ======================================================================
# CACHE - DEFAULT PYGAME FONT (by pixel size)
# ======================================================================
# Used by the player nicknames AND by every renderer that used to call
# `pygame.font.Font(None, size)` on every frame (orbs, doors, etc.).
# Building a Pygame font is slow - the instance is shared by all callers
# that use the same size.

_FONT_DEFAULT_CACHE: dict = {}


def get_font_default(size_px: int) -> pygame.font.Font:
    """Return `pygame.font.Font(None, size_px)` memoised by size."""
    font = _FONT_DEFAULT_CACHE.get(size_px)
    if font is None:
        font = pygame.font.Font(None, size_px)
        _FONT_DEFAULT_CACHE[size_px] = font
    return font


# Alias kept for compatibility: the player nickname historically used
# a dedicated cache.
get_font_nickname = get_font_default


# ======================================================================
# CACHE - SEMI-TRANSPARENT BACKGROUND SURFACES ("label bg")
# ======================================================================
# Small SRCALPHA rectangle filled with one uniform color - used as the
# background of floating labels (orb, nickname, etc.).
# The key includes the size AND the alpha (the fill color is always
# black, which is the real case used everywhere in the game).

_LABEL_BG_CACHE: dict = {}
_LABEL_BG_MAX = 128


def label_bg(width: int, height: int, alpha: int = 120) -> pygame.Surface:
    """Black SRCALPHA surface (`(0,0,0,alpha)`) memoised by dimensions.

    Reusable for label backgrounds - the same instance is returned on every
    call, do not modify it.
    """
    key = (width, height, alpha)
    cached = _LABEL_BG_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_LABEL_BG_CACHE) >= _LABEL_BG_MAX:
        _LABEL_BG_CACHE.clear()
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    surf.fill((0, 0, 0, alpha))
    _LABEL_BG_CACHE[key] = surf
    return surf


# ======================================================================
# CACHE - STATIC SURFACES OF THE ECHO WIDGET (HUD)
# ======================================================================
# The "ECHO" and "READY" labels and the "E" icon (cyan + grayed) are
# pre-rendered once when the HUD is initialised (and on every
# resolution change since the fonts change).

def create_texts_echo_hud(font_label_small: pygame.font.Font,
                          font_label_medium: pygame.font.Font,
                          font_echo_icon: pygame.font.Font) -> dict:
    """Return a dict with the static surfaces of the Echo widget.

    Keys of the returned dict:
    - 'echo_label' : "ECHO" (small, gray)
    - 'echo_ready' : "READY" (medium, cyan)

    The key icons (e_ready / e_waiting) are rendered dynamically through
    render_text() in the HUD to reflect the key bindings.
    """
    return {
        'echo_label': font_label_small.render("ECHO", True, (100, 85, 130)),
        'echo_ready':  font_label_medium.render(get_text("hud_ready"), True, COLOR_CYAN),
    }


# ======================================================================
# CONSTANTS - ECHO DIRECTION VECTORS
# ======================================================================
# Precomputed once when the module is loaded; shared by
# every GameMap instance.

DIRECTIONS_ECHO_RADIAL = tuple(
    (math.cos(i / ECHO_RAY_COUNT * 2 * math.pi),
     math.sin(i / ECHO_RAY_COUNT * 2 * math.pi))
    for i in range(ECHO_RAY_COUNT)
)

_HALF_RAD_ECHO = ECHO_DIR_HALF_ANGLE * math.pi / 180

DIRECTIONS_ECHO_RIGHT = tuple(
    (math.cos(-_HALF_RAD_ECHO + i / (ECHO_RAY_COUNT - 1) * 2 * _HALF_RAD_ECHO),
     math.sin(-_HALF_RAD_ECHO + i / (ECHO_RAY_COUNT - 1) * 2 * _HALF_RAD_ECHO))
    for i in range(ECHO_RAY_COUNT)
)

DIRECTIONS_ECHO_LEFT = tuple(
    (math.cos(math.pi - _HALF_RAD_ECHO + i / (ECHO_RAY_COUNT - 1) * 2 * _HALF_RAD_ECHO),
     math.sin(math.pi - _HALF_RAD_ECHO + i / (ECHO_RAY_COUNT - 1) * 2 * _HALF_RAD_ECHO))
    for i in range(ECHO_RAY_COUNT)
)


# ======================================================================
# CONSTANTS - SQUARED DISTANCES (to avoid math.sqrt)
# ======================================================================

TRACKER_HEARING_RADIUS_SQ = TRACKER_HEARING_RADIUS * TRACKER_HEARING_RADIUS


# ======================================================================
# UTILITY - PURGE
# ======================================================================

def clear_caches() -> None:
    """Purge every dynamic cache (call it if the fonts are recreated)."""
    _FLIP_H_CACHE.clear()
    _TEXT_CACHE.clear()
    _FONT_DEFAULT_CACHE.clear()
    _LABEL_BG_CACHE.clear()
