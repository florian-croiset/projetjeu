# parametres.py
# Fichier pour stocker les constantes et paramètres globaux du jeu.

# -- Paramètres de la Fenêtre --
LARGEUR_ECRAN = 1024
HAUTEUR_ECRAN = 768
TITRE_FENETRE = "Metroidvania - Écho"
FPS = 60

# -- Paramètres de Sauvegarde --
NB_SLOTS_SAUVEGARDE = 3

# -- Paramètres de la Carte (Tilemap) --
TAILLE_TUILE = 32  # Chaque tuile fait 32x32 pixels

# -- Couleurs (Format RGB) --
COULEUR_NOIR = (0, 0, 0)
COULEUR_BLANC = (255, 255, 255)
COULEUR_JOUEUR = (50, 150, 255)
COULEUR_JOUEUR_AUTRE = (255, 100, 50) # Couleur pour les autres joueurs
COULEUR_ENNEMI = (200, 50, 50) 
COULEUR_MUR_VISIBLE = (100, 100, 100) # Couleur des murs révélés
COULEUR_GUIDE = (30, 30, 30) # Petites parties visibles en permanence
COULEUR_FOND = (10, 10, 10) # Fond très sombre, mais pas noir absolu
COULEUR_SAUVEGARDE = (200, 200, 50) # Jaune pour les points de sauvegarde
COULEUR_AME_PERDUE = (150, 150, 255) # Bleu/Violet pâle pour l'âme

# -- Couleurs pour l'Interface (UI) --
COULEUR_TITRE = (220, 220, 220)
COULEUR_TEXTE = (200, 200, 200)
COULEUR_BOUTON = (50, 50, 70)
COULEUR_BOUTON_SURVOL = (80, 80, 100)
COULEUR_INPUT_BOX = (30, 30, 40)
COULEUR_FOND_PAUSE = (10, 10, 10, 180) # Fond semi-transparent pour la pause
COULEUR_PV = (50, 200, 50) # Vert pour la vie
COULEUR_PV_PERDU = (70, 70, 70) # Gris pour la vie perdue

# -- Paramètres du Joueur --
VITESSE_JOUEUR = 5
FORCE_SAUT = 12
GRAVITE = 0.6
PV_JOUEUR_MAX = 6
TEMPS_INVINCIBILITE = 1000 # 1 seconde d'invincibilité après un coup

# -- Paramètres de l'Ennemi --
VITESSE_ENNEMI = 1.5

# -- Paramètres de l'Écho (Raycasting) --
PORTEE_ECHO = 250  # En pixels (longueur max des rayons)
NB_RAYONS_ECHO = 90  # Nombre de rayons (plus c'est haut, plus c'est lourd)
COOLDOWN_ECHO = 6000 # 6 secondes (en millisecondes)

# -- Paramètres Réseau --
PORT_SERVEUR = 5555
# L'hôte utilisera "localhost" (ou 127.0.0.1)
# Les clients devront entrer l'adresse IP de l'hôte
# Pour les tests sur la même machine, tout le monde utilise "localhost"