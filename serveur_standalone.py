# serveur_standalone.py
# Point d'entrée pour lancer le serveur sur un VPS / Replit (sans écran).

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

import serveur

if __name__ == "__main__":
    print("[STANDALONE] Démarrage du serveur Echo...")
    serveur.main(id_slot=0, type_lancement="nouvelle")