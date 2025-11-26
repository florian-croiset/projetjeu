# langue.py
# Gère l'internationalisation (i18n) du jeu.

# Dictionnaire des textes en Français
FR = {
    "titre_jeu": "Metroidvania - Écho",
    
    # Menu Principal
    "menu_heberger": "Héberger une partie",
    "menu_rejoindre": "Rejoindre une partie",
    "menu_parametres": "Paramètres",
    "menu_quitter": "Quitter",
    "menu_nouvelle_partie": "Nouvelle Partie",
    "menu_continuer": "Continuer",

    # Menu Slots (Nouvelle Partie / Continuer)
    "slots_titre_nouvelle": "Choisir un emplacement",
    "slots_titre_continuer": "Charger une partie",
    "slots_lancer": "Lancer",
    "slots_confirmer_ecraser": "Cette sauvegarde existe. Écraser ?",

    # Menu Rejoindre
    "rejoindre_titre": "Rejoindre une partie",
    "rejoindre_label_ip": "Entrez l'IP de l'hôte (vide pour 'localhost'):",
    "rejoindre_connecter": "Se connecter",
    "rejoindre_retour": "Retour",

    # Menu Pause
    "pause_titre": "Pause",
    "pause_reprendre": "Reprendre",
    "pause_parametres": "Paramètres",
    "pause_quitter_session": "Quitter la session",
    "pause_terminer_session": "Mettre fin à la session",

    # Menu Paramètres
    "param_titre": "Paramètres",
    "param_section_jouabilite": "--- Jouabilité ---",
    "param_langue": "Langue",
    "param_section_video": "--- Vidéo ---",
    "param_plein_ecran": "Plein écran",
    "param_vsync": "VSync (Non implémenté)",
    "param_section_controles": "--- Contrôles ---",
    "param_gauche": "Gauche",
    "param_droite": "Droite",
    "param_saut": "Saut",
    "param_echo": "Écho",
    "param_appliquer": "Appliquer",
    "param_retour": "Retour",
    "param_attente_touche": "[ ... ]",
    "param_oui": "OUI",
    "param_non": "NON"
}

# Dictionnaire des textes en Anglais
EN = {
    "titre_jeu": "Metroidvania - Echo",
    
    # Main Menu
    "menu_heberger": "Host a game",
    "menu_rejoindre": "Join a game",
    "menu_parametres": "Settings",
    "menu_quitter": "Quit",
    "menu_nouvelle_partie": "New Game",
    "menu_continuer": "Continue",

    # Menu Slots (New Game / Continue)
    "slots_titre_nouvelle": "Choose a slot",
    "slots_titre_continuer": "Load a game",
    "slots_lancer": "Launch",
    "slots_confirmer_ecraser": "This save exists. Overwrite?",

    # Join Menu
    "rejoindre_titre": "Join a game",
    "rejoindre_label_ip": "Enter host IP (empty for 'localhost'):",
    "rejoindre_connecter": "Connect",
    "rejoindre_retour": "Back",

    # Pause Menu
    "pause_titre": "Paused",
    "pause_reprendre": "Resume",
    "pause_parametres": "Settings",
    "pause_quitter_session": "Quit Session",
    "pause_terminer_session": "End Session",

    # Settings Menu
    "param_titre": "Settings",
    "param_section_jouabilite": "--- Gameplay ---",
    "param_langue": "Language",
    "param_section_video": "--- Video ---",
    "param_plein_ecran": "Fullscreen",
    "param_vsync": "VSync (Not implemented)",
    "param_section_controles": "--- Controls ---",
    "param_gauche": "Left",
    "param_droite": "Right",
    "param_saut": "Jump",
    "param_echo": "Echo",
    "param_appliquer": "Apply",
    "param_retour": "Back",
    "param_attente_touche": "[ ... ]",
    "param_oui": "YES",
    "param_non": "NO"
}

# Stocke tous les dictionnaires de langue
LANGUES = {
    "fr": FR,
    "en": EN
}

# Langue actuellement sélectionnée (par défaut 'fr')
langue_actuelle = FR

def set_langue(code_langue="fr"):
    """Définit la langue globale à utiliser."""
    global langue_actuelle
    # Si la langue demandée n'existe pas, on garde le français par défaut
    langue_actuelle = LANGUES.get(code_langue, FR)

def get_texte(cle):
    """Récupère un texte par sa clé dans la langue actuelle."""
    # Si la clé n'est pas trouvée, on la renvoie elle-même pour voir l'erreur
    return langue_actuelle.get(cle, cle)