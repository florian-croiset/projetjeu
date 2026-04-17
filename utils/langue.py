# langue.py
# Gère l'internationalisation (i18n) du jeu.
# CORRECTION : Ajout des textes pour la popup de confirmation et le changement de langue.

# Dictionnaire des textes en Français
FR = {
    "titre_jeu": "Écho",
    
    # Menu Principal
    "menu_heberger": "Héberger une partie",
    "menu_rejoindre": "Rejoindre une partie",
    "menu_parametres": "Paramètres",
    "menu_quitter": "Quitter",
    "menu_nouvelle_partie": "Nouvelle Partie",
    "menu_continuer": "Continuer",

    # Menu Slots
    "slots_titre_nouvelle": "Choisir un emplacement",
    "slots_titre_continuer": "Charger une partie",
    "slots_lancer": "Lancer",
    "slots_confirmer_ecraser": "Cette sauvegarde existe. Écraser ?",

    # Menu Rejoindre
    "rejoindre_titre": "Rejoindre une partie",
    "rejoindre_label_ip": "Entrez l'IP de l'hôte (vide pour 'localhost'):",
    "rejoindre_label_code": "Entrez le code room :",
    "rejoindre_connecter": "Se connecter",
    "rejoindre_retour": "Retour",
    "rejoindre_mode_ip": "Mode : IP directe",
    "rejoindre_mode_code": "Mode : Code Room",
    "rejoindre_code_invalide": "Code invalide",
    "rejoindre_label_ip_relay": "IP de l'hôte :",
    "param_code_room_label": "Code partie :",
    "param_code_room_vide": "Partie non lancée",

    # Menu Pause
    "pause_titre": "Pause",
    "pause_reprendre": "Reprendre",
    "pause_parametres": "Paramètres",
    "pause_quitter_session": "Quitter la session",
    "pause_terminer_session": "Mettre fin à la session",

    # Menu Paramètres
    "param_titre": "Paramètres",
    "param_section_jouabilite": "--- Jouabilité ---",
    "param_langue": "Langue : Français",
    "param_section_reseau": "--- Réseau ---",
    "param_section_video": "--- Vidéo ---",
    "param_resolution": "Résolution",
    "param_plein_ecran": "Plein écran",
    "param_vsync": "VSync (Non implémenté)",
    "param_luminosite": "Luminosité",
    "param_luminosite_titre": "Ajuster la luminosité",
    "param_luminosite_aide": "Glissez le curseur, puis Appliquer",
    "param_section_controles": "--- Contrôles ---",
    "param_gauche": "Gauche",
    "param_droite": "Droite",
    "param_saut": "Saut",
    "param_echo": "Écho",
    "param_attaque": "Attaque",
    "param_dash": "Dash",
    "param_echo_dir": "Écho Directionnel",
    "param_appliquer": "Appliquer",
    "param_retour": "Retour",
    "param_attente_touche": "[ ... ]",
    "param_oui": "OUI",
    "param_non": "NON",

    # Popup Confirmation
    "popup_titre": "Attention",
    "popup_message": "Voulez-vous écraser cette sauvegarde ?",
    "popup_oui": "Oui",
    "popup_non": "Non"
}

# Dictionnaire des textes en Anglais
EN = {
    "titre_jeu": "Echo",
    
    # Main Menu
    "menu_heberger": "Host a game",
    "menu_rejoindre": "Join a game",
    "menu_parametres": "Settings",
    "menu_quitter": "Quit",
    "menu_nouvelle_partie": "New Game",
    "menu_continuer": "Continue",

    # Menu Slots
    "slots_titre_nouvelle": "Choose a slot",
    "slots_titre_continuer": "Load a game",
    "slots_lancer": "Launch",
    "slots_confirmer_ecraser": "This save exists. Overwrite?",

    # Join Menu
    "rejoindre_titre": "Join a game",
    "rejoindre_label_ip": "Enter host IP (empty for 'localhost'):",
    "rejoindre_label_code": "Enter room code:",
    "rejoindre_connecter": "Connect",
    "rejoindre_retour": "Back",
    "rejoindre_mode_ip": "Mode: Direct IP",
    "rejoindre_mode_code": "Mode: Room Code",
    "rejoindre_code_invalide": "Invalid code",
    "rejoindre_label_ip_relay": "Host IP:",
    "param_code_room_label": "Game code:",
    "param_code_room_vide": "No game running",

    # Pause Menu
    "pause_titre": "Paused",
    "pause_reprendre": "Resume",
    "pause_parametres": "Settings",
    "pause_quitter_session": "Quit Session",
    "pause_terminer_session": "End Session",

    # Settings Menu
    "param_titre": "Settings",
    "param_section_jouabilite": "--- Gameplay ---",
    "param_langue": "Language: English",
    "param_section_reseau": "--- Network ---",
    "param_section_video": "--- Video ---",
    "param_resolution": "Resolution",
    "param_plein_ecran": "Fullscreen",
    "param_vsync": "VSync (Not implemented)",
    "param_luminosite": "Brightness",
    "param_luminosite_titre": "Adjust brightness",
    "param_luminosite_aide": "Drag the slider, then Apply",
    "param_section_controles": "--- Controls ---",
    "param_gauche": "Left",
    "param_droite": "Right",
    "param_saut": "Jump",
    "param_echo": "Echo",
    "param_attaque": "Attack",
    "param_dash": "Dash",
    "param_echo_dir": "Directional Echo",
    "param_appliquer": "Apply",
    "param_retour": "Back",
    "param_attente_touche": "[ ... ]",
    "param_oui": "YES",
    "param_non": "NO",

    # Popup Confirmation
    "popup_titre": "Warning",
    "popup_message": "Do you want to overwrite this save?",
    "popup_oui": "Yes",
    "popup_non": "No"
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
    langue_actuelle = LANGUES.get(code_langue, FR)

def get_texte(cle):
    """Récupère un texte par sa clé dans la langue actuelle."""
    return langue_actuelle.get(cle, cle)