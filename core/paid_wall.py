import pygame
from settings import TILE_SIZE


class PaidWall:
    RANGE_INTERACTION = 80

    def __init__(self, tile_x, tile_y, cost, message):
        self.x = tile_x * TILE_SIZE
        self.y = tile_y * TILE_SIZE
        self.rect = pygame.Rect(self.x, self.y, TILE_SIZE, TILE_SIZE)
        self.cost = cost
        self.message = message
        self.unlocked = False
        self._font = None

    def _init_font(self):
        if self._font is None:
            self._font = pygame.font.Font(None, 22)

    def try_pay(self, player):
        if self.unlocked:
            return 'already_unlocked'
        if player.money < self.cost:
            return 'pauvre'
        player.money -= self.cost
        self.unlocked = True
        return 'unlocked'

    def get_state(self):
        return {'unlocked': self.unlocked}

    def set_state(self, data):
        self.unlocked = data.get('unlocked', False)

    def draw(self, surface, camera_offset, player_rect=None):
        if self.unlocked:
            return
        if player_rect is None:
            return
        dx = player_rect.centerx - (self.x + TILE_SIZE // 2)
        dy = player_rect.centery - (self.y + TILE_SIZE // 2)
        if (dx * dx + dy * dy) > self.RANGE_INTERACTION ** 2:
            return

        self._init_font()
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        lines = [self.message, "[F]"]
        surfs = [self._font.render(l, True, (220, 200, 255)) for l in lines]
        w = max(s.get_width() for s in surfs) + 20
        h = sum(s.get_height() for s in surfs) + 14

        bx = sx + TILE_SIZE // 2 - w // 2
        by = sy - h - 6

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((20, 10, 40, 210))
        pygame.draw.rect(bg, (150, 100, 220), pygame.Rect(0, 0, w, h), 1)
        surface.blit(bg, (bx, by))

        y_cur = by + 7
        for s in surfs:
            surface.blit(s, (bx + (w - s.get_width()) // 2, y_cur))
            y_cur += s.get_height()
