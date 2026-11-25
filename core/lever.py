import pygame
from settings import TILE_SIZE


class Lever:
    def __init__(self, tile_x, tile_y):
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.x = tile_x * TILE_SIZE
        self.y = tile_y * TILE_SIZE
        # Rect slightly taller so the attack reaches it more easily
        self.rect = pygame.Rect(self.x, self.y - TILE_SIZE, TILE_SIZE, TILE_SIZE * 2)
        self.active = False
        self.time_activation = 0

    def activate(self, timestamp):
        self.active = True
        self.time_activation = timestamp

    def reset(self):
        self.active = False
        self.time_activation = 0

    def get_state(self):
        return {
            'x': self.x,
            'y': self.y,
            'active': self.active,
            'time': self.time_activation,
        }

    def set_state(self, data):
        self.active = data.get('active', False)
        self.time_activation = data.get('time', 0)

    def draw(self, surface, camera_offset=(0, 0), ticks=0):
        if not self.active:
            return
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y
        # Semi-transparent yellow halo over the tile sprite
        glow = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        glow.fill((255, 220, 50, 90))
        surface.blit(glow, (sx, sy))
