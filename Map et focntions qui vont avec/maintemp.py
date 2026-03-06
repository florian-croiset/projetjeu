import pygame
from map_collisions import TiledMap
from camera import Camera
from player import Player

pygame.init()
screen = pygame.display.set_mode((960, 640))
clock = pygame.time.Clock()

map = TiledMap("MapS2.tmx")
camera = Camera(map.width, map.height)

spawn = (1050, 350)  # valeur par défaut pour tester
player = Player(*spawn)


running = True
while running:
    dt = clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    player.update(map.walls)
    camera.update(player)

    screen.fill((0, 0, 0))
    map.draw(screen, camera)
    screen.blit(player.image, camera.apply(player.rect))
    pygame.display.flip()

pygame.quit()
