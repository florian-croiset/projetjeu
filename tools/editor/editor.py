# editor.py
# Editor class - main Pygame loop of the TMX level editor.
# WASD camera, mouse-wheel zoom, side palette, saving through a button.

import json
import math

import pygame

from settings import (
    FPS, TILE_SIZE,
    COLOR_BACKGROUND, COLOR_CYAN, COLOR_TEXT, COLOR_TEXT_DARK,
    COLOR_PANEL_BACKGROUND,
)
from ui.button import Button

from tools.editor import tmx_io, rendering
from utils.paths import asset_path
from tools.editor.palette import Palette

_PATH_ENEMIES = asset_path('enemies.json')
_PATH_SOULS = asset_path('souls.json')

_COLORS_ENEMIES = {1: (255, 220, 0), 2: (255, 140, 0), 3: (220, 50, 50)}
_LABELS_ENEMIES = {
    1: ("Patroller", "1 HP - fast, fragile"),
    2: ("Guard", "2 HP - balanced"),
    3: ("Warden", "3 HP - slow, tough"),
}
_COLOR_SOUL = (100, 200, 255)


# ----------------------------------------------------------------------
# Constants local to the editor
# ----------------------------------------------------------------------
SPEED_CAM_PX_S = 800.0      # camera speed at zoom 1 (px/s)
ZOOM_MIN = 0.25
ZOOM_MAX = 4.0
ZOOM_STEP = 1.15               # multiplicative factor per wheel notch
WIDTH_PALETTE = 320


class Editor:
    """Standalone TMX map editing application."""

    def __init__(self, path_tmx):
        pygame.init()
        pygame.display.set_caption(f"Echo Editor - {path_tmx}")
        # Info() only returns the native resolution as long as no set_mode
        # has been called: the value is captured here once and for all.
        info = pygame.display.Info()
        self._native_w = info.current_w
        self._native_h = info.current_h
        self._size_windowed = (1280, 720)
        self._fullscreen = True
        self.screen = pygame.display.set_mode(
            (self._native_w, self._native_h),
            pygame.FULLSCREEN,
        )
        self.width = self.screen.get_width()
        self.height = self.screen.get_height()
        self.clock = pygame.time.Clock()

        self.data = tmx_io.load_tmx(path_tmx)
        self.cache_tiles = tmx_io.CacheTiles(self.data)

        # Camera (in world pixels) and zoom
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.zoom = 1.0
        self.keys_cam = {'z': False, 'q': False, 's': False, 'd': False}
        self.highlight_active = False

        # Editing state
        if not self.data['layers']:
            raise ValueError("The TMX file contains no tile layer")
        self.layer_active = 0
        self.gid_active = self.data['tileset_firstgid']
        self.modified = False
        self.in_paint = False
        self.message_temp = ""
        self.message_temp_end = 0

        # Enemy and soul modes
        self.mode = 'tiles'
        self.hp_enemy_active = 1
        self.data['enemies'] = self._load_enemies()
        self.data['souls'] = self._load_souls()

        # Fonts
        self.font_ui    = pygame.font.SysFont("Arial", 18)
        self.font_title = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 14)

        # Viewport (area on the left of the palette)
        self.viewport = pygame.Rect(0, 0, self.width - WIDTH_PALETTE, self.height)

        # Side palette
        rect_palette = pygame.Rect(
            self.width - WIDTH_PALETTE, 0,
            WIDTH_PALETTE, self.height - 80,
        )
        self.palette = Palette(self.cache_tiles, self.data, rect_palette, self.font_ui)

        # Buttons (bottom right, under the palette)
        self._init_buttons()

        # Center the camera on the map
        self._center_camera()

    # ------------------------------------------------------------------
    def _init_buttons(self):
        x_panel = self.width - WIDTH_PALETTE
        y = self.height - 70
        width = (WIDTH_PALETTE - 30) // 2
        self.button_layer = Button(
            x_panel + 10, y, width, 50,
            self._label_layer(), self.font_ui, style="normal",
        )
        self.button_save = Button(
            x_panel + 20 + width, y, width, 50,
            "Sauvegarder", self.font_ui, style="confirm",
        )
        self.button_mode = Button(
            x_panel + 10, y - 60, WIDTH_PALETTE - 20, 45,
            self._label_mode(), self.font_ui, style="ghost",
        )

    def _label_layer(self):
        name = self.data['layers'][self.layer_active]['name']
        return f"Couche : {name}"

    def _label_mode(self):
        if self.mode == 'tiles':
            return "Mode : Tuiles  [M]"
        elif self.mode == 'enemies':
            return "Mode : Ennemis  [M]"
        else:
            return "Mode: Souls  [M]"

    def _resize(self, width, height):
        self.width = width
        self.height = height
        if not self._fullscreen:
            self._size_windowed = (width, height)
        self.viewport = pygame.Rect(0, 0, self.width - WIDTH_PALETTE, self.height)
        self.palette.rect = pygame.Rect(
            self.width - WIDTH_PALETTE, 0,
            WIDTH_PALETTE, self.height - 140,
        )
        self._init_buttons()

    def _toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.screen = pygame.display.set_mode(
                (self._native_w, self._native_h),
                pygame.FULLSCREEN,
            )
        else:
            self.screen = pygame.display.set_mode(
                self._size_windowed,
                pygame.RESIZABLE,
            )
        self._resize(self.screen.get_width(), self.screen.get_height())

    def _center_camera(self):
        width_world = self.data['width'] * TILE_SIZE
        height_world = self.data['height'] * TILE_SIZE
        self.cam_x = max(0, (width_world - self.viewport.width / self.zoom) / 2)
        self.cam_y = max(0, (height_world - self.viewport.height / self.zoom) / 2)

    # ------------------------------------------------------------------
    def launch(self):
        in_progress = True
        while in_progress:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    in_progress = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    in_progress = False
                else:
                    self._handle_event(event)

            self._update(dt)
            self._draw()
            pygame.display.flip()

        pygame.quit()

    # ------------------------------------------------------------------
    def _handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self._resize(event.w, event.h)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                self._toggle_fullscreen()
                return
            if event.key == pygame.K_m:
                self._toggle_mode()
                return
            if event.key == pygame.K_z:
                self.keys_cam['z'] = True
            elif event.key == pygame.K_q:
                self.keys_cam['q'] = True
            elif event.key == pygame.K_s:
                # Ctrl+S = quick save
                if pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self._save()
                else:
                    self.keys_cam['s'] = True
            elif event.key == pygame.K_d:
                self.keys_cam['d'] = True
            elif event.key == pygame.K_a:
                self.highlight_active = True
            elif event.key == pygame.K_TAB:
                if self.mode == 'tiles':
                    self._change_layer()

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_z:
                self.keys_cam['z'] = False
            elif event.key == pygame.K_q:
                self.keys_cam['q'] = False
            elif event.key == pygame.K_s:
                self.keys_cam['s'] = False
            elif event.key == pygame.K_d:
                self.keys_cam['d'] = False
            elif event.key == pygame.K_a:
                self.highlight_active = False

        elif event.type == pygame.MOUSEWHEEL:
            if self.mode == 'tiles' and self.palette.handle_scroll(event):
                pass  # the palette consumed the scroll
            else:
                self._zoomer(event.y, pygame.mouse.get_pos())

        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_click_mouse(event)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.in_paint = False

        elif event.type == pygame.MOUSEMOTION:
            self.button_layer.verify_hover(event.pos)
            self.button_save.verify_hover(event.pos)
            self.button_mode.verify_hover(event.pos)
            if (self.in_paint and self.mode == 'tiles' and event.buttons[0]
                    and self.viewport.collidepoint(event.pos)):
                self._paint_to_position(event.pos)

    # ------------------------------------------------------------------
    def _handle_click_mouse(self, event):
        # Priority UI buttons (shared by both modes)
        if event.button == 1:
            if self.button_mode.verify_click(event):
                self._toggle_mode()
                return
            if self.button_save.verify_click(event):
                self._save()
                return

        if self.mode == 'tiles':
            if event.button != 1:
                return
            if self.button_layer.verify_click(event):
                self._change_layer()
                return
            gid = self.palette.gid_a_la_position(event.pos)
            if gid is not None:
                self.gid_active = gid
                return
            if self.viewport.collidepoint(event.pos):
                self.in_paint = True
                self._paint_to_position(event.pos)

        elif self.mode == 'enemies':
            if event.button == 1:
                if self._select_type_enemy(event.pos):
                    return
                if self.viewport.collidepoint(event.pos):
                    self._place_enemy(event.pos)
            elif event.button == 3:
                if self.viewport.collidepoint(event.pos):
                    self._delete_enemy(event.pos)

        else:  # 'souls' mode
            if event.button == 1:
                if self.viewport.collidepoint(event.pos):
                    self._place_soul(event.pos)
            elif event.button == 3:
                if self.viewport.collidepoint(event.pos):
                    self._delete_soul(event.pos)

    def _paint_to_position(self, pos_screen):
        """Convert screen_pos into a tile and write active_gid into the active layer."""
        x_local = pos_screen[0] - self.viewport.x
        y_local = pos_screen[1] - self.viewport.y
        tx, ty = rendering.screen_to_case(
            x_local, y_local, self.cam_x, self.cam_y, self.zoom, TILE_SIZE
        )
        if 0 <= tx < self.data['width'] and 0 <= ty < self.data['height']:
            line = self.data['layers'][self.layer_active]['gids'][ty]
            if line[tx] != self.gid_active:
                line[tx] = self.gid_active
                self.modified = True

    # ------------------------------------------------------------------
    # Enemy mode methods
    # ------------------------------------------------------------------
    def _toggle_mode(self):
        cycle = {'tiles': 'enemies', 'enemies': 'souls', 'souls': 'tiles'}
        self.mode = cycle[self.mode]
        self.in_paint = False
        self.button_mode.text = self._label_mode()

    def _load_enemies(self):
        try:
            with open(_PATH_ENEMIES, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _save_enemies(self):
        with open(_PATH_ENEMIES, 'w') as f:
            json.dump(self.data['enemies'], f, indent=2)

    def _place_enemy(self, pos_screen):
        x_local = pos_screen[0] - self.viewport.x
        y_local = pos_screen[1] - self.viewport.y
        tx, ty = rendering.screen_to_case(
            x_local, y_local, self.cam_x, self.cam_y, self.zoom, TILE_SIZE
        )
        if 0 <= tx < self.data['width'] and 0 <= ty < self.data['height']:
            x = tx * TILE_SIZE + TILE_SIZE // 2
            y = ty * TILE_SIZE + TILE_SIZE // 2
            self.data['enemies'].append({'x': x, 'y': y, 'max_hp': self.hp_enemy_active})
            self.modified = True

    def _delete_enemy(self, pos_screen):
        x_local = pos_screen[0] - self.viewport.x
        y_local = pos_screen[1] - self.viewport.y
        xm = x_local / self.zoom + self.cam_x
        ym = y_local / self.zoom + self.cam_y
        threshold = TILE_SIZE
        candidate = None
        dist_min = float('inf')
        for e in self.data['enemies']:
            d = math.hypot(e['x'] - xm, e['y'] - ym)
            if d < dist_min:
                dist_min = d
                candidate = e
        if candidate is not None and dist_min < threshold:
            self.data['enemies'].remove(candidate)
            self.modified = True

    def _select_type_enemy(self, pos):
        """Return True if the click was inside the type-selection panel."""
        rect = self._rect_palette_enemies()
        if not rect.collidepoint(pos):
            return False
        y_rel = pos[1] - rect.y
        height_block = rect.height // 3
        idx = min(2, y_rel // height_block)
        self.hp_enemy_active = idx + 1
        return True

    def _rect_palette_enemies(self):
        """Area of the right panel reserved for the enemy palette."""
        return pygame.Rect(
            self.width - WIDTH_PALETTE, 0,
            WIDTH_PALETTE, self.height - 140,
        )

    # ------------------------------------------------------------------
    # Soul mode methods
    # ------------------------------------------------------------------
    def _load_souls(self):
        try:
            with open(_PATH_SOULS, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def _save_souls(self):
        with open(_PATH_SOULS, 'w') as f:
            json.dump(self.data['souls'], f, indent=2)

    def _place_soul(self, pos_screen):
        x_local = pos_screen[0] - self.viewport.x
        y_local = pos_screen[1] - self.viewport.y
        tx, ty = rendering.screen_to_case(
            x_local, y_local, self.cam_x, self.cam_y, self.zoom, TILE_SIZE
        )
        if 0 <= tx < self.data['width'] and 0 <= ty < self.data['height']:
            x = tx * TILE_SIZE + TILE_SIZE // 2
            y = ty * TILE_SIZE + TILE_SIZE // 2
            self.data['souls'].append({'x': x, 'y': y})
            self.modified = True

    def _delete_soul(self, pos_screen):
        x_local = pos_screen[0] - self.viewport.x
        y_local = pos_screen[1] - self.viewport.y
        xm = x_local / self.zoom + self.cam_x
        ym = y_local / self.zoom + self.cam_y
        threshold = TILE_SIZE
        candidate = None
        dist_min = float('inf')
        for a in self.data['souls']:
            d = math.hypot(a['x'] - xm, a['y'] - ym)
            if d < dist_min:
                dist_min = d
                candidate = a
        if candidate is not None and dist_min < threshold:
            self.data['souls'].remove(candidate)
            self.modified = True

    # ------------------------------------------------------------------
    def _zoomer(self, direction, pos_pivot):
        """Zoom centered on the mouse position."""
        if not self.viewport.collidepoint(pos_pivot):
            return
        old_zoom = self.zoom
        if direction > 0:
            new = self.zoom * ZOOM_STEP
        else:
            new = self.zoom / ZOOM_STEP
        new = max(ZOOM_MIN, min(ZOOM_MAX, new))
        if new == old_zoom:
            return

        # Keep the world position under the pivot
        x_local = pos_pivot[0] - self.viewport.x
        y_local = pos_pivot[1] - self.viewport.y
        x_world = self.cam_x + x_local / old_zoom
        y_world = self.cam_y + y_local / old_zoom
        self.zoom = new
        self.cam_x = x_world - x_local / self.zoom
        self.cam_y = y_world - y_local / self.zoom
        self._clamp_camera()

        # Empty the scaling cache beyond a threshold to limit memory
        rendering.clear_cache_zoom()

    def _change_layer(self):
        num = len(self.data['layers'])
        self.layer_active = (self.layer_active + 1) % num
        self.button_layer.text = self._label_layer()

    def _save(self):
        try:
            tmx_io.save_tmx(self.data)
            self._save_enemies()
            self._save_souls()
            self.modified = False
            self._show_message("Saved!")
        except Exception as e:
            self._show_message(f"Erreur : {e}")
            print(f"[EDITOR] save error: {e}")
            import traceback
            traceback.print_exc()

    def _show_message(self, text, duration_ms=2500):
        self.message_temp = text
        self.message_temp_end = pygame.time.get_ticks() + duration_ms

    # ------------------------------------------------------------------
    def _update(self, dt):
        # WASD camera movement at constant speed (in world pixels)
        speed = SPEED_CAM_PX_S * dt / self.zoom
        if self.keys_cam['z']:
            self.cam_y -= speed
        if self.keys_cam['s']:
            self.cam_y += speed
        if self.keys_cam['q']:
            self.cam_x -= speed
        if self.keys_cam['d']:
            self.cam_x += speed
        self._clamp_camera()

    def _clamp_camera(self):
        width_world = self.data['width'] * TILE_SIZE
        height_world = self.data['height'] * TILE_SIZE
        margin = 200
        self.cam_x = max(-margin, min(self.cam_x, width_world - self.viewport.width / self.zoom + margin))
        self.cam_y = max(-margin, min(self.cam_y, height_world - self.viewport.height / self.zoom + margin))

    # ------------------------------------------------------------------
    def _draw(self):
        self.screen.fill(COLOR_BACKGROUND)

        # Map: image layers, tile layers, grid
        rendering.draw_image_layers(
            self.screen, self.data['image_layers'],
            self.cam_x, self.cam_y, self.zoom, self.viewport,
        )
        rendering.draw_tile_layers(
            self.screen, self.data['layers'], self.cache_tiles,
            self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
            self.data['width'], self.data['height'],
            self.viewport, layer_active=self.layer_active,
        )
        if self.highlight_active:
            rendering.draw_highlight_layer(
                self.screen, self.data['layers'][self.layer_active],
                self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
                self.data['width'], self.data['height'], self.viewport,
            )
        rendering.draw_grid(
            self.screen, self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
            self.data['width'], self.data['height'], self.viewport,
        )

        # Cursor on the tile under the mouse
        pos = pygame.mouse.get_pos()
        if self.viewport.collidepoint(pos):
            tx, ty = rendering.screen_to_case(
                pos[0] - self.viewport.x, pos[1] - self.viewport.y,
                self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
            )
            preview_surf = self.cache_tiles.get(self.gid_active) if self.gid_active > 0 else None
            rendering.draw_cursor_case(
                self.screen, tx, ty, self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
                self.data['width'], self.data['height'], self.viewport,
                gid_preview_surface=preview_surf,
            )

        # Enemies and souls (always visible, whatever the mode)
        self._draw_souls_editor()
        self._draw_enemies_editor()

        # Palette + buttons
        if self.mode == 'tiles':
            self.palette.draw(self.screen, self.gid_active)
            self.button_layer.draw(self.screen)
        elif self.mode == 'enemies':
            self._draw_palette_enemies()
        else:
            self._draw_palette_souls()
        self.button_mode.draw(self.screen)
        self.button_save.draw(self.screen)

        # Info HUD at the top left of the viewport
        self._draw_hud()

    def _draw_souls_editor(self):
        self.screen.set_clip(self.viewport)
        for a in self.data['souls']:
            sx = int((a['x'] - self.cam_x) * self.zoom) + self.viewport.x
            sy = int((a['y'] - self.cam_y) * self.zoom) + self.viewport.y
            if not (self.viewport.left - 20 <= sx <= self.viewport.right + 20
                    and self.viewport.top - 20 <= sy <= self.viewport.bottom + 20):
                continue
            r = max(5, int(8 * self.zoom))
            pygame.draw.circle(self.screen, (0, 0, 0), (sx, sy), r + 2)
            pygame.draw.circle(self.screen, _COLOR_SOUL, (sx, sy), r)
            # white cross to tell them apart from the enemies
            d = max(3, r - 2)
            pygame.draw.line(self.screen, (255, 255, 255), (sx - d, sy), (sx + d, sy), 1)
            pygame.draw.line(self.screen, (255, 255, 255), (sx, sy - d), (sx, sy + d), 1)
        self.screen.set_clip(None)

    def _draw_palette_souls(self):
        rect = pygame.Rect(
            self.width - WIDTH_PALETTE, 0,
            WIDTH_PALETTE, self.height - 140,
        )
        background = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        background.fill(COLOR_PANEL_BACKGROUND)
        self.screen.blit(background, rect.topleft)

        title = self.font_title.render("Free souls", True, COLOR_CYAN)
        self.screen.blit(title, (rect.x + 10, rect.y + 10))

        # Single info block
        y_block = rect.y + 50
        h_block = 80
        background_block = pygame.Surface((rect.width - 20, h_block), pygame.SRCALPHA)
        background_block.fill((20, 30, 50, 220))
        self.screen.blit(background_block, (rect.x + 10, y_block))
        pygame.draw.rect(self.screen, COLOR_CYAN,
                         pygame.Rect(rect.x + 10, y_block, rect.width - 20, h_block), 2)

        cx, cy = rect.x + 30, y_block + h_block // 2
        pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), 14)
        pygame.draw.circle(self.screen, _COLOR_SOUL, (cx, cy), 12)
        d = 7
        pygame.draw.line(self.screen, (255, 255, 255), (cx - d, cy), (cx + d, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255), (cx, cy - d), (cx, cy + d), 2)

        s_name = self.font_ui.render("Free soul", True, _COLOR_SOUL)
        s_desc = self.font_small.render("Value: 5 souls", True, COLOR_TEXT_DARK)
        self.screen.blit(s_name, (rect.x + 50, y_block + h_block // 2 - 14))
        self.screen.blit(s_desc, (rect.x + 50, y_block + h_block // 2 + 4))

        # Counter
        num = len(self.data['souls'])
        s_num = self.font_small.render(f"{num} soul(s) placed", True, COLOR_TEXT_DARK)
        self.screen.blit(s_num, (rect.x + 10, y_block + h_block + 12))

    def _draw_enemies_editor(self):
        self.screen.set_clip(self.viewport)
        for e in self.data['enemies']:
            sx = int((e['x'] - self.cam_x) * self.zoom) + self.viewport.x
            sy = int((e['y'] - self.cam_y) * self.zoom) + self.viewport.y
            if not (self.viewport.left - 20 <= sx <= self.viewport.right + 20
                    and self.viewport.top - 20 <= sy <= self.viewport.bottom + 20):
                continue
            hp = e['max_hp']
            color = _COLORS_ENEMIES.get(hp, (180, 180, 180))
            r = max(6, int(10 * self.zoom))
            pygame.draw.circle(self.screen, (0, 0, 0), (sx, sy), r + 2)
            pygame.draw.circle(self.screen, color, (sx, sy), r)
            label = str(hp)
            surf = self.font_small.render(label, True, (0, 0, 0))
            self.screen.blit(surf, surf.get_rect(center=(sx, sy)))
        self.screen.set_clip(None)

    def _draw_palette_enemies(self):
        rect = self._rect_palette_enemies()
        background = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        background.fill(COLOR_PANEL_BACKGROUND)
        self.screen.blit(background, rect.topleft)

        title = self.font_title.render("Types d'ennemis", True, COLOR_CYAN)
        self.screen.blit(title, (rect.x + 10, rect.y + 10))

        num = 3
        height_block = (rect.height - 50) // num
        for i, hp in enumerate((1, 2, 3)):
            y_block = rect.y + 50 + i * height_block
            color = _COLORS_ENEMIES[hp]
            active = (hp == self.hp_enemy_active)

            background_block = pygame.Surface((rect.width - 20, height_block - 6), pygame.SRCALPHA)
            background_block.fill((30, 25, 50, 220) if active else (15, 12, 30, 180))
            self.screen.blit(background_block, (rect.x + 10, y_block + 3))

            edge_color = COLOR_CYAN if active else (60, 60, 90)
            pygame.draw.rect(
                self.screen, edge_color,
                pygame.Rect(rect.x + 10, y_block + 3, rect.width - 20, height_block - 6),
                2,
            )

            cx = rect.x + 30
            cy = y_block + height_block // 2
            pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), 14)
            pygame.draw.circle(self.screen, color, (cx, cy), 12)
            num = self.font_small.render(str(hp), True, (0, 0, 0))
            self.screen.blit(num, num.get_rect(center=(cx, cy)))

            name, desc = _LABELS_ENEMIES[hp]
            s_name = self.font_ui.render(name, True, color if active else COLOR_TEXT)
            s_desc = self.font_small.render(desc, True, COLOR_TEXT_DARK)
            self.screen.blit(s_name, (rect.x + 50, y_block + height_block // 2 - 14))
            self.screen.blit(s_desc, (rect.x + 50, y_block + height_block // 2 + 4))

    def _draw_hud(self):
        pos = pygame.mouse.get_pos()
        if self.viewport.collidepoint(pos):
            tx, ty = rendering.screen_to_case(
                pos[0] - self.viewport.x, pos[1] - self.viewport.y,
                self.cam_x, self.cam_y, self.zoom, TILE_SIZE,
            )
            if 0 <= tx < self.data['width'] and 0 <= ty < self.data['height']:
                layers_here = [
                    layer['name']
                    for layer in self.data['layers']
                    if layer['gids'][ty][tx] != 0
                ]
                tile_info = ", ".join(layers_here) if layers_here else "aucune tuile"
            else:
                tile_info = "aucune tuile"
        else:
            tile_info = "aucune tuile"

        if self.mode == 'tiles':
            lines = [
                f"Map : {self.data['width']}x{self.data['height']} tuiles",
                f"Zoom : {int(self.zoom * 100)}%",
                "Mode : Tuiles",
                f"Couche active : {self.data['layers'][self.layer_active]['name']}",
                f"Selected tile: gid {self.gid_active}",
                f"Hovered tile: {tile_info}",
            ]
        elif self.mode == 'enemies':
            name_type = _LABELS_ENEMIES[self.hp_enemy_active][0]
            lines = [
                f"Map : {self.data['width']}x{self.data['height']} tuiles",
                f"Zoom : {int(self.zoom * 100)}%",
                f"Mode: Enemies ({len(self.data['enemies'])} placed)",
                f"Type actif : {name_type} ({self.hp_enemy_active} PV)",
            ]
        else:
            lines = [
                f"Map : {self.data['width']}x{self.data['height']} tuiles",
                f"Zoom : {int(self.zoom * 100)}%",
                f"Mode: Souls ({len(self.data['souls'])} placed)",
            ]
        if self.modified:
            lines.append("* MODIFIED (not saved)")

        # Semi-transparent background
        h_total = 12 + 22 * len(lines)
        background = pygame.Surface((380, h_total), pygame.SRCALPHA)
        background.fill((10, 8, 25, 200))
        pygame.draw.rect(background, COLOR_CYAN, background.get_rect(), 1)
        self.screen.blit(background, (10, 10))

        for i, line in enumerate(lines):
            color = (255, 200, 60) if line.startswith("●") else COLOR_TEXT
            surf = self.font_ui.render(line, True, color)
            self.screen.blit(surf, (20, 16 + i * 22))

        # Help at the bottom
        if self.mode == 'tiles':
            help = "WASD: move  •  Wheel: zoom  •  TAB: layer  •  A: highlight  •  M: next mode  •  Ctrl+S: save  •  Échap : quitter"
        else:
            help = "WASD: move  •  Wheel: zoom  •  Left click: place  •  Right click: delete  •  M: next mode  •  Ctrl+S: save  •  Échap : quitter"
        s = self.font_small.render(help, True, COLOR_TEXT_DARK)
        self.screen.blit(s, (10, self.height - 22))

        # Temporary message (saved / error)
        if self.message_temp and pygame.time.get_ticks() < self.message_temp_end:
            surf = self.font_title.render(self.message_temp, True, COLOR_CYAN)
            r = surf.get_rect(midtop=(self.viewport.centerx, 30))
            background_msg = pygame.Surface((r.width + 30, r.height + 16), pygame.SRCALPHA)
            background_msg.fill((10, 8, 25, 220))
            pygame.draw.rect(background_msg, COLOR_CYAN, background_msg.get_rect(), 1)
            self.screen.blit(background_msg, (r.x - 15, r.y - 8))
            self.screen.blit(surf, r)
