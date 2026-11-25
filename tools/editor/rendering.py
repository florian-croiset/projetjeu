# rendering.py
# Pure map rendering functions (image layers, tiles, grid, cursor)
# with a camera (cam_x, cam_y) in world pixels and a zoom factor.

import pygame
from settings import COLOR_CYAN


# Cache of resized tiles: (id(surface), quantised_zoom) -> Surface
_cache_tiles_zoomed = {}
# Cache of resized + dimmed tiles (for inactive layers):
# (id(surface), quantised_zoom, alpha) -> Surface
_cache_tiles_dimmed = {}
# Cache of resized image layers: (id(image), quantised_zoom) -> Surface
_cache_images_zoomed = {}


def _zoom_quantized(zoom):
    """Quantise the zoom to the hundredth to limit the cache size."""
    return round(zoom * 100) / 100.0


def _surface_zoomed(surface_original, zoom, size_tile):
    """Return the resized version of a tile at the given zoom, with cache."""
    key_item = (id(surface_original), _zoom_quantized(zoom))
    surf = _cache_tiles_zoomed.get(key_item)
    if surf is None:
        size = max(1, int(round(size_tile * zoom)))
        surf = pygame.transform.scale(surface_original, (size, size))
        _cache_tiles_zoomed[key_item] = surf
    return surf


def _surface_zoomed_dimmed(surface_original, zoom, size_tile, alpha=110):
    """Variant of _surface_zoomed whose alpha is applied once and cached:
    avoids a copy()+set_alpha per tile per frame for the inactive layers.
    """
    key_item = (id(surface_original), _zoom_quantized(zoom), alpha)
    surf = _cache_tiles_dimmed.get(key_item)
    if surf is None:
        base = _surface_zoomed(surface_original, zoom, size_tile)
        surf = base.copy()
        surf.set_alpha(alpha)
        _cache_tiles_dimmed[key_item] = surf
    return surf


def _image_zoomed(image_original, zoom):
    """Return the resized version of a parallax image layer (full-screen PNG),
    with cache. Avoids re-scaling on every frame when the zoom is constant.
    """
    key_item = (id(image_original), _zoom_quantized(zoom))
    img = _cache_images_zoomed.get(key_item)
    if img is None:
        w = max(1, int(image_original.get_width() * zoom))
        h = max(1, int(image_original.get_height() * zoom))
        img = pygame.transform.scale(image_original, (w, h))
        _cache_images_zoomed[key_item] = img
    return img


def clear_cache_zoom():
    """Call when the zoom changes a lot to free memory."""
    _cache_tiles_zoomed.clear()
    _cache_tiles_dimmed.clear()
    _cache_images_zoomed.clear()


def world_to_screen(x_world, y_world, cam_x, cam_y, zoom):
    """Convert world coordinates into screen coordinates."""
    return ((x_world - cam_x) * zoom, (y_world - cam_y) * zoom)


def screen_to_case(x_screen, y_screen, cam_x, cam_y, zoom, size_tile):
    """Convert a screen position into a tile coordinate (tx, ty). May be out of bounds."""
    if zoom <= 0:
        return (0, 0)
    tx = int((x_screen / zoom + cam_x) // size_tile)
    ty = int((y_screen / zoom + cam_y) // size_tile)
    return (tx, ty)


def draw_image_layers(surface, image_layers, cam_x, cam_y, zoom, viewport_rect):
    """Draw the image layers (parallax PNGs) according to the camera and the zoom."""
    surface.set_clip(viewport_rect)
    for il in image_layers:
        img = il['surface']
        x = (il['offset_x'] - cam_x) * zoom + viewport_rect.x
        y = (il['offset_y'] - cam_y) * zoom + viewport_rect.y
        if zoom != 1.0:
            img = _image_zoomed(img, zoom)
        surface.blit(img, (x, y))
    surface.set_clip(None)


def draw_tile_layers(surface, layers, cache_tiles, cam_x, cam_y, zoom,
                         size_tile, width_map, height_map, viewport_rect,
                         layer_active=None):
    """Draw every tile layer with culling. The active layer is rendered normally;
    the others are semi-transparent to highlight the one being edited.
    """
    surface.set_clip(viewport_rect)

    max(1, int(round(size_tile * zoom)))

    # Culling: only draw the tiles visible in the viewport
    case_x_min = max(0, int(cam_x // size_tile))
    case_y_min = max(0, int(cam_y // size_tile))
    case_x_max = min(width_map, int((cam_x + viewport_rect.width / zoom) // size_tile) + 1)
    case_y_max = min(height_map, int((cam_y + viewport_rect.height / zoom) // size_tile) + 1)

    for index_layer, layer in enumerate(layers):
        gids = layer['gids']
        layer_active = (layer_active is None or index_layer == layer_active)
        for ty in range(case_y_min, case_y_max):
            line = gids[ty]
            for tx in range(case_x_min, case_x_max):
                gid = line[tx]
                if gid <= 0:
                    continue
                surf = cache_tiles.get(gid)
                if surf is None:
                    continue
                if layer_active:
                    surf_z = _surface_zoomed(surf, zoom, size_tile)
                else:
                    surf_z = _surface_zoomed_dimmed(surf, zoom, size_tile)
                px = (tx * size_tile - cam_x) * zoom + viewport_rect.x
                py = (ty * size_tile - cam_y) * zoom + viewport_rect.y
                surface.blit(surf_z, (px, py))

    surface.set_clip(None)


def draw_grid(surface, cam_x, cam_y, zoom, size_tile,
                    width_map, height_map, viewport_rect):
    """Draw the tile grid (thin lines) on the viewport."""
    if zoom < 0.4:
        return  # grid unreadable when zoomed out too far

    surface.set_clip(viewport_rect)
    color = (60, 70, 95)

    # Compute the visible bounds
    x_min = max(0, int(cam_x // size_tile))
    y_min = max(0, int(cam_y // size_tile))
    x_max = min(width_map, int((cam_x + viewport_rect.width / zoom) // size_tile) + 1)
    y_max = min(height_map, int((cam_y + viewport_rect.height / zoom) // size_tile) + 1)

    # Vertical lines
    for tx in range(x_min, x_max + 1):
        x = (tx * size_tile - cam_x) * zoom + viewport_rect.x
        if viewport_rect.left <= x <= viewport_rect.right:
            pygame.draw.line(
                surface, color,
                (x, max(viewport_rect.top, (y_min * size_tile - cam_y) * zoom + viewport_rect.y)),
                (x, min(viewport_rect.bottom, (y_max * size_tile - cam_y) * zoom + viewport_rect.y)),
                1
            )
    # Horizontal lines
    for ty in range(y_min, y_max + 1):
        y = (ty * size_tile - cam_y) * zoom + viewport_rect.y
        if viewport_rect.top <= y <= viewport_rect.bottom:
            pygame.draw.line(
                surface, color,
                (max(viewport_rect.left, (x_min * size_tile - cam_x) * zoom + viewport_rect.x), y),
                (min(viewport_rect.right, (x_max * size_tile - cam_x) * zoom + viewport_rect.x), y),
                1
            )

    surface.set_clip(None)


def draw_highlight_layer(surface, layer, cam_x, cam_y, zoom,
                                 size_tile, width_map, height_map,
                                 viewport_rect, color=(60, 140, 255, 130)):
    """Cover the non-empty tiles of the layer with a translucent blue veil.
    Used to highlight the extent of the layer being edited.
    """
    surface.set_clip(viewport_rect)
    size_zoomed = max(1, int(round(size_tile * zoom)))

    case_x_min = max(0, int(cam_x // size_tile))
    case_y_min = max(0, int(cam_y // size_tile))
    case_x_max = min(width_map, int((cam_x + viewport_rect.width / zoom) // size_tile) + 1)
    case_y_max = min(height_map, int((cam_y + viewport_rect.height / zoom) // size_tile) + 1)

    overlay = pygame.Surface((size_zoomed, size_zoomed), pygame.SRCALPHA)
    overlay.fill(color)

    gids = layer['gids']
    for ty in range(case_y_min, case_y_max):
        line = gids[ty]
        for tx in range(case_x_min, case_x_max):
            if line[tx] <= 0:
                continue
            px = (tx * size_tile - cam_x) * zoom + viewport_rect.x
            py = (ty * size_tile - cam_y) * zoom + viewport_rect.y
            surface.blit(overlay, (px, py))

    surface.set_clip(None)


def draw_cursor_case(surface, case_x, case_y, cam_x, cam_y, zoom,
                          size_tile, width_map, height_map, viewport_rect,
                          gid_preview_surface=None):
    """Draw the outline of the tile under the mouse + a translucent preview
    of the selected tile if gid_preview_surface is given.
    """
    if not (0 <= case_x < width_map and 0 <= case_y < height_map):
        return

    surface.set_clip(viewport_rect)
    size_zoomed = max(1, int(round(size_tile * zoom)))
    px = (case_x * size_tile - cam_x) * zoom + viewport_rect.x
    py = (case_y * size_tile - cam_y) * zoom + viewport_rect.y

    # Translucent preview
    if gid_preview_surface is not None:
        preview = _surface_zoomed(gid_preview_surface, zoom, size_tile).copy()
        preview.set_alpha(140)
        surface.blit(preview, (px, py))

    # Neon cyan frame
    pygame.draw.rect(
        surface, COLOR_CYAN,
        pygame.Rect(int(px), int(py), size_zoomed, size_zoomed),
        2
    )
    surface.set_clip(None)
