# utils/cache.py
# Caches et pré-calculs centralisés pour optimiser le jeu.
#
# Contenu :
#   ┌─ Caches pygame ─────────────────────────────────────────────────────┐
#   │  flip_h(surface)               → surface flippée horizontalement    │
#   │  render_text(font, txt, coul)  → font.render() mémoïsé              │
#   │  get_font_defaut(taille_px)    → pygame.font.Font(None, taille)     │
#   │  get_font_pseudo(taille_px)    → alias de get_font_defaut           │
#   │  creer_textes_echo_hud(fonts)  → surfaces statiques du widget Echo  │
#   │  label_bg(w, h, alpha=120)     → surface de fond semi-transparent   │
#   └─────────────────────────────────────────────────────────────────────┘
#   ┌─ Constantes pré-calculées ─────────────────────────────────────────┐
#   │  DIRECTIONS_ECHO_RADIAL        → vecteurs des rayons radiaux       │
#   │  DIRECTIONS_ECHO_DROITE/GAUCHE → vecteurs des cônes directionnels  │
#   │  RAYON_AUDITION_TRAQUEUR_SQ    → rayon² pour comparaisons rapides  │
#   └────────────────────────────────────────────────────────────────────┘

import math
import pygame

from parametres import (
    COULEUR_CYAN,
    ECHO_DIR_DEMI_ANGLE,
    NB_RAYONS_ECHO,
    RAYON_AUDITION_TRAQUEUR,
)


# ══════════════════════════════════════════════════════════════════════
#  CACHE — SURFACES FLIPPÉES HORIZONTALEMENT
# ══════════════════════════════════════════════════════════════════════
# Clé : id(surface_source). Tant que la surface source reste référencée
# ailleurs (par l'animator), id() ne sera pas réutilisé.
# Si jamais le cache devient trop gros, on le purge entièrement.

_FLIP_H_CACHE: dict = {}
_FLIP_H_MAX = 512


def flip_h(surface: pygame.Surface) -> pygame.Surface:
    """Retourne la version flippée horizontalement de `surface`, mémoïsée."""
    key = id(surface)
    cached = _FLIP_H_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_FLIP_H_CACHE) >= _FLIP_H_MAX:
        _FLIP_H_CACHE.clear()
    flipped = pygame.transform.flip(surface, True, False)
    _FLIP_H_CACHE[key] = flipped
    return flipped


# ══════════════════════════════════════════════════════════════════════
#  CACHE — RENDUS DE TEXTE
# ══════════════════════════════════════════════════════════════════════
# Clé : (id(font), texte, couleur). Évite font.render() pour des textes
# statiques re-rendus à chaque frame (HUD, labels menu).

_TEXT_CACHE: dict = {}
_TEXT_CACHE_MAX = 256


def render_text(font: pygame.font.Font, texte: str, couleur) -> pygame.Surface:
    """font.render mémoïsé. À utiliser pour des textes statiques répétés."""
    coul_key = tuple(couleur) if not isinstance(couleur, tuple) else couleur
    key = (id(font), texte, coul_key)
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_TEXT_CACHE) >= _TEXT_CACHE_MAX:
        _TEXT_CACHE.clear()
    surf = font.render(texte, True, couleur)
    _TEXT_CACHE[key] = surf
    return surf


# ══════════════════════════════════════════════════════════════════════
#  CACHE — FONT PYGAME PAR DÉFAUT (par taille en pixels)
# ══════════════════════════════════════════════════════════════════════
# Utilisé par les pseudos joueurs ET par tous les rendus qui faisaient
# auparavant `pygame.font.Font(None, taille)` à chaque frame (orbes,
# portes, etc.). La construction d'une font Pygame est lente —
# l'instance est partagée par tous les appelants à taille égale.

_FONT_DEFAUT_CACHE: dict = {}


def get_font_defaut(taille_px: int) -> pygame.font.Font:
    """Retourne `pygame.font.Font(None, taille_px)` mémoïsée par taille."""
    font = _FONT_DEFAUT_CACHE.get(taille_px)
    if font is None:
        font = pygame.font.Font(None, taille_px)
        _FONT_DEFAUT_CACHE[taille_px] = font
    return font


# Alias conservé pour la compatibilité : le pseudo joueur utilisait
# historiquement un cache dédié.
get_font_pseudo = get_font_defaut


# ══════════════════════════════════════════════════════════════════════
#  CACHE — SURFACES DE FOND SEMI-TRANSPARENT (« label bg »)
# ══════════════════════════════════════════════════════════════════════
# Petit rectangle SRCALPHA rempli d'une seule couleur uniforme — utilisé
# comme arrière-plan des étiquettes flottantes (orbe, pseudo, etc.).
# La clé inclut la taille ET l'alpha (la couleur de remplissage est
# toujours du noir, c'est le cas réel utilisé partout dans le jeu).

_LABEL_BG_CACHE: dict = {}
_LABEL_BG_MAX = 128


def label_bg(largeur: int, hauteur: int, alpha: int = 120) -> pygame.Surface:
    """Surface noire SRCALPHA (`(0,0,0,alpha)`) mémoïsée par dimensions.

    Réutilisable pour les arrière-plans d'étiquettes — la même
    instance est renvoyée à chaque appel, ne pas la modifier.
    """
    key = (largeur, hauteur, alpha)
    cached = _LABEL_BG_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_LABEL_BG_CACHE) >= _LABEL_BG_MAX:
        _LABEL_BG_CACHE.clear()
    surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
    surf.fill((0, 0, 0, alpha))
    _LABEL_BG_CACHE[key] = surf
    return surf


# ══════════════════════════════════════════════════════════════════════
#  CACHE — SURFACES STATIQUES DU WIDGET ECHO (HUD)
# ══════════════════════════════════════════════════════════════════════
# Les labels « ECHO », « PRÊT » et l'icône « E » (cyan + grisé) sont
# pré-rendus une fois lors de l'initialisation du HUD (et à chaque
# changement de résolution puisque les fonts changent).

def creer_textes_echo_hud(font_label_small: pygame.font.Font,
                          font_label_medium: pygame.font.Font,
                          font_echo_icon: pygame.font.Font) -> dict:
    """Renvoie un dict contenant les surfaces statiques du widget Echo.

    Clés du dict retourné :
      - 'echo_label'  : « ECHO » (petit, gris)
      - 'echo_pret'   : « PRÊT » (moyen, cyan)

    Les icônes de touche (e_pret / e_attente) sont rendues dynamiquement
    via render_text() dans le HUD pour refléter les liaisons de touches.
    """
    return {
        'echo_label': font_label_small.render("ECHO", True, (100, 85, 130)),
        'echo_pret':  font_label_medium.render("PRÊT", True, COULEUR_CYAN),
    }


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTES — VECTEURS DE DIRECTION D'ÉCHO
# ══════════════════════════════════════════════════════════════════════
# Pré-calculés une seule fois au chargement du module ; partagés par
# toutes les instances de Carte.

DIRECTIONS_ECHO_RADIAL = tuple(
    (math.cos(i / NB_RAYONS_ECHO * 2 * math.pi),
     math.sin(i / NB_RAYONS_ECHO * 2 * math.pi))
    for i in range(NB_RAYONS_ECHO)
)

_DEMI_RAD_ECHO = ECHO_DIR_DEMI_ANGLE * math.pi / 180

DIRECTIONS_ECHO_DROITE = tuple(
    (math.cos(-_DEMI_RAD_ECHO + i / (NB_RAYONS_ECHO - 1) * 2 * _DEMI_RAD_ECHO),
     math.sin(-_DEMI_RAD_ECHO + i / (NB_RAYONS_ECHO - 1) * 2 * _DEMI_RAD_ECHO))
    for i in range(NB_RAYONS_ECHO)
)

DIRECTIONS_ECHO_GAUCHE = tuple(
    (math.cos(math.pi - _DEMI_RAD_ECHO + i / (NB_RAYONS_ECHO - 1) * 2 * _DEMI_RAD_ECHO),
     math.sin(math.pi - _DEMI_RAD_ECHO + i / (NB_RAYONS_ECHO - 1) * 2 * _DEMI_RAD_ECHO))
    for i in range(NB_RAYONS_ECHO)
)


# ══════════════════════════════════════════════════════════════════════
#  CONSTANTES — DISTANCES AU CARRÉ (pour éviter math.sqrt)
# ══════════════════════════════════════════════════════════════════════

RAYON_AUDITION_TRAQUEUR_SQ = RAYON_AUDITION_TRAQUEUR * RAYON_AUDITION_TRAQUEUR


# ══════════════════════════════════════════════════════════════════════
#  UTILITAIRE — PURGE
# ══════════════════════════════════════════════════════════════════════

def vider_caches() -> None:
    """Purge tous les caches dynamiques (à appeler si les fonts sont recréées)."""
    _FLIP_H_CACHE.clear()
    _TEXT_CACHE.clear()
    _FONT_DEFAUT_CACHE.clear()
    _LABEL_BG_CACHE.clear()
