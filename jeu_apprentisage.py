import install_package as ip
ip.install_package(["setuptools","pygame"])

import pygame
import sys
import json
import os

default_WIDTH, default_HEIGHT = 960, 640
default_fps = 60
fps = 0,30,60,100,120,144,180,240,360
highlight = (120,180,255)

SAVE_FILE = "save_slots.json"
CTRL_FILE = "controls.json"
SET_FILE = "settings.json"
MAX_SLOTS = 3



WHITE = (255,255,255)
BLACK = (0,0,0)
BG_COLOR = (18,18,30)
PLAYER_COLOR = (100,200,255)
ENEMY_COLOR = (255,100,100)
SHARD_COLOR = (200,180,255)
EXIT_COLOR = (150,255,150)

pygame.init()
z=pygame.FULLSCREEN
os.environ["SDL_VIDEO_WINDOWS_POS"] = "0 , 28"
screen=fenetre = pygame.display.set_mode((0, 0),z)

pygame.display.update()
def game():
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()

game()