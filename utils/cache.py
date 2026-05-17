# utils/cache.py
# Caches et pré-calculs centralisés pour optimiser le jeu.
#
# Contenu :
#   ┌─ Caches pygame ─────────────────────────────────────────────────────┐
#   │  flip_h(surface)               → surface flippée horizontalement    │
#   │  render_text(font, txt, coul)  → font.render() mémoïsé              │
#   │  get_font_pseudo(taille_px)    → font Pygame pour les pseudos       │
#   │  creer_textes_echo_hud(fonts)  → surfaces statiques du widget Echo  │
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
#  CACHE — FONT POUR LES PSEUDOS JOUEURS
# ══════════════════════════════════════════════════════════════════════
# Le pseudo est rendu à une taille proportionnelle au zoom caméra.
# La font Pygame est mise en cache par taille (en pixels).

_FONT_PSEUDO_CACHE: dict = {}


def get_font_pseudo(taille_px: int) -> pygame.font.Font:
    """Retourne la font Pygame par défaut à la taille demandée, mémoïsée."""
    font = _FONT_PSEUDO_CACHE.get(taille_px)
    if font is None:
        font = pygame.font.Font(None, taille_px)
        _FONT_PSEUDO_CACHE[taille_px] = font
    return font


# ══════════════════════════════════════════════════════════════════════
#  CACHE — SURFACES STATIQUES DU WIDGET ECHO (HUD)
# ══════════════════════════════════════════════════════════════════════
# Les labels « ECHO », « PRÊT » et l'icône « E » (cyan + grisé) sont
# pré-rendus une fois lors de l'initialisation du HUD (et à chaque
# changement de résolution puisque les fonts changent).

def creer_textes_echo_hud(font_label_small: pygame.font.Font,
                          font_label_medium: pygame.font.Font,
                          font_echo_icon: pygame.font.Font) -> dict:
    """Renvoie un dict contenant les 4 surfaces statiques du widget Echo.

    Clés du dict retourné :
      - 'echo_label'  : « ECHO » (petit, gris)
      - 'echo_pret'   : « PRÊT » (moyen, cyan)
      - 'e_pret'      : « E » (icône, cyan)
      - 'e_attente'   : « E » (icône, grisé)
    """
    return {
        'echo_label': font_label_small.render("ECHO", True, (100, 85, 130)),
        'echo_pret':  font_label_medium.render("PRÊT", True, COULEUR_CYAN),
        'e_pret':     font_echo_icon.render("E", True, COULEUR_CYAN),
        'e_attente':  font_echo_icon.render("E", True, (100, 80, 140)),
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
    _FONT_PSEUDO_CACHE.clear()
