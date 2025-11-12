import pygame
from Gaspard import *
from Save import load_settings
settings = load_settings()
def apply_display_settings():
    global screen, clock
    flags = 0
    if settings["display_mode"] == "borderless":
        flags = pygame.NOFRAME
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=settings["vsync"])
    elif settings["display_mode"] == "fullscreen":
        flags = pygame.FULLSCREEN
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=settings["vsync"])
    else:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), vsync=settings["vsync"])
    clock = pygame.time.Clock()
    pygame.display.set_caption("EchoVerse — Premier aperçu")