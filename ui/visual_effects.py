# ui/visual_effects.py
# Drawing helper functions for the Echo interface.
# Extracted from client.py to slim the main file.

import pygame
import math
import numpy as np
from settings import *

# Global cache for the echo distortion: precomputed sinusoidal profile
# Fixed size for every possible radius (up to 500 px)
_DISTORTION_PROFILE_CACHE = None
_DISTORTION_PROFILE_CACHE_SIZE = 512


def _generate_profile_distortion_cache():
    """Generate the global cache of the sinusoidal profile used by the distortion."""
    global _DISTORTION_PROFILE_CACHE
    if _DISTORTION_PROFILE_CACHE is not None:
        return
    half = ECHO_DISTORTION_THICKNESS_PX / 2.0
    thickness = ECHO_DISTORTION_THICKNESS_PX

    # Precompute the profile for every possible distance
    # The profile goes from 0 to pi, which gives a half sine
    profiles = []
    for i in range(_DISTORTION_PROFILE_CACHE_SIZE):
        distance_norm = i / (_DISTORTION_PROFILE_CACHE_SIZE - 1) * 2 - 1  # -1 to 1
        # We want the sinusoidal profile for the impact zone
        # (dist - (radius - half)) / thickness * pi
        # For dist in [radius-half, radius+half]
        value = (distance_norm * half + half) / thickness * np.pi
        profile = np.sin(np.clip(value, 0, np.pi))
        profiles.append(profile)
    _DISTORTION_PROFILE_CACHE = np.array(profiles, dtype=np.float32)


def draw_background_echo(surface, width, height, time_ms):
    """
    Echo-style animated background:
    - dark blue vertical gradient
    - subtle particle grid
    - pulsing central glow
    """
    # 1. Base background with a vertical gradient
    if MENU_BACKGROUND:
        for y in range(height):
            ratio = y / height
            r = int(8  + ratio * 4)
            g = int(8  + ratio * 2)
            b = int(20 + ratio * 15)
            pygame.draw.line(surface, (r, g, b), (0, y), (width, y))
    else:
        surface.fill((0, 0, 0))

    # 2. Perspective grid (thin horizontal lines)
    if MENU_HALOS:
        num_lines = 12
        grid_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        for i in range(num_lines):
            ratio = (i + 1) / num_lines
            y_pos = int(height * 0.55 + ratio * height * 0.6)
            if y_pos >= height:
                break
            alpha = int(12 + ratio * 25)
            thickness = 1 if ratio < 0.6 else 2
            pygame.draw.line(grid_surf, (0, 180, 255, alpha),
                            (0, y_pos), (width, y_pos), thickness)

        # Vertical lines of the grid
        num_v = 20
        for i in range(num_v + 1):
            ratio_x = i / num_v
            x_vanish = width // 2
            y_vanish = int(height * 0.55)
            x_bottom = int(ratio_x * width)
            alpha = int(8 + abs(ratio_x - 0.5) * 20)
            pygame.draw.line(grid_surf, (0, 150, 220, alpha),
                            (x_vanish, y_vanish), (x_bottom, height), 1)
        surface.blit(grid_surf, (0, 0))

    # 3. Pulsing central glow (cyan)
    if MENU_HALOS:
        pulse = 0.75 + 0.25 * math.sin(time_ms / 1200)
        glow_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        cx, cy = width // 2, int(height * 0.38)
        for radius, alpha_base in [(420, 18), (280, 30), (150, 45), (70, 25)]:
            a = int(alpha_base * pulse)
            pygame.draw.circle(glow_surf, (0, 180, 255, a), (cx, cy), radius)
        surface.blit(glow_surf, (0, 0))


def draw_separator_neon(surface, x1, y, x2, color=None, alpha=180):
    """Neon-style separator line with a transparency gradient."""
    if color is None:
        color = COLOR_CYAN
    sep_surf = pygame.Surface((x2 - x1, 2), pygame.SRCALPHA)
    r, g, b = color
    width = x2 - x1
    for px in range(width):
        ratio = px / width
        dist_center = abs(ratio - 0.5) * 2   # 0 at the center, 1 at the edges
        a = int(alpha * (1 - dist_center ** 1.5))
        sep_surf.set_at((px, 0), (r, g, b, a))
        sep_surf.set_at((px, 1), (r, g, b, a // 3))
    surface.blit(sep_surf, (x1, y))


def draw_title_neon(surface, font, text, cx, cy, color_neon=None):
    """Title with a multi-layer neon glow effect."""
    if color_neon is None:
        color_neon = COLOR_CYAN
    r, g, b = color_neon

    # Glow layers (from the largest to the smallest)
    for offset, alpha in [(6, 15), (4, 25), (2, 40)]:
        for dx in (-offset, 0, offset):
            for dy in (-offset, 0, offset):
                if dx == 0 and dy == 0:
                    continue
                glow = font.render(text, True, (r, g, b))
                glow.set_alpha(alpha)
                rect = glow.get_rect(center=(cx + dx, cy + dy))
                surface.blit(glow, rect)

    # Main text
    surf = font.render(text, True, color_neon)
    rect = surf.get_rect(center=(cx, cy))
    surface.blit(surf, rect)


def draw_panel(surface, rect, color_border=None, alpha_background=220):
    """Semi-transparent panel with a neon border and beveled corners."""
    if color_border is None:
        color_border = COLOR_CYAN_DARK

    # Background
    background_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    r_background = (COLOR_PANEL_BACKGROUND[0], COLOR_PANEL_BACKGROUND[1], COLOR_PANEL_BACKGROUND[2], alpha_background)
    pygame.draw.rect(background_surf, r_background,
                    pygame.Rect(0, 0, rect.width, rect.height),
                    border_radius=12)
    surface.blit(background_surf, rect.topleft)

    # Outer border
    pygame.draw.rect(surface, color_border, rect, width=1, border_radius=12)

    # Top highlight (bright line)
    reflection = pygame.Surface((rect.width - 20, 1), pygame.SRCALPHA)
    for px in range(rect.width - 20):
        ratio = px / (rect.width - 20)
        dist = abs(ratio - 0.5) * 2
        a = int(50 * (1 - dist ** 2))
        reflection.set_at((px, 0), (200, 230, 255, a))
    surface.blit(reflection, (rect.x + 10, rect.y + 8))


def apply_distortion_echo(surface, waves, t_now):
    """
    Local "water drop" radial distortion effect on the surface.
    Mutates `surface` in place. The caller manages the lifetime of `waves`
    (filtering out finished waves before the call).

    surface : pygame.Surface - virtual surface (modified in place)
    waves   : list of dicts {start_ms, sx, sy, radius_max, duration_ms}
              with sx/sy already converted to virtual screen coordinates.
    t_now   : pygame.time.get_ticks() - current timestamp in ms.
    """
    if not ECHO_DISTORTION_ENABLED or not waves:
        return

    try:
        import numpy as np
    except ImportError:
        return

    width, height = surface.get_size()
    thickness     = ECHO_DISTORTION_THICKNESS_PX
    amplitude_max = ECHO_DISTORTION_AMPLITUDE_PX
    half          = thickness / 2.0
    pad           = int(half) + amplitude_max + 1

    try:
        pixels = pygame.surfarray.pixels3d(surface)   # mutable view (W, H, 3)
    except (pygame.error, ValueError):
        return

    try:
        for wave in waves:
            t = t_now - wave['start_ms']
            duration = wave['duration_ms']
            if t < 0 or t >= duration:
                continue

            ratio = t / duration
            radius = wave['radius_max'] * ratio
            fade  = 1.0 - ratio
            sx, sy = wave['sx'], wave['sy']

            x0 = max(0, int(sx - radius - pad))
            y0 = max(0, int(sy - radius - pad))
            x1 = min(width, int(sx + radius + pad) + 1)
            y1 = min(height, int(sy + radius + pad) + 1)
            if x1 <= x0 or y1 <= y0:
                continue

            src_snap = pixels[x0:x1, y0:y1].copy()

            xx, yy = np.mgrid[x0:x1, y0:y1].astype(np.float32)
            dx = xx - sx
            dy = yy - sy
            dist = np.sqrt(dx * dx + dy * dy)

            mask = np.abs(dist - radius) < half
            if not mask.any():
                continue

            profile = np.sin(np.clip((dist - (radius - half)) / thickness * np.pi, 0, np.pi))
            amp = profile * amplitude_max * fade

            mag = np.maximum(dist, 1e-3)
            ux = dx / mag
            uy = dy / mag

            src_x_rel = np.clip((xx - x0 + ux * amp).astype(np.int32), 0, x1 - x0 - 1)
            src_y_rel = np.clip((yy - y0 + uy * amp).astype(np.int32), 0, y1 - y0 - 1)

            ix, iy = np.where(mask)
            pixels[x0 + ix, y0 + iy] = src_snap[src_x_rel[ix, iy], src_y_rel[ix, iy]]
    finally:
        del pixels   # release the pixels3d lock
