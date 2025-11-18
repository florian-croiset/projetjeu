from install_package import install_package
install_package(["pygame","multiprocessing","math","numpy","pywin32","sys","subprocess","time","os","json","screeninfo"])
import pygame
import multiprocessing
import math
import numpy
import sys
import subprocess
import time
import os
import json
from Configuration import *

#configuration
WIDTH, HEIGHT = 1920,1080

ANIM_FPS = 8
FRAME_W, FRAME_H = 48, 48
REVEAL_RADIUS = 200
REVEAL_DURATION = 2
COOLDOWN = 10

GRAVITY = 0.5
JUMP_SPEED = -10

BG_COLOR = (20, 20, 20)
WALL_COLOR = (70, 70, 70)
WHITE = (255, 255, 255)
GREEN = (0, 255, 100)

# --- INITIALISATION ---
pygame.init()
pygame.display.set_caption("Human Explorer")
screen = pygame.display.set_mode((WIDTH, HEIGHT))
font = pygame.font.SysFont("cambria", 25)
clock = pygame.time.Clock()
def draw_center(text,font,color,y):
    surf=font.render(text,True,color)
    screen.blit(surf,(WIDTH//2-surf.get_width()//2,y))

running = True
while running:
    # secondes écoulées depuis la dernière frame
    dt = clock.tick(FPS) / 1000



if __name__ == "__main__":
    pass