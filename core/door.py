# core/door.py
# Door sprite - 3 frames: closed / ajar / open.
# Horizontal spritesheet: door_sheet.png (3 x 507x653 px).

import pygame
from utils.paths import asset_path
from settings import TILE_SIZE


# -- Timings ---------------------------------------------------------
_DURATION_AJAR   = 400   # ms between closed -> ajar
_DURATION_OPEN = 400   # ms between ajar -> open

# -- Frames in the spritesheet ---------------------------------------
_FRAME_CLOSED      = 0
_FRAME_AJAR = 1
_FRAME_OPEN     = 2

_SHEET_FRAME_W = 507
_SHEET_FRAME_H = 653


class Door:
    """
    Door sprite with 3 states.

    Displayed size: 2 tiles x 3 tiles (64x96 px).
    Only frame 0 blocks the player; from frame 1 the way is free.

    """

    WIDTH = TILE_SIZE * 2   # 64
    HEIGHT = TILE_SIZE * 3   # 96

    # Class-level cache shared by all doors - loaded once
    _frames: list[pygame.Surface] | None = None

    # -- Loading ----------------------------------------------------------

    @classmethod
    def load_assets(cls, path: str = None):
        if cls._frames is not None:
            return
        sheet = pygame.image.load(path or asset_path('door_sheet.png')).convert_alpha()
        frame_w = sheet.get_width() // 3
        frame_h = sheet.get_height()
        cls._frames = []
        for i in range(3):
            rect  = pygame.Rect(i * frame_w, 0, frame_w, frame_h)
            frame = sheet.subsurface(rect)
            frame = pygame.transform.scale(frame, (cls.WIDTH, cls.HEIGHT))
            cls._frames.append(frame)

    # -- Init -------------------------------------------------------------

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, self.WIDTH, self.HEIGHT)

        self.is_open   = False
        self.is_opening  = False
        self._frame_current = _FRAME_CLOSED
        self._t_transition   = 0   # start time of the current transition

    # -- Logic ------------------------------------------------------------

    def try_opening(self, player, time_ms=None) -> bool:
        if self.is_open or self.is_opening:
            return False
        if not player.have_key:
            return False
        self.is_opening    = True
        self._t_transition   = pygame.time.get_ticks() if time_ms is None else time_ms
        self._frame_current = _FRAME_CLOSED
        return True

    def update(self, time_ms: int):
        if not self.is_opening:
            return

        elapsed = time_ms - self._t_transition

        if self._frame_current == _FRAME_CLOSED:
            if elapsed >= _DURATION_AJAR:
                self._frame_current = _FRAME_AJAR
                self._t_transition   = time_ms

        elif self._frame_current == _FRAME_AJAR:
            if elapsed >= _DURATION_OPEN:
                self._frame_current = _FRAME_OPEN
                self.is_opening    = False
                self.is_open     = True
                self.rect.width      = 0
                self.rect.height     = 0

    @property
    def rect_collision(self) -> pygame.Rect:
        # From the ajar frame on, the player can pass
        if self._frame_current >= _FRAME_AJAR:
            return pygame.Rect(self.x, self.y, 0, 0)
        return pygame.Rect(self.x, self.y, self.WIDTH, self.HEIGHT)

    # -- Network ------------------------------------------------------------

    def get_state(self) -> dict:
        return {
            'x': self.x, 'y': self.y,
            'is_open': self.is_open,
            'opening': self.is_opening,
            'frame': self._frame_current,
        }

    def set_state(self, data: dict):
        self.x               = data['x']
        self.y               = data['y']
        self.is_open     = data['is_open']
        self.is_opening    = data['opening']
        self._frame_current = data['frame']

    # -- Rendering ---------------------------------------------------------

    def draw(self, surface: pygame.Surface,
                 camera_offset=(0, 0), time_ms: int = 0):
        if self._frames is None:
            return   # assets not loaded

        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        surface.blit(self._frames[self._frame_current], (sx, sy))
