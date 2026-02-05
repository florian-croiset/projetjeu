# parametres.py
# Fichier pour stocker les constantes et paramètres globaux du jeu.
# CORRECTION : Ajout de la valeur en âmes des ennemis.

# -- Paramètres de la Fenêtre --
LARGEUR_ECRAN = 1920
HAUTEUR_ECRAN = 1080
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
COULEUR_JOUEUR_AUTRE = (255, 100, 50) 
COULEUR_ENNEMI = (200, 50, 50) 
COULEUR_MUR_VISIBLE = (100, 100, 100) 
COULEUR_GUIDE = (30, 30, 30) 
COULEUR_FOND = (10, 10, 10) 
COULEUR_SAUVEGARDE = (200, 200, 50) 
COULEUR_AME_PERDUE = (150, 150, 255) 
COULEUR_ATTAQUE = (255, 255, 200)

# -- Couleurs pour l'Interface (UI) --
COULEUR_TITRE = (220, 220, 220)
COULEUR_TEXTE = (200, 200, 200)
COULEUR_BOUTON = (50, 50, 70)
COULEUR_BOUTON_SURVOL = (80, 80, 100)
COULEUR_INPUT_BOX = (30, 30, 40)
COULEUR_FOND_PAUSE = (10, 10, 10, 180) 
COULEUR_PV = (50, 200, 50) 
COULEUR_PV_PERDU = (70, 70, 70) 

# -- Paramètres du Joueur --
VITESSE_JOUEUR = 5
FORCE_SAUT = 13
GRAVITE = 0.6
PV_JOUEUR_MAX = 5
TEMPS_INVINCIBILITE = 1000 
ARGENT_DEPART = 0

# -- Paramètres de Combat --
DUREE_ATTAQUE = 200
COOLDOWN_ATTAQUE = 600
PORTEE_ATTAQUE = 40 
DEGATS_JOUEUR = 1

# -- Paramètres de l'Ennemi --
VITESSE_ENNEMI = 1.5
PV_ENNEMI_BASE = 3
ARGENT_PAR_ENNEMI = 10 # <-- Un ennemi rapporte 10 âmes

# -- Paramètres des Capacités --
# Dash
DISTANCE_DASH = TAILLE_TUILE * 4  # 4 blocs de texture (128 pixels si TAILLE_TUILE=32)
DUREE_DASH = 150  # millisecondes
COOLDOWN_DASH = 600  # millisecondes
DASH_EN_AIR_MAX = 1  # Nombre de dashs autorisés en l'air

# Double Saut
FORCE_DOUBLE_SAUT = 10  # Légèrement moins puissant que FORCE_SAUT (12)

# -- Paramètres de l'Écho (Raycasting) --
PORTEE_ECHO = 250 
NB_RAYONS_ECHO = 360
COOLDOWN_ECHO = 6000

# -- Paramètres Réseau --
PORT_SERVEUR = 5555

# -- Paramètres de la Caméra --
ZOOM_CAMERA = 2.5  # 1.0 = Normal, 2.0 = Zoom x2