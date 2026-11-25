# palette.py
# Right side panel showing every available tile + an "eraser"
# (gid 0). Vertically scrollable with the mouse wheel when the cursor is over it.

import pygame
from settings import (
    COLOR_PANEL_BACKGROUND, COLOR_CYAN, COLOR_CYAN_DARK,
    COLOR_TEXT, COLOR_TEXT_DARK,
)


class Palette:
    """Clickable grid of the tileset tiles.

    The entry at index 0 is the "eraser" (gid 0). The following ones match the
    tileset gids (firstgid .. firstgid + tile_count - 1).
    """

    def __init__(self, cache_tiles, data_tmx, rect, font):
        self.cache = cache_tiles
        self.data = data_tmx
        self.rect = pygame.Rect(rect)
        self.font = font

        # Build the list of entries: [0 (eraser), firstgid, firstgid+1, ...]
        firstgid = data_tmx['tileset_firstgid']
        num = data_tmx['tileset_num_tiles']
        self.entries = [0] + [firstgid + i for i in range(num)]

        # Layout
        self.size_case = 48      # thumbnail size
        self.padding = 6
        self.header_h = 40         # title area at the top
        self.scroll_y = 0
        self._compute_grid()

    # ------------------------------------------------------------------
    def _compute_grid(self):
        width_available = self.rect.width - 2 * self.padding
        self.columns = max(1, width_available // (self.size_case + self.padding))
        lines_total = (len(self.entries) + self.columns - 1) // self.columns
        self.height_content = lines_total * (self.size_case + self.padding) + self.padding

    def _zone_grid(self):
        """Rect of the scrollable area where the thumbnails are shown."""
        return pygame.Rect(
            self.rect.x,
            self.rect.y + self.header_h,
            self.rect.width,
            self.rect.height - self.header_h,
        )

    def _index_position(self, index):
        """Screen position (x, y) of the thumbnail with the given index, scroll applied."""
        col = index % self.columns
        line = index // self.columns
        x = self.rect.x + self.padding + col * (self.size_case + self.padding)
        y = (self.rect.y + self.header_h + self.padding
             + line * (self.size_case + self.padding)
             - self.scroll_y)
        return (x, y)

    # ------------------------------------------------------------------
    def handle_scroll(self, event):
        """If the wheel turns above the panel, adjust the scroll. Return True if consumed."""
        if event.type != pygame.MOUSEWHEEL:
            return False
        pos = pygame.mouse.get_pos()
        if not self.rect.collidepoint(pos):
            return False
        self.scroll_y -= event.y * 60
        scroll_max = max(0, self.height_content - (self.rect.height - self.header_h))
        self.scroll_y = max(0, min(self.scroll_y, scroll_max))
        return True

    def gid_a_la_position(self, pos):
        """Return the gid of the thumbnail under the position, or None."""
        if not self._zone_grid().collidepoint(pos):
            return None
        for i in range(len(self.entries)):
            x, y = self._index_position(i)
            r = pygame.Rect(x, y, self.size_case, self.size_case)
            if r.collidepoint(pos):
                return self.entries[i]
        return None

    # ------------------------------------------------------------------
    def draw(self, surface, gid_active):
        # Panel background
        pygame.draw.rect(surface, COLOR_PANEL_BACKGROUND, self.rect)
        pygame.draw.line(
            surface, COLOR_CYAN_DARK,
            (self.rect.x, self.rect.y),
            (self.rect.x, self.rect.bottom), 1,
        )

        # Title
        title = self.font.render("Tuiles", True, COLOR_CYAN)
        surface.blit(title, (self.rect.x + 12, self.rect.y + 10))
        sub = self.font.render(f"gid : {gid_active}", True, COLOR_TEXT_DARK)
        surface.blit(sub, (self.rect.x + 90, self.rect.y + 12))

        # Thumbnails - clipped to the scrollable area
        zone = self._zone_grid()
        surface.set_clip(zone)

        for i, gid in enumerate(self.entries):
            x, y = self._index_position(i)
            # Vertical culling
            if y + self.size_case < zone.top or y > zone.bottom:
                continue

            r = pygame.Rect(x, y, self.size_case, self.size_case)

            # Cell background
            pygame.draw.rect(surface, (20, 18, 40), r)

            if gid == 0:
                # Eraser: red cross
                pygame.draw.line(surface, (200, 60, 60),
                                 (r.left + 8, r.top + 8),
                                 (r.right - 8, r.bottom - 8), 3)
                pygame.draw.line(surface, (200, 60, 60),
                                 (r.right - 8, r.top + 8),
                                 (r.left + 8, r.bottom - 8), 3)
                lib = self.font.render("∅", True, COLOR_TEXT)
                surface.blit(lib, (r.centerx - lib.get_width() // 2, r.bottom - 14))
            else:
                surf = self.cache.get(gid)
                if surf is not None:
                    sz = pygame.transform.scale(surf, (self.size_case - 4, self.size_case - 4))
                    surface.blit(sz, (r.x + 2, r.y + 2))

            # Border (thick + cyan when selected)
            if gid == gid_active:
                pygame.draw.rect(surface, COLOR_CYAN, r, 3)
            else:
                pygame.draw.rect(surface, (50, 55, 80), r, 1)

        surface.set_clip(None)
