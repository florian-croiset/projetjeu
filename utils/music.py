# music.py
# Module singleton — gestion de la musique de fond et des SFX.
# Usage :
#   import music
#   music.init(parametres)        # une seule fois au démarrage
#   music.demarrer()              # lance la musique de fond
#   music.jouer_sfx('saut')       # joue un son court
#   music.torche_allumer()        # son allumage + boucle flamme
#   music.torche_eteindre()       # arrête boucle flamme + son extinction
#
# Formats supportés pour les SFX : .mp3, .ogg, .wav (détection automatique)
# Dossier SFX attendu : assets/sounds/

import pygame
import os
import sys

# ======================================================================
#  ÉTAT INTERNE (privé)
# ======================================================================

_musique_ok      = False
_musique_jouee   = False
_musique_activee = True
_sfx_actifs      = True
_volume_sfx      = 0.8
_volume_musique  = 0.5

# Cache des SFX : { 'saut': pygame.mixer.Sound, ... }
_sons: dict = {}

# Index de rotation pour les sons d'attaque joueur
_slash_joueur_idx = 0

# Channel dédié à la boucle de flamme (torche)
_channel_torche: pygame.mixer.Channel = None

# Noms de base des SFX (sans extension — détectée automatiquement)
_LISTE_SFX = {
    'saut':           'saut', # DONE
    'double_saut':    'double_saut', # DONE
    'dash':           'dash',
    'attaque':        'Slash1',
    'slash2':         'Slash2',
    'slash3':         'Slash3',
    'porte':          'Audio_porte',
    'slash_boss':     'SlashBoss1',
    'degat':          'degat', # DONE
    'mort':           'mort', # DONE
    'ennemi_mort':    'ennemi_mort', # DONE
    'ennemi_degat':   'ennemi_degat',
    'ame_libre':      'ame_libre',
    'ame_perdue':     'ame_perdue',
    'echo':           'echo',
    'echo_dir':       'echo_dir',
    'cle':            'cle',
    'torche_boucle':  'torche_boucle', # DONE
    'checkpoint':     'checkpoint',
}

_EXTENSIONS = ['.mp3', '.ogg', '.wav']

# Volume personnalisé par son (0.0 → 1.0) — si absent, utilise _volume_sfx
_VOLUMES_SFX = {
    'saut':        0.2,   # trop fort de base → on baisse
    'double_saut':        0.4,
}

def _get_base() -> str:
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ======================================================================
#  INITIALISATION
# ======================================================================

def init(parametres: dict):
    """
    Initialise le mixer et charge musique + SFX.
    À appeler APRÈS pygame.init() et APRÈS charger_parametres().
    """
    global _musique_ok, _musique_jouee, _sfx_actifs, _volume_sfx
    global _volume_musique, _musique_activee, _channel_torche

    sons_params      = parametres.get('sons', {})
    _sfx_actifs      = sons_params.get('activer_sfx', True)
    _volume_sfx      = float(sons_params.get('volume_sfx', 0.8))
    _volume_musique  = float(sons_params.get('volume_musique', 0.5))
    _musique_activee = parametres.get('video', {}).get('musique', True)

    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        # Réserver au moins 8 channels (1 sera dédié à la torche)
        pygame.mixer.set_num_channels(8)
        _channel_torche = pygame.mixer.Channel(7)  # channel 7 = torche
    except Exception as e:
        print(f'[MUSIC] Impossible d\'initialiser le mixer : {e}')
        return

    _charger_musique()
    _charger_sfx()


def _charger_musique():
    global _musique_ok, _musique_jouee
    try:
        chemin = os.path.join(_get_base(), 'assets', 'musique.mp3')
        pygame.mixer.music.load(chemin)
        pygame.mixer.music.set_volume(_volume_musique)
        _musique_ok    = True
        _musique_jouee = False
        print(f'[MUSIC] Musique chargée : {chemin}')
    except Exception as e:
        print(f'[MUSIC] Impossible de charger musique.mp3 : {e}')
        _musique_ok = False


def _charger_sfx():
    global _sons
    base_sons = os.path.join(_get_base(), 'assets', 'sounds')
    for nom, base in _LISTE_SFX.items():
        charge = False
        for ext in _EXTENSIONS:
            chemin = os.path.join(base_sons, base + ext)
            if not os.path.exists(chemin):
                continue
            try:
                son = pygame.mixer.Sound(chemin)
                son.set_volume(_VOLUMES_SFX.get(nom, _volume_sfx))
                _sons[nom] = son
                charge = True
                break
            except Exception as e:
                print(f'[MUSIC] Erreur chargement {chemin} : {e}')
        if not charge:
            _sons[nom] = None


# ======================================================================
#  MUSIQUE DE FOND
# ======================================================================

# ======================================================================
#  MUSIQUE DE FOND
# ======================================================================

def demarrer():
    """Lance la musique si activée dans les paramètres — appelé à l'entrée en jeu."""
    global _musique_jouee
    if _musique_ok and _musique_activee:
        if not _musique_jouee:
            pygame.mixer.music.play(-1)
            _musique_jouee = True
        else:
            pygame.mixer.music.unpause()


def pause():
    """Pause temporaire (menu pause) — ne change pas _musique_activee."""
    if _musique_ok and _musique_jouee:
        pygame.mixer.music.pause()


def reprendre():
    """Reprend après une pause temporaire — seulement si activée."""
    if _musique_ok and _musique_jouee and _musique_activee:
        pygame.mixer.music.unpause()


def toggle(activer: bool):
    """Appliqué uniquement au clic sur 'Appliquer' dans les paramètres."""
    global _musique_jouee, _musique_activee
    _musique_activee = activer
    if not _musique_ok:
        return
    if activer:
        # Ne relance que si on est en jeu (musique déjà initialisée)
        if _musique_jouee:
            pygame.mixer.music.unpause()
        # Si pas encore jouée, demarrer() s'en chargera à l'entrée en jeu
    else:
        pygame.mixer.music.pause()
        # NE PAS mettre _musique_jouee = False — on garde la trace
        # pour savoir qu'elle avait été lancée et peut reprendre


# ======================================================================
#  TORCHE — boucle flamme + audio spatial 2D
# ======================================================================

# Distance max au-delà de laquelle la torche est inaudible (en pixels monde)
TORCHE_DISTANCE_MAX = 1000

# Volume actuel du channel torche (pour le lissage progressif)
_volume_torche_actuel = 0.0


def torche_boucle_start():
    """Démarre la boucle de flamme à volume 0 (le volume monte via torche_mettre_a_jour_volume)."""
    global _volume_torche_actuel
    if not _sfx_actifs:
        return
    son = _sons.get('torche_boucle')
    if son and _channel_torche:
        _channel_torche.set_volume(0.0)
        _channel_torche.play(son, loops=-1)
        _volume_torche_actuel = 0.0


def torche_boucle_stop():
    """Arrête immédiatement la boucle de flamme."""
    global _volume_torche_actuel
    if _channel_torche:
        _channel_torche.stop()
    _volume_torche_actuel = 0.0


def torche_mettre_a_jour_volume(dist_pixels: float):
    """
    Appelé chaque frame depuis client.py avec la distance joueur↔torche.
    Calcule le volume cible et lisse la transition progressivement.

    dist_pixels : distance euclidienne en pixels (coordonnées monde, avant zoom).
    """
    global _volume_torche_actuel
    if not _channel_torche or not _sfx_actifs:
        return

    # Volume cible : 1.0 à distance 0, 0.0 à TORCHE_DISTANCE_MAX
    # Courbe douce avec clamp
    ratio = max(0.0, 1.0 - dist_pixels / TORCHE_DISTANCE_MAX)
    volume_cible = ratio ** 1.5 * _volume_sfx  # courbe légèrement convexe

    # Lissage : interpolation vers la cible (vitesse ~5% par frame à 60fps)
    vitesse = 0.05
    _volume_torche_actuel += (volume_cible - _volume_torche_actuel) * vitesse
    _volume_torche_actuel = max(0.0, min(1.0, _volume_torche_actuel))

    _channel_torche.set_volume(_volume_torche_actuel)


# ======================================================================
#  SFX GÉNÉRIQUES
# ======================================================================

def jouer_sfx(nom: str):
    """Joue un son court par nom. Silencieux si SFX désactivés ou manquant."""
    if not _sfx_actifs:
        return
    son = _sons.get(nom)
    if son is not None:
        son.play()


def jouer_sfx_slash_joueur():
    """Joue un son d'attaque joueur en rotation : Slash1 → Slash2 → Slash3 → ..."""
    global _slash_joueur_idx
    if not _sfx_actifs:
        return
    noms = ['attaque', 'slash2', 'slash3']
    nom = noms[_slash_joueur_idx % 3]
    _slash_joueur_idx += 1
    son = _sons.get(nom)
    if son is not None:
        son.play()


def set_volume_sfx(volume: float):
    global _volume_sfx
    _volume_sfx = max(0.0, min(1.0, volume))
    for son in _sons.values():
        if son is not None:
            son.set_volume(_volume_sfx)
    if _channel_torche:
        _channel_torche.set_volume(_volume_sfx)


def set_volume_musique(volume: float):
    global _volume_musique
    _volume_musique = max(0.0, min(1.0, volume))
    if _musique_ok:
        pygame.mixer.music.set_volume(_volume_musique)


def activer_sfx(actif: bool):
    global _sfx_actifs
    _sfx_actifs = actif
    # Si on désactive les SFX, couper aussi la boucle torche
    if not actif and _channel_torche:
        _channel_torche.stop()