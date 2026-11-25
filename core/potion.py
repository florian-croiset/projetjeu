# potion.py
# Potions dropped by enemies.

import pygame
import sys
import os
import math


# ---------------------------------------------------------------------------
# Sprite loading
# ---------------------------------------------------------------------------

def _get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(__file__))


def _load_sprite_potion(name_file, size):
    try:
        path = os.path.join(_get_base_path(), 'assets', name_file)
        img = pygame.image.load(path).convert_alpha()
        return pygame.transform.scale(img, size)
    except Exception as e:
        print(f"[POTION] cannot load {name_file}: {e}")
        return None


# Lazy loading (after pygame.display init)
_SPRITES = {}

def _load_sprites_si_needed():
    global _SPRITES
    if _SPRITES:
        return
    _SPRITES = {
        'small': _load_sprite_potion('Small_Potion.png', (32, 32)),
        'large': _load_sprite_potion('Large_Potion.png', (32, 32)),
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEAL_SMALL_POTION = 1
HEAL_LARGE_POTION = 2


# ---------------------------------------------------------------------------
# Potion class
# ---------------------------------------------------------------------------

class Potion:
    """
    Potion dropped in the world, picked up automatically on contact.

    Parameters
    ----------
    x, y    : spawn position (center of the potion)
    type    : 'small' or 'large'
    """

    def __init__(self, x, y, type_potion='small'):
        _load_sprites_si_needed()

        self.type = type_potion
        self.heal = HEAL_SMALL_POTION if type_potion == 'small' else HEAL_LARGE_POTION
        self.sprite = _SPRITES.get(type_potion)

        size = 32
        self.rect = pygame.Rect(0, 0, size, size)
        self.rect.center = (x, y)

        self.active = True  # False = to be removed from the list

        # Small floating animation
        self._offset_y = 0.0
        self._time = 0.0

    def update(self, dt_ms, players):
        """
        Check the collision with each player and heal on contact.
        dt_ms   : milliseconds elapsed since the last tick
        players : list of Player objects (with .rect, .hp and .max_hp)
        Returns the list of (player, healing_applied) for this tick.
        """
        if not self.active:
            return []

        # Floating animation
        self._time += dt_ms * 0.003  # speed
        self._offset_y = 3.0 * math.cos(self._time)

        heals = []
        for player in players:
            if self.rect.colliderect(player.rect):
                # Only heal if the player is not at max
                if player.hp < player.max_hp:
                    heal_real = min(self.heal, player.max_hp - player.hp)
                    player.hp += heal_real
                    heals.append((player, heal_real))
                    self.active = False
                    break
        return heals

    def draw(self, surface, camera_offset=(0, 0)):
        if not self.active:
            return
        off_x, off_y = camera_offset
        pos = (
            self.rect.x - off_x,
            self.rect.y - off_y + int(self._offset_y),
        )
        if self.sprite:
            surface.blit(self.sprite, pos)
        else:
            # Fallback: colored circle
            color = (255, 80, 80) if self.type == 'small' else (200, 0, 255)
            pygame.draw.circle(surface, color,
                               (pos[0] + self.rect.width // 2,
                                pos[1] + self.rect.height // 2),
                               self.rect.width // 2)


# ---------------------------------------------------------------------------
# Potion manager (used server side)
# ---------------------------------------------------------------------------

class PotionManager:
    """
    Keeps the list of active potions and exposes the methods
    to drop, update and draw them.

    Typical server-side usage
    -------------------------
    # In the game loop:
    self.potions.update(dt, players)

    # When an enemy dies:
    self.potions.drop(enemy.rect.centerx, enemy.rect.centery,
                      type_potion='small')   # or 'large'
    """

    def __init__(self):
        self.potions: list[Potion] = []

    def drop(self, x, y, type_potion='small'):
        """Create a new potion at the given position."""
        self.potions.append(Potion(x, y, type_potion))

    def update(self, dt_ms, players):
        """Update every potion and remove the picked-up ones."""
        for potion in self.potions:
            potion.update(dt_ms, players)
        self.potions = [p for p in self.potions if p.active]

    def draw(self, surface, camera_offset=(0, 0)):
        for potion in self.potions:
            potion.draw(surface, camera_offset)

    def get_state(self):
        """Serialise the potions for network sending."""
        return [
            {
                'x': p.rect.centerx,
                'y': p.rect.centery,
                'type': p.type,
            }
            for p in self.potions if p.active
        ]

    def set_state(self, data):
        """
        Rebuild the list client side from the network data.
        Simple resync: the potions are recreated from scratch each time.
        """
        _load_sprites_si_needed()
        self.potions = [Potion(d['x'], d['y'], d['type']) for d in data]
