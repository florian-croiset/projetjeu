# visualiseur_map.py
# Script pour afficher la map et vérifier qu'elle est correcte

import pygame
import json
import sys

# Paramètres
TAILLE_TUILE = 32
COULEUR_FOND = (10, 10, 10)
COULEUR_MUR = (100, 100, 100)
COULEUR_GUIDE = (30, 30, 30)
COULEUR_SAUVEGARDE = (200, 200, 50)
COULEUR_VIDE = (20, 20, 20)

def charger_map(fichier="map.json"):
    """Charge la map depuis le fichier JSON."""
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['largeur'], data['hauteur'], data['data']
    except Exception as e:
        print(f"Erreur lors du chargement : {e}")
        sys.exit(1)

def afficher_map():
    """Affiche la map dans une fenêtre pygame."""
    pygame.init()
    
    # Charger la map
    largeur, hauteur, map_data = charger_map()
    
    print(f"Map chargée : {largeur}x{hauteur}")
    print(f"Tuile (0,0) = {map_data[0][0]}")
    print(f"Tuile (12,1) = {map_data[12][1]} (devrait être 3 pour un checkpoint)")
    
    # Créer la fenêtre
    largeur_ecran = largeur * TAILLE_TUILE
    hauteur_ecran = hauteur * TAILLE_TUILE
    
    # Limiter la taille si trop grande
    if largeur_ecran > 1920:
        largeur_ecran = 1920
    if hauteur_ecran > 1080:
        hauteur_ecran = 1080
    
    ecran = pygame.display.set_mode((largeur_ecran, hauteur_ecran))
    pygame.display.set_caption("Visualiseur de Map")
    
    # Créer une surface pour toute la map
    surface_map = pygame.Surface((largeur * TAILLE_TUILE, hauteur * TAILLE_TUILE))
    
    # Dessiner toute la map
    for y in range(hauteur):
        for x in range(largeur):
            tuile = map_data[y][x]
            rect = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE)
            
            if tuile == 0:
                couleur = COULEUR_VIDE
            elif tuile == 1:
                couleur = COULEUR_MUR
            elif tuile == 2:
                couleur = COULEUR_GUIDE
            elif tuile == 3:
                couleur = COULEUR_SAUVEGARDE
            else:
                couleur = (255, 0, 255)  # Magenta pour valeurs inconnues
            
            pygame.draw.rect(surface_map, couleur, rect)
    
    # Offset pour naviguer
    offset_x = 0
    offset_y = 0
    vitesse_scroll = 20
    
    running = True
    horloge = pygame.time.Clock()
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # Navigation avec les flèches
        touches = pygame.key.get_pressed()
        if touches[pygame.K_LEFT]:
            offset_x -= vitesse_scroll
        if touches[pygame.K_RIGHT]:
            offset_x += vitesse_scroll
        if touches[pygame.K_UP]:
            offset_y -= vitesse_scroll
        if touches[pygame.K_DOWN]:
            offset_y += vitesse_scroll
        
        # Limiter l'offset
        offset_x = max(0, min(offset_x, max(0, largeur * TAILLE_TUILE - largeur_ecran)))
        offset_y = max(0, min(offset_y, max(0, hauteur * TAILLE_TUILE - hauteur_ecran)))
        
        # Afficher
        ecran.fill(COULEUR_FOND)
        ecran.blit(surface_map, (-offset_x, -offset_y))
        
        # Afficher les infos
        police = pygame.font.Font(None, 24)
        texte = police.render(f"Position: ({offset_x//TAILLE_TUILE}, {offset_y//TAILLE_TUILE}) | Flèches pour naviguer | ESC pour quitter", True, (255, 255, 255))
        ecran.blit(texte, (10, 10))
        
        pygame.display.flip()
        horloge.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    afficher_map()