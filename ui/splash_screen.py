# ui/splash_screen.py
# Écran de démarrage (logo du jeu avec fondu).
# Extrait de client.py pour alléger le fichier principal.

import pygame
import sys
import os
from parametres import *


def afficher_splash_screen(ecran, duree=3000):
    """Affiche un splash screen avec le logo du jeu (70% de l'écran)."""
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(__file__))

        logo_path = os.path.join(base_path, 'favicon.png')
        logo_original = pygame.image.load(logo_path).convert_alpha()
        taille_ref = min(LARGEUR_ECRAN, HAUTEUR_ECRAN)
        cote_cible = int(taille_ref * 0.7)
        logo = pygame.transform.smoothscale(logo_original, (cote_cible, cote_cible))
        fond = pygame.Surface((LARGEUR_ECRAN, HAUTEUR_ECRAN))
        fond.fill((0, 0, 0))
        logo_rect = logo.get_rect(center=(LARGEUR_ECRAN // 2, HAUTEUR_ECRAN // 2))
        debut = pygame.time.get_ticks()
        horloge = pygame.time.Clock()

        # Import conditionnel pour MODE_DEV
        if MODE_DEV:
            from utils import envoyer_logs

        while pygame.time.get_ticks() - debut < duree:
            temps_ecoule = pygame.time.get_ticks() - debut
            if temps_ecoule < duree * 0.3:
                alpha = int((temps_ecoule / (duree * 0.3)) * 255)
            elif temps_ecoule > duree * 0.7:
                alpha = int((1 - (temps_ecoule - duree * 0.7) / (duree * 0.3)) * 255)
            else:
                alpha = 255
            ecran.blit(fond, (0, 0))
            logo_temp = logo.copy()
            logo_temp.set_alpha(alpha)
            ecran.blit(logo_temp, logo_rect)
            pygame.display.flip()
            horloge.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    return
                if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                    envoyer_logs.envoyer_maintenant()
                    print("[LOG] Envoi manuel déclenché depuis le bouton HUD")
    except Exception as e:
        print(f"Impossible d'afficher le splash screen: {e}")
