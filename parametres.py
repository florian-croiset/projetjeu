# parametres.py
# Fichier pour stocker les constantes et paramètres globaux du jeu.
# MISE À JOUR : Couleurs alignées sur la charte graphique Echo (Team Nightberry).

# -- Paramètres de la Fenêtre --
LARGEUR_ECRAN = 1920
HAUTEUR_ECRAN = 1080
TITRE_FENETRE = "Écho - Team Nightberry"
FPS = 60

# -- Paramètres de Sauvegarde --
NB_SLOTS_SAUVEGARDE = 3

# -- Paramètres de la Carte (Tilemap) --
TAILLE_TUILE = 32  # Chaque tuile fait 32x32 pixels

# =====================================================================
# PALETTE DE COULEURS — CHARTE GRAPHIQUE ECHO (Team Nightberry)
# =====================================================================
# Fond & neutres
COULEUR_NOIR          = (0, 0, 0)
COULEUR_BLANC         = (255, 255, 255)
COULEUR_FOND          = (8, 8, 20)          # Noir-bleu profond
COULEUR_FOND_ALT      = (12, 12, 28)        # Légèrement plus clair
COULEUR_FOND_PANEL    = (14, 10, 35)        # Fond des panneaux UI

# Cyan néon (couleur primaire Echo)
COULEUR_CYAN          = (0, 208, 198)       # #00d4ff  — néon principal
COULEUR_CYAN_CLAIR    = (96, 244, 215)     # Survol / highlight
COULEUR_CYAN_SOMBRE   = (3, 119, 120)       # Bordure / ombre

# Violet (couleur secondaire Echo)
COULEUR_VIOLET        = (123, 47, 255)      # #7b2fff  — accent violet
COULEUR_VIOLET_CLAIR  = (160, 100, 255)     # Survol violet
COULEUR_VIOLET_SOMBRE = (60, 20, 120)       # Ombre violette

# Couleurs gameplay (conservées)
COULEUR_JOUEUR        = (50, 150, 255)
COULEUR_JOUEUR_AUTRE  = (255, 100, 50)
COULEUR_ENNEMI        = (200, 50, 50)
COULEUR_MUR_VISIBLE   = (40, 40, 80)        # Murs dans l'ambiance Echo
COULEUR_GUIDE         = (20, 20, 40)
COULEUR_SAUVEGARDE    = (0, 212, 255)       # Checkpoints en cyan Echo
COULEUR_AME_PERDUE    = (160, 100, 255)     # Âmes en violet Echo
COULEUR_ATTAQUE       = (255, 255, 200)

# -- Couleurs pour l'Interface (UI) — palette Echo --
COULEUR_TITRE         = (0, 208, 198)       # Titres en cyan néon
COULEUR_TEXTE         = (200, 220, 235)     # Texte clair légèrement bleuté
COULEUR_TEXTE_SOMBRE  = (120, 140, 160)     # Texte secondaire / désactivé

# Boutons normaux : fond sombre avec bordure cyan
COULEUR_BOUTON        = (14, 10, 35)        # Fond foncé (violet très sombre)
COULEUR_BOUTON_SURVOL = (25, 15, 60)        # Survol : légèrement plus clair

# Input
COULEUR_INPUT_BOX     = (10, 8, 25)
COULEUR_INPUT_ACTIF   = (0, 212, 255)

# Pause / overlay
COULEUR_FOND_PAUSE    = (4, 4, 15, 200)     # Semi-transparent très sombre

# HUD
COULEUR_PV            = (0, 212, 255)       # PV en cyan Echo
COULEUR_PV_PERDU      = (30, 20, 60)        # PV perdu en violet très sombre

# =====================================================================

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
ARGENT_PAR_ENNEMI = 10

# -- Paramètres des Capacités --
DISTANCE_DASH = TAILLE_TUILE * 4
DUREE_DASH = 150
COOLDOWN_DASH = 600
DASH_EN_AIR_MAX = 1
FORCE_DOUBLE_SAUT = 10

# -- Paramètres de l'Écho (Raycasting) --
PORTEE_ECHO = 250
NB_RAYONS_ECHO = 360
COOLDOWN_ECHO = 2500            # Réduit : 2.5s entre chaque écho
ECHO_DUREE_REVEAL = 600         # Durée révélation progressive (ms)

# -- Paramètres de l'Écho Directionnel --
PORTEE_ECHO_DIR = PORTEE_ECHO * 2   # 500px (portée double)
COOLDOWN_ECHO_DIR = 4000            # 4s de cooldown indépendant
ECHO_DIR_DEMI_ANGLE = 25           # ±15° autour de la direction (cône de 30°)

# -- Âmes libres --
ARGENT_AME_LIBRE = 5
COULEUR_AME_LIBRE = (0, 220, 180)  # Turquoise

# -- Clé --
HAVE_KEY = False  # Variable globale, mise à True quand le joueur ramasse une clé

# -- Paramètres Réseau --
PORT_SERVEUR = 5555

# -- Paramètres de la Caméra --
ZOOM_CAMERA = 2.5

# -- Torche --
COULEUR_TORCHE = (255, 140, 30)
RAYON_LUMIERE_TORCHE = 120
DISTANCE_TORCHE_ECHO = 30

# -- Visibilité ennemis --
DISTANCE_DETECTION_ENNEMI = 120  # pixels, ennemi visible si joueur proche
DUREE_FLASH_ECHO_ENNEMI = 1500   # ms, durée d'apparition après écho

# -- Halo joueur --
RAYON_HALO_JOUEUR = 80

# -- Debug --
MODE_DEV = False  # Passer à False pour désactiver le compteur FPS/debug et à True pour l'activer
HALOS_MENU = False  # Passer à False pour désactiver les halos animés des menus
FOND_MENU = False  # Passer à False pour un fond noir uni


TICK_RATE_RESEAU = 30  # envois réseau par seconde (vs 60 pour la physique)