import pygame

class Camera:
    def __init__(self, width, height):
        self.rect = pygame.Rect(0, 0, width, height)

    def apply(self, rect):
        return rect.move(self.rect.topleft)

    def apply_pos(self, x, y):
        return x + self.rect.x, y + self.rect.y

    def update(self, target):
        self.rect.x = -target.rect.centerx + 480
        self.rect.y = -target.rect.centery + 320
