# game_map.py
# Level tilemap and per-player visibility map.

import pygame
import os
from settings import *
from utils.cache import (
    DIRECTIONS_ECHO_RADIAL,
    DIRECTIONS_ECHO_RIGHT,
    DIRECTIONS_ECHO_LEFT,
)


class GameMap:
    def __init__(self, file_map, graphics=True):
        """Load the map. ``graphics=False`` (server) skips tilesets and background
        images: only the collision/visibility grid is built.
        """
        self._graphics = graphics
        self.map_data = []
        self.width_map = 0
        self.height_map = 0

        # Rendering optimisation: GID -> Surface cache + pre-baked surface
        self._cache_tiles = {}        # Avoids subsurface() on every frame
        self._map_prebake = None     # Whole-world pre-rendered surface
        self._vis_map_dirty = True     # Rebuild flag (replaces the hash)
        self._tiles_to_reveal = []    # Buffer of (x, y) tiles to patch onto the prebake
        
        # Vectors shared from utils.cache - no per-instance recomputation
        self._directions         = DIRECTIONS_ECHO_RADIAL
        self._directions_right  = DIRECTIONS_ECHO_RIGHT
        self._directions_left  = DIRECTIONS_ECHO_LEFT
        # Load the map file
        if os.path.exists(file_map):
            if file_map.endswith('.tmx'):
                self.load_tmx(file_map)
        else:
            print(f"[MAP] file {file_map} not found, using the default map")
            self.load_default_map()
        
        self.visibility_map = self.create_blank_visibility_map()

    def load_tmx(self, file_map):
        """Load the map from a Tiled TMX file (multi-layer).
        Wall.1 and Sol.1 = solid walls (type 1), everything else = empty (type 0).
        """
        try:
            import xml.etree.ElementTree as ET
            import sys

            if getattr(sys, 'frozen', False):
                base = os.path.join(sys._MEIPASS, 'assets')
            else:
                base = os.path.dirname(os.path.abspath(file_map))

            tree = ET.parse(file_map)
            root = tree.getroot()

            self.width_map = int(root.attrib['width'])
            self.height_map = int(root.attrib['height'])

            self.map_data = [[0] * self.width_map for _ in range(self.height_map)]

            layers_walls = {'Wall.1', 'Sol.1'}
            for layer in root.findall('layer'):
                name = layer.attrib.get('name', '')
                data_el = layer.find('data')
                if data_el is None:
                    continue
                values = [int(v) for v in data_el.text.strip().split(',')]
                if name in layers_walls:
                    for y in range(self.height_map):
                        for x in range(self.width_map):
                            gid = values[y * self.width_map + x]
                            if gid != 0:
                                self.map_data[y][x] = 1

            self.spawn = None
            for og in root.findall('objectgroup'):
                if og.attrib.get('name') == 'Spawn':
                    obj = og.find('object')
                    if obj is not None:
                        self.spawn = (int(float(obj.attrib['x'])),
                                    int(float(obj.attrib['y'])))

            self.layers_gids = []
            self.layers_names = []
            for layer in root.findall('layer'):
                data_el = layer.find('data')
                if data_el is None:
                    continue
                values = [int(v) for v in data_el.text.strip().split(',')]
                grid = []
                for row_y in range(self.height_map):
                    grid.append(values[row_y * self.width_map:(row_y + 1) * self.width_map])
                self.layers_gids.append(grid)
                self.layers_names.append(layer.attrib.get('name', ''))

            self.tilesets = []
            self.image_layers = []
            if not self._graphics:
                self._cache_tiles = {}
                print(f"[MAP] TMX map loaded (no graphics): {self.width_map}x{self.height_map}")
                return

            # Tilesets - load ALL the tilesets
            self.tileset = None
            self.tileset_firstgid = 1
            self.tileset_columns = 1
            self.tileset_size = 32
            self.tileset_spacing = 0
            self.tileset_margin = 0

            for ts_el in root.findall('tileset'):
                firstgid = int(ts_el.attrib.get('firstgid', 1))
                tsx_src = ts_el.attrib.get('source', '')
                if tsx_src:
                    tsx_path = os.path.join(base, tsx_src)
                    tsx_tree = ET.parse(tsx_path)
                    tsx_root = tsx_tree.getroot()
                    size  = int(tsx_root.attrib.get('tilewidth', 32))
                    spacing = int(tsx_root.attrib.get('spacing', 0))
                    margin  = int(tsx_root.attrib.get('margin', 0))
                    img_el  = tsx_root.find('image')
                    img_w   = int(img_el.attrib.get('width', 0))
                    columns = (img_w - 2*margin + spacing) // (size + spacing) if (size+spacing) > 0 else 1
                    img_src  = img_el.attrib.get('source', '')
                else:
                    size   = int(ts_el.attrib.get('tilewidth', 32))
                    spacing  = int(ts_el.attrib.get('spacing', 0))
                    margin   = int(ts_el.attrib.get('margin', 0))
                    columns = 11
                    img_el   = ts_el.find('image')
                    img_src  = img_el.attrib.get('source', '') if img_el is not None else ''

                if not img_src:
                    continue
                img_path = os.path.join(base, img_src)
                try:
                    surf = pygame.image.load(img_path).convert_alpha()
                    self.tilesets.append({
                        'firstgid': firstgid,
                        'surface':  surf,
                        'columns': columns,
                        'size':   size,
                        'spacing':  spacing,
                        'margin':   margin,
                    })
                    print(f"[MAP] tileset loaded: {img_src} (firstgid={firstgid})")
                except Exception as e:
                    print(f"[MAP] tileset not found: {img_path} - {e}")

            if self.tilesets:
                t0 = self.tilesets[0]
                self.tileset          = t0['surface']
                self.tileset_firstgid = t0['firstgid']
                self.tileset_columns = t0['columns']
                self.tileset_size   = t0['size']
                self.tileset_spacing  = t0['spacing']
                self.tileset_margin   = t0['margin']

            self._cache_tiles = {}

            # Image layers (midground, background PNG)
            self.image_layers = []
            for il in root.findall('imagelayer'):
                src = il.find('image')
                if src is None:
                    continue
                path_img = os.path.join(base, src.attrib['source'])
                offset_x = float(il.attrib.get('offsetx', 0))
                offset_y = float(il.attrib.get('offsety', 0))
                try:
                    img = pygame.image.load(path_img).convert_alpha()
                    self.image_layers.append({
                        'surface': img,
                        'offset_x': offset_x,
                        'offset_y': offset_y,
                    })
                    print(f"[MAP] image layer loaded: {src.attrib['source']}")
                except Exception as e:
                    print(f"[MAP] image layer not found: {e}")

            print(f"[MAP] TMX map loaded: {self.width_map}x{self.height_map}")
            if self.spawn:
                print(f"[MAP] spawn: {self.spawn}")

        except Exception as e:
            print(f"[MAP] ERROR while loading the TMX: {e}")
            import traceback
            traceback.print_exc()
            self.load_default_map()

    def load_default_map(self):
        """Load the hard-coded map (backup)."""
        self.map_data = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 2, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 2, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        ]
        self.width_map = len(self.map_data[0])
        self.height_map = len(self.map_data)
        self.layers_gids = []        
        self.tileset = None
        self.layers_gids = []
        self.image_layers = []
        print(f"[MAP] default map loaded: {self.width_map}x{self.height_map}")

    def create_blank_visibility_map(self):
        """Create a visibility map matching map_data."""
        vis_map = []
        for y, row in enumerate(self.map_data):
            vis_map.append([])
            for x, tile in enumerate(row):
                vis_map[y].append(REVEAL_ALL)
        return vis_map

    def is_wall(self, x, y):
        """Check whether the tile at pixel coordinates (x, y) is a wall."""
        tile_x = int(x // TILE_SIZE)
        tile_y = int(y // TILE_SIZE)
        
        if 0 <= tile_x < self.width_map and 0 <= tile_y < self.height_map:
            return self.map_data[tile_y][tile_x] == 1
        return True 

    def is_solid(self, tile_x, tile_y):
        """Check whether a tile is solid (used by enemies)."""
        if 0 <= tile_x < self.width_map and 0 <= tile_y < self.height_map:
            return self.map_data[tile_y][tile_x] in [1, 3]
        return False

    def _reveal_neighbors(self, tile_x, tile_y, vis_map, delta_set=None):
            """Reveal the touched block and its neighbours within 2 blocks (5x5 square)."""
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = tile_x + dx, tile_y + dy
                    if 0 <= nx < self.width_map and 0 <= ny < self.height_map:
                        if not vis_map[ny][nx]:
                            vis_map[ny][nx] = True
                        if delta_set is not None:
                            delta_set.add((nx, ny))

    def reveal_per_echo(self, center_x, center_y, vis_map):
        """Cast rays with the DDA algorithm (fast and accurate)."""
        start_tile_x = int(center_x // TILE_SIZE)
        start_tile_y = int(center_y // TILE_SIZE)
        range_tiles = int(ECHO_RANGE // TILE_SIZE)

        for cos_a, sin_a in self._directions:
            step_x = 1 if cos_a > 0 else -1 if cos_a < 0 else 0
            step_y = 1 if sin_a > 0 else -1 if sin_a < 0 else 0

            t_delta_x = abs(TILE_SIZE / cos_a) if cos_a != 0 else float('inf')
            t_delta_y = abs(TILE_SIZE / sin_a) if sin_a != 0 else float('inf')

            t_max_x = abs(((start_tile_x + (1 if step_x > 0 else 0)) * TILE_SIZE - center_x) / cos_a) if cos_a != 0 else float('inf')
            t_max_y = abs(((start_tile_y + (1 if step_y > 0 else 0)) * TILE_SIZE - center_y) / sin_a) if sin_a != 0 else float('inf')

            current_tile_x = start_tile_x
            current_tile_y = start_tile_y

            for _ in range(range_tiles):
                if not (0 <= current_tile_x < self.width_map and 0 <= current_tile_y < self.height_map):
                    break

                tile_type = self.map_data[current_tile_y][current_tile_x]
                if tile_type in [1, 3]:
                    self._reveal_neighbors(current_tile_x, current_tile_y, vis_map)
                    break
                vis_map[current_tile_y][current_tile_x] = True

                if t_max_x < t_max_y:
                    t_max_x += t_delta_x
                    current_tile_x += step_x
                else:
                    t_max_y += t_delta_y
                    current_tile_y += step_y

    def reveal_ring(self, center_x, center_y, radius_min, radius_max, vis_map):
        """Reveal the tiles within the ring [min_radius, max_radius] pixels.
        Used for the progressive reveal of the echo.
        """
        for i in range(ECHO_RAY_COUNT):
            cos_a, sin_a = self._directions[i]

            for dist in range(max(1, radius_min), min(radius_max + 1, ECHO_RANGE)):
                x = center_x + dist * cos_a
                y = center_y + dist * sin_a

                tile_x = int(x // TILE_SIZE)
                tile_y = int(y // TILE_SIZE)

                if not (0 <= tile_x < self.width_map and 0 <= tile_y < self.height_map):
                    break

                if self.map_data[tile_y][tile_x] in [1, 3]:
                    vis_map[tile_y][tile_x] = True
                    break  # Stop at the first wall: rays do not pass through

    def _draw_tile_prebake(self, x, y):
        """Draw a single tile onto the pre-baked surface."""
        px = x * TILE_SIZE
        py = y * TILE_SIZE
        tile_drawn = False
        for gids_layer in self.layers_gids:
            gid = gids_layer[y][x]
            if gid != 0 and self.tileset:
                tile_surf = self.get_tile_surface(gid)
                if tile_surf:
                    self._map_prebake.blit(tile_surf, (px, py))
                    tile_drawn = True
        if not tile_drawn:
            tile_type = self.map_data[y][x]
            rect = pygame.Rect(px, py, TILE_SIZE, TILE_SIZE)
            if tile_type == 1:
                pygame.draw.rect(self._map_prebake, COLOR_WALL_VISIBLE, rect)
            elif tile_type == 2:
                pygame.draw.rect(self._map_prebake, COLOR_GUIDE, rect)
            elif tile_type == 3:
                pygame.draw.rect(self._map_prebake, COLOR_SAVE_POINT, rect)

    def draw_map(self, surface, vis_map, camera_offset=(0,0)):
        off_x, off_y = camera_offset
        lv, hv = surface.get_size()

        map_w = self.width_map * TILE_SIZE
        map_h = self.height_map * TILE_SIZE

        if (self._map_prebake is None
                or self._map_prebake.get_size() != (map_w, map_h)
                or self._vis_map_dirty):
            # Path A - full rebuild
            self._map_prebake = pygame.Surface((map_w, map_h))
            self._map_prebake.fill(COLOR_BACKGROUND)

            for il in getattr(self, 'image_layers', []):
                self._map_prebake.blit(
                    il['surface'], (int(il['offset_x']), int(il['offset_y'])))

            for y in range(self.height_map):
                for x in range(self.width_map):
                    if not vis_map[y][x]:
                        continue
                    self._draw_tile_prebake(x, y)

            self._vis_map_dirty = False
            self._tiles_to_reveal.clear()

        elif self._tiles_to_reveal:
            # Path B - incremental patch (newly revealed tiles)
            for x, y in self._tiles_to_reveal:
                if 0 <= x < self.width_map and 0 <= y < self.height_map:
                    self._draw_tile_prebake(x, y)
            self._tiles_to_reveal.clear()

        # Path C is implicit - nothing to do when not dirty and no new tiles

        # Simple blit of the camera window from the pre-baked surface
        surface.fill(COLOR_BACKGROUND)
        surface.blit(self._map_prebake, (0, 0), pygame.Rect(off_x, off_y, lv, hv))
        
    def get_rects_collisions(self):
        """Return a list of Rects for every wall (type 1)."""
        rects = []
        for y in range(self.height_map):
            for x in range(self.width_map):
                if self.map_data[y][x] == 1:
                    rects.append(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        return rects

    # ------------------------------------------------------------------
    # SPATIAL GRID FOR COLLISIONS
    # ------------------------------------------------------------------

    _CELL_SIZE = TILE_SIZE * 4  # 128 px per cell

    def build_grid_collision(self):
        """Build a spatial grid from the collision rects."""
        self._grid_collision = {}
        cs = self._CELL_SIZE
        for y in range(self.height_map):
            for x in range(self.width_map):
                if self.map_data[y][x] == 1:
                    r = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE,
                                    TILE_SIZE, TILE_SIZE)
                    key_item = (x * TILE_SIZE // cs, y * TILE_SIZE // cs)
                    self._grid_collision.setdefault(key_item, []).append(r)

    def get_nearby_rects(self, rect, margin=None):
        """Return the collision rects in the cells overlapped by rect + margin.

        The margin (default TILE_SIZE*2) compensates for the movement between
        the query and the collision checks after the move.
        """
        if not hasattr(self, '_grid_collision'):
            self.build_grid_collision()
        if margin is None:
            margin = TILE_SIZE * 2
        cs = self._CELL_SIZE
        x_min = (rect.left   - margin) // cs
        x_max = (rect.right  + margin) // cs
        y_min = (rect.top    - margin) // cs
        y_max = (rect.bottom + margin) // cs
        result = []
        for cy in range(y_min, y_max + 1):
            for cx in range(x_min, x_max + 1):
                cell = self._grid_collision.get((cx, cy))
                if cell:
                    result.extend(cell)
        return result
    
    def reveal_per_echo_partial(self, center_x, center_y, attack_range, vis_map, delta_set=None):
        """Progressive reveal with DDA: stops at walls and at distance 'range'."""
        start_tile_x = int(center_x // TILE_SIZE)
        start_tile_y = int(center_y // TILE_SIZE)
        for cos_a, sin_a in self._directions:
            dir_x = cos_a if cos_a != 0 else 1e-10
            dir_y = sin_a if sin_a != 0 else 1e-10
            t_delta_x = abs(TILE_SIZE / dir_x)
            t_delta_y = abs(TILE_SIZE / dir_y)
            step_x = 1 if dir_x > 0 else -1
            step_y = 1 if dir_y > 0 else -1
            if dir_x > 0:
                t_max_x = ((start_tile_x + 1) * TILE_SIZE - center_x) / dir_x
            else:
                t_max_x = (center_x - start_tile_x * TILE_SIZE) / abs(dir_x)
            if dir_y > 0:
                t_max_y = ((start_tile_y + 1) * TILE_SIZE - center_y) / dir_y
            else:
                t_max_y = (center_y - start_tile_y * TILE_SIZE) / abs(dir_y)
            current_tile_x = start_tile_x
            current_tile_y = start_tile_y
            distance_traveled = 0
            if 0 <= current_tile_x < self.width_map and 0 <= current_tile_y < self.height_map:
                if not vis_map[current_tile_y][current_tile_x]:
                    vis_map[current_tile_y][current_tile_x] = True
                if delta_set is not None:
                    delta_set.add((current_tile_x, current_tile_y))
            while True:
                if t_max_x < t_max_y:
                    distance_traveled = t_max_x
                    t_max_x += t_delta_x
                    current_tile_x += step_x
                else:
                    distance_traveled = t_max_y
                    t_max_y += t_delta_y
                    current_tile_y += step_y
                if distance_traveled > attack_range:
                    break
                if not (0 <= current_tile_x < self.width_map and 0 <= current_tile_y < self.height_map):
                    break
                if not vis_map[current_tile_y][current_tile_x]:
                    vis_map[current_tile_y][current_tile_x] = True
                if delta_set is not None:
                    delta_set.add((current_tile_x, current_tile_y))
                if self.map_data[current_tile_y][current_tile_x] in [1, 3]:
                    self._reveal_neighbors(current_tile_x, current_tile_y, vis_map, delta_set)
                    break
    def reveal_per_echo_dir_partial(self, center_x, center_y, attack_range, vis_map, direction, delta_set=None):
        """Progressive DDA reveal inside a +-25 degree cone.
        direction: 1 = right (0 deg), -1 = left (180 deg).
        """
        directions_cone = self._directions_right if direction >= 0 else self._directions_left
        start_tile_x = int(center_x // TILE_SIZE)
        start_tile_y = int(center_y // TILE_SIZE)

        for cos_a, sin_a in directions_cone:
            dir_x = cos_a if cos_a != 0 else 1e-10
            dir_y = sin_a if sin_a != 0 else 1e-10
            t_delta_x = abs(TILE_SIZE / dir_x)
            t_delta_y = abs(TILE_SIZE / dir_y)
            step_x = 1 if dir_x > 0 else -1
            step_y = 1 if dir_y > 0 else -1
            if dir_x > 0:
                t_max_x = ((start_tile_x + 1) * TILE_SIZE - center_x) / dir_x
            else:
                t_max_x = (center_x - start_tile_x * TILE_SIZE) / abs(dir_x)
            if dir_y > 0:
                t_max_y = ((start_tile_y + 1) * TILE_SIZE - center_y) / dir_y
            else:
                t_max_y = (center_y - start_tile_y * TILE_SIZE) / abs(dir_y)
            current_tile_x = start_tile_x
            current_tile_y = start_tile_y
            distance_traveled = 0
            if 0 <= current_tile_x < self.width_map and 0 <= current_tile_y < self.height_map:
                if not vis_map[current_tile_y][current_tile_x]:
                    vis_map[current_tile_y][current_tile_x] = True
                if delta_set is not None:
                    delta_set.add((current_tile_x, current_tile_y))
            while True:
                if t_max_x < t_max_y:
                    distance_traveled = t_max_x
                    t_max_x += t_delta_x
                    current_tile_x += step_x
                else:
                    distance_traveled = t_max_y
                    t_max_y += t_delta_y
                    current_tile_y += step_y
                if distance_traveled > attack_range:
                    break
                if not (0 <= current_tile_x < self.width_map and 0 <= current_tile_y < self.height_map):
                    break
                if not vis_map[current_tile_y][current_tile_x]:
                    vis_map[current_tile_y][current_tile_x] = True
                if delta_set is not None:
                    delta_set.add((current_tile_x, current_tile_y))
                if self.map_data[current_tile_y][current_tile_x] in [1, 3]:
                    self._reveal_neighbors(current_tile_x, current_tile_y, vis_map, delta_set)
                    break



    def get_tile_surface(self, gid):
        if gid <= 0:
            return None
        if gid in self._cache_tiles:
            return self._cache_tiles[gid]
        ts = None
        for t in sorted(getattr(self, 'tilesets', []), key=lambda x: -x['firstgid']):
            if gid >= t['firstgid']:
                ts = t
                break
        if ts is None:
            self._cache_tiles[gid] = None
            return None
        idx = gid - ts['firstgid']
        col = idx % ts['columns']
        row = idx // ts['columns']
        x   = ts['margin'] + col * (ts['size'] + ts['spacing'])
        y   = ts['margin'] + row * (ts['size'] + ts['spacing'])
        w, h = ts['surface'].get_size()
        if x + ts['size'] > w or y + ts['size'] > h:
            self._cache_tiles[gid] = None
            return None
        surf = ts['surface'].subsurface(pygame.Rect(x, y, ts['size'], ts['size']))
        self._cache_tiles[gid] = surf
        return surf