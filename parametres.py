# parametres.py
# Fichier pour stocker les constantes et paramètres globaux du jeu.
# MISE À JOUR : Couleurs alignées sur la charte graphique Echo (Team Nightberry).

# -- Paramètres de la Fenêtre --
LARGEUR_ECRAN = 1920
HAUTEUR_ECRAN = 1080
TITRE_FENETRE = "Écho - Team Nightberry"
FPS = 60
seconde=1000
minute=60*seconde

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
TEMPS_RESPAWN_ENNEMI = minute*3  # 3 minutes en ms

# -- Paramètres des Capacités --
DISTANCE_DASH = TAILLE_TUILE * 4
DUREE_DASH = 150
COOLDOWN_DASH = 600
DASH_EN_AIR_MAX = 1
FORCE_DOUBLE_SAUT = 10

# -- Paramètres de l'Écho (Raycasting) --
PORTEE_ECHO = 150
NB_RAYONS_ECHO = 360
COOLDOWN_ECHO = 2500            # Réduit : 2.5s entre chaque écho
ECHO_DUREE_REVEAL = 600         # Durée révélation progressive (ms)

# -- Paramètres de l'Écho Directionnel --
PORTEE_ECHO_DIR = PORTEE_ECHO * 2   # 300px (portée double)
COOLDOWN_ECHO_DIR = 4000            # 4s de cooldown indépendant
ECHO_DIR_DEMI_ANGLE = 25           # ±15° autour de la direction (cône de 30°)

# -- Âmes libres --
ARGENT_AME_LIBRE = 5
COULEUR_AME_LIBRE = (0, 220, 180)  # Turquoise

# -- Âmes Loot (butin ennemi) --
COULEUR_AME_LOOT = (0, 200, 160)
VITESSE_BURST_LOOT = 4.0           # Vélocité max initiale de dispersion
REBOND_AMORTISSEMENT = 0.2         # Facteur de rebond sur murs/sol
SEUIL_REPOS_LOOT = 0.5             # Vélocité sous laquelle l'orbe se pose
DUREE_MAX_DISPERSION = 3000        # ms, force repos après ce délai
DUREE_VIE_AME_LOOT = 60000         # ms, despawn après repos

# -- Clé --
HAVE_KEY = False  # Variable globale, mise à True quand le joueur ramasse une clé

# -- Paramètres Réseau --
PORT_SERVEUR = 5555

# -- Relay (connexion par room code) --
RELAY_HOST = ""         # Vide = relay désactivé. Ex: "relay.example.com" ou "1.2.3.4"
RELAY_PORT = 7777

# -- Paramètres de la Caméra --
ZOOM_CAMERA = 2.5

# Toutes les résolutions habituelles, du plus petit au plus grand
RESOLUTIONS_DISPONIBLES = [
    (800, 600),    # SVGA
    (1024, 600),   # WSVGA
    (1280, 720),   # HD
    (1024, 768),   # XGA
    (1280, 768),   # WXGA
    (1366, 768),   # HD (laptop)
    (1280, 800),   # WXGA
    (1152, 864),   # XGA+
    (1536, 864),   # Chromebook
    (1440, 900),   # WXGA+
    (1600, 900),   # HD+
    (1280, 960),   # SXGA-
    (1280, 1024),  # SXGA
    (1600, 1024),  # —
    (1400, 1050),  # SXGA+
    (1680, 1050),  # WSXGA+
    (1920, 1080),  # Full HD
    (2048, 1080),  # 2K DCI
    (2560, 1080),  # Ultra-Wide FHD
    (1920, 1200),  # WUXGA
    (2560, 1440),  # 2K QHD
    (3440, 1440),  # Ultra-Wide QHD
    (2560, 1600),  # WQXGA
    (3840, 2160),  # 4K UHD
]

def get_resolutions_compatibles(resolution_native):
    """Retourne les résolutions ≤ à la résolution native de l'écran."""
    larg_max, haut_max = resolution_native
    return [r for r in RESOLUTIONS_DISPONIBLES if r[0] <= larg_max and r[1] <= haut_max]

# -- Torche --
COULEUR_TORCHE = (255, 140, 30)
RAYON_LUMIERE_TORCHE = 120
DISTANCE_TORCHE_ECHO = 30

# -- Visibilité ennemis --
DISTANCE_DETECTION_ENNEMI = 120  # pixels, ennemi visible si joueur proche
DUREE_FLASH_ECHO_ENNEMI = 1500   # ms, durée d'apparition après écho

# -- Halo joueur --
RAYON_HALO_JOUEUR    = 80   # Rayon total du halo en pixels
HALO_DEGRADE_ETENDUE = 20   # Largeur de la zone de dégradé (= rayon → dégradé sur tout le rayon)
HALO_NB_NIVEAUX      = 0    # 0 = parfait pixel/pixel (numpy), entier > 0 = couches discrètes

# -- Debug --
MODE_DEV = True  # Passer à False pour désactiver le compteur FPS/debug et à True pour l'activer
HALOS_MENU = False  # Passer à False pour désactiver les halos animés des menus
FOND_MENU = False  # Passer à False pour un fond noir uni
REVELATION = False
ASSOMBRISSEMENT = True  # False = tout illuminé sans halo | True = obscurité avec halo autour du joueur
TICK_RATE_RESEAU = 60  # envois réseau par seconde (vs 60 pour la physique)

