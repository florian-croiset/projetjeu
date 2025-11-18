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
from screeninfo import *
import win32api
import win32con
import sys
#configuration
WIDTH, HEIGHT = 1920,1080
PLAYER_SPEED = 5
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

def get_screen_refresh_rate_windows_fixed():
    """
    Récupère le taux de rafraîchissement de l'écran principal sous Windows 
    en utilisant les API natives.
    """
    if sys.platform != "win32":
        return 0.0
    
    try:
        # 1. Obtenir les informations du périphérique d'affichage (Moniteur principal : index 0)
        device = win32api.EnumDisplayDevices(None, 0)
        
        # 2. Obtenir les paramètres d'affichage actuels
        #    -> La constante ENUM_CURRENT_SETTINGS est dans win32con
        settings = win32api.EnumDisplaySettings(device.DeviceName, win32con.ENUM_CURRENT_SETTINGS)
        
        # 3. Le taux de rafraîchissement est dans l'attribut DisplayFrequency
        refresh_rate = settings.DisplayFrequency
        
        # win32api retourne un int pour la fréquence (ex: 60, 144)
        return float(refresh_rate)
        
    except Exception as e:
        return 0.0

# Récupérer le taux dans une variable
fps_ecran = get_screen_refresh_rate_windows_fixed()
if __name__ == "__main__":
    pass