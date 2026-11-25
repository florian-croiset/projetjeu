# ui/camera.py
# Camera management (offset, zoom) and the precomputed halo mask.
# Extracted from client.py to separate responsibilities.

import pygame
from settings import *


def compute_camera(rect_target, width_screen, height_screen, zoom,
                    width_world, height_world):
    """Compute the camera offset centered on target_rect."""
    view_width = width_screen / zoom
    view_height = height_screen / zoom
    offset_x = rect_target.centerx - (view_width / 2)
    offset_y = rect_target.centery - (view_height / 2)
    offset_x = max(0, offset_x)
    offset_y = max(0, offset_y)
    offset_x = min(offset_x, width_world - view_width)
    offset_y = min(offset_y, height_world - view_height)
    return int(offset_x), int(offset_y)


def create_mask_halo(radius, extent, alpha_max=220):
    """
    Precompute a circular surface with a linear darkness gradient.
    To be blitted with BLEND_RGBA_MIN on the darkness layer every frame.

    radius    : total radius of the halo (pixels)
    extent    : width of the gradient zone from the edge towards the center
                (extent == radius -> gradient over the whole radius, transparent center)
    alpha_max : maximum darkness level (0-255)
    """
    diameter = radius * 2 + 2
    center   = radius + 1
    surf     = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    start   = max(0, radius - int(extent))   # start of the gradient from the center

    if HALO_LEVEL_COUNT == 0:
        # Perfect pixel-by-pixel gradient with numpy
        try:
            import numpy as np
            x_idx, y_idx = np.ogrid[:diameter, :diameter]
            dist  = np.sqrt((x_idx - center) ** 2 + (y_idx - center) ** 2)
            alpha = np.clip(
                (dist - start) / max(1, extent) * alpha_max,
                0, alpha_max
            ).astype(np.uint8)

            arr_a        = pygame.surfarray.pixels_alpha(surf)
            arr_a[:]     = alpha
            del arr_a

            arr_rgb      = pygame.surfarray.pixels3d(surf)
            arr_rgb[:, :] = (0, 0, 10)
            del arr_rgb

            return surf
        except (ImportError, pygame.error):
            print("[HALO] numpy unavailable - falling back to discrete layers")

    # Fallback or discrete mode (HALO_LEVEL_COUNT > 0)
    num = HALO_LEVEL_COUNT if HALO_LEVEL_COUNT > 0 else max(32, radius)
    surf.fill((0, 0, 10, alpha_max))             # everything dark by default
    for i in range(num, -1, -1):                  # from the largest circle to the smallest
        r = start + int(extent * i / num)
        a = int(alpha_max * i / num)
        pygame.draw.circle(surf, (0, 0, 10, a), (center, center), r)

    return surf
