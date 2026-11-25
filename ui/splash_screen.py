# ui/splash_screen.py
# Start-up screen (game logo with a fade).
# Extracted from client.py to slim the main file.

import pygame
from utils.paths import asset_path
import sys
from settings import *


def show_splash_screen(screen, duration=3000):
    """Show a splash screen with the game logo (70% of the screen)."""
    try:
        logo_path = asset_path('favicon.png')
        logo_original = pygame.image.load(logo_path).convert_alpha()
        width = screen.get_width()
        height = screen.get_height()
        size_ref = min(width, height)
        side_target = int(size_ref * 0.7)
        logo = pygame.transform.smoothscale(logo_original, (side_target, side_target))
        background = pygame.Surface((width, height))
        background.fill((0, 0, 0))
        logo_rect = logo.get_rect(center=(width // 2, height // 2))
        start = pygame.time.get_ticks()
        clock = pygame.time.Clock()

        while pygame.time.get_ticks() - start < duration:
            time_elapsed = pygame.time.get_ticks() - start
            if time_elapsed < duration * 0.3:
                alpha = int((time_elapsed / (duration * 0.3)) * 255)
            elif time_elapsed > duration * 0.7:
                alpha = int((1 - (time_elapsed - duration * 0.7) / (duration * 0.3)) * 255)
            else:
                alpha = 255
            screen.blit(background, (0, 0))
            logo_temp = logo.copy()
            logo_temp.set_alpha(alpha)
            screen.blit(logo_temp, logo_rect)
            pygame.display.flip()
            clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    return
    except Exception as e:
        print(f"[SPLASH] cannot show the splash screen: {e}")
