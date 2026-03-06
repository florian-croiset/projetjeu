import pygame

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((32, 32))
        self.image.fill((255, 0, 0))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.vel = pygame.Vector2()

    def update(self, walls):
        keys = pygame.key.get_pressed()
        self.vel.x = (keys[pygame.K_d] - keys[pygame.K_q]) * 4
        self.vel.y = (keys[pygame.K_s] - keys[pygame.K_z]) * 4

        # X
        self.rect.x += self.vel.x
        for wall in walls:
            if self.rect.colliderect(wall):
                if self.vel.x > 0:
                    self.rect.right = wall.left
                if self.vel.x < 0:
                    self.rect.left = wall.right

        # Y
        self.rect.y += self.vel.y
        for wall in walls:
            if self.rect.colliderect(wall):
                if self.vel.y > 0:
                    self.rect.bottom = wall.top
                if self.vel.y < 0:
                    self.rect.top = wall.bottom
