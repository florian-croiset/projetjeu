# potion.py
# Gestion des potions droppées par les ennemis.

import pygame
import sys
import os


# ---------------------------------------------------------------------------
# Chargement des sprites
# ---------------------------------------------------------------------------

def _get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))


def _charger_sprite_potion(nom_fichier, taille):
    try:
        path = os.path.join(_get_base_path(), 'assets', nom_fichier)
        print(f"[POTION] Chargement : {path} — existe : {os.path.exists(path)}")
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, taille)
    except Exception as e:
        print(f"[POTION] ERREUR {nom_fichier}: {e}")
        return None


# Chargement lazy (après pygame.display init)
_SPRITES = {}

def _charger_sprites_si_necessaire():
    global _SPRITES
    if _SPRITES:
        return
    _SPRITES = {
        'small': _charger_sprite_potion('Small_Potion.png', (32, 32)),
        'large': _charger_sprite_potion('Large_Potion.png', (32, 32)),
    }


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SOIN_SMALL_POTION = 2
SOIN_LARGE_POTION = 5


# ---------------------------------------------------------------------------
# Classe Potion
# ---------------------------------------------------------------------------

class Potion:
    """
    Potion droppée dans le monde, ramassée automatiquement au contact.

    Paramètres
    ----------
    x, y    : position de spawn (centre de la potion)
    type    : 'small' ou 'large'
    """

    def __init__(self, x, y, type_potion='small'):
        _charger_sprites_si_necessaire()

        self.type = type_potion
        self.soin = SOIN_SMALL_POTION if type_potion == 'small' else SOIN_LARGE_POTION
        self.sprite = _SPRITES.get(type_potion)

        taille = 32
        self.rect = pygame.Rect(0, 0, taille, taille)
        self.rect.center = (x, y)

        self.active = True  # False = à supprimer de la liste

        # Petite animation de flottement
        self._offset_y = 0.0
        self._temps = 0.0

    def mettre_a_jour(self, dt_ms, joueurs):
        """
        Vérifie la collision avec chaque joueur et soigne si contact.
        dt_ms  : millisecondes écoulées depuis le dernier tick
        joueurs: liste d'objets Joueur (avec .rect et .pv et .pv_max)
        Retourne la liste des (joueur, soin_appliqué) ce tick.
        """
        if not self.active:
            return []

        # Animation flottement
        self._temps += dt_ms * 0.003  # vitesse
        self._offset_y = 3 * (pygame.math.Vector2(0, 1).rotate(self._temps * 57.3).y)

        soins = []
        for joueur in joueurs:
            if self.rect.colliderect(joueur.rect):
                # Ne soigne que si le joueur n'est pas au max
                if joueur.pv < joueur.pv_max:
                    soin_reel = min(self.soin, joueur.pv_max - joueur.pv)
                    joueur.pv += soin_reel
                    soins.append((joueur, soin_reel))
                    self.active = False
                    break
        return soins

    def dessiner(self, surface, camera_offset=(0, 0)):
        if not self.active:
            return
        off_x, off_y = camera_offset
        pos = (
            self.rect.x - off_x,
            self.rect.y - off_y + int(self._offset_y),
        )
        print(f"[POTION] Dessin {self.type} à pos écran {pos}")
        if self.sprite:
            surface.blit(self.sprite, pos)
        else:
            # Fallback : cercle coloré
            couleur = (255, 80, 80) if self.type == 'small' else (200, 0, 255)
            pygame.draw.circle(surface, couleur,
                               (pos[0] + self.rect.width // 2,
                                pos[1] + self.rect.height // 2),
                               self.rect.width // 2)


# ---------------------------------------------------------------------------
# Gestionnaire de potions (à utiliser côté serveur)
# ---------------------------------------------------------------------------

class GestionnairePotions:
    """
    Garde la liste des potions actives et expose les méthodes
    pour les faire dropper, mettre à jour et dessiner.

    Utilisation typique côté serveur
    ---------------------------------
        # Dans la boucle de jeu :
        self.potions.mettre_a_jour(dt, joueurs)

        # Quand un ennemi meurt :
        self.potions.dropper(ennemi.rect.centerx, ennemi.rect.centery,
                             type_potion='small')   # ou 'large'
    """

    def __init__(self):
        self.potions: list[Potion] = []

    def dropper(self, x, y, type_potion='small'):
        """Crée une nouvelle potion à la position donnée."""
        self.potions.append(Potion(x, y, type_potion))

    def mettre_a_jour(self, dt_ms, joueurs):
        """Met à jour toutes les potions et supprime celles ramassées."""
        for potion in self.potions:
            potion.mettre_a_jour(dt_ms, joueurs)
        self.potions = [p for p in self.potions if p.active]

    def dessiner(self, surface, camera_offset=(0, 0)):
        for potion in self.potions:
            potion.dessiner(surface, camera_offset)

    def get_etat(self):
        """Sérialise les potions pour l'envoi réseau."""
        return [
            {
                'x': p.rect.centerx,
                'y': p.rect.centery,
                'type': p.type,
            }
            for p in self.potions if p.active
        ]

    def set_etat(self, data):
        """
        Reconstruit la liste côté client depuis les données réseau.
        Simple resync : on recrée les potions depuis zéro chaque tick.
        """
        _charger_sprites_si_necessaire()
        self.potions = [Potion(d['x'], d['y'], d['type']) for d in data]
