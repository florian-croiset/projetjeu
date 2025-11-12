import pygame
from Gaspard import screen
PLAYER_SPEED = 5
class Player(pygame.sprite.Sprite):
    def __init__(self,x,y):
        super().__init__()
        self.size=30
        self.image=pygame.Surface((self.size,self.size),pygame.SRCALPHA)
        pygame.draw.polygon(self.image,(100,200,255),[(0,self.size),(self.size/2,0),(self.size,self.size)])
        self.rect=self.image.get_rect(center=(x,y))
        self.speed=4
        self.collected=False
    def update(self,keys,ctrl):
        dx=dy=0
        if keys[ctrl["left"]]: dx=-self.speed
        if keys[ctrl["right"]]: dx=self.speed
        if keys[ctrl["up"]]: dy=-self.speed
        if keys[ctrl["down"]]: dy=self.speed
        self.rect.x+=dx; self.rect.y+=dy
        self.rect.clamp_ip(screen.get_rect())