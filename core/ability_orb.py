# core/ability_orb.py
# Single-use orbs that permanently unlock an ability (dash or double jump).
# Picked up by touching the player. Persisted in the save through the upgrades.

import pygame
import math
from utils.cache import get_font_default, render_text, label_bg
from utils.i18n import get_text


# Colors and icons per ability type
_CONFIG_ABILITIES = {
    'double_jump': {
        'color':  (80, 160, 255),    # Sky blue
        'color2': (120, 200, 255),
        'icon':    '⬆',
        'name':      'Double Saut',
    },
    'dash': {
        'color':  (180, 80, 255),    # Violet
        'color2': (220, 140, 255),
        'icon':    '»',
        'name':      'Dash',
    },
}


COST_PER_ABILITY = {'double_jump': 30, 'dash': 50}


class AbilityOrb:
    """
    Floating orb that unlocks an ability when the player touches it.
    Single use (disappears once picked up).
    """

    RADIUS = 14   # radius of the pickup hitbox (pixels)

    _next_id = 0

    def __init__(self, x: int, y: int, ability: str):
        """
        x, y      : center of the orb in pixels (world coordinates).
        ability   : 'double_jump' or 'dash'.
        """
        self.id       = AbilityOrb._next_id
        AbilityOrb._next_id += 1

        self.x_base   = float(x)
        self.y_base   = float(y)
        self.ability = ability
        self.phase    = (self.id * 1.57) % (2 * math.pi)

        cfg = _CONFIG_ABILITIES.get(ability, _CONFIG_ABILITIES['dash'])
        self.color  = cfg['color']
        self.color2 = cfg['color2']
        self.icon    = cfg['icon']
        self.name      = cfg['name']

        # Pickup rect (fixed on the base position: server-side collision
        # does not depend on the cosmetic floating).
        self.rect = pygame.Rect(x - self.RADIUS, y - self.RADIUS,
                                self.RADIUS * 2, self.RADIUS * 2)

        self.is_picked_up = False

    # ------------------------------------------------------------------
    # SERVER LOGIC
    # ------------------------------------------------------------------

    def update(self, time_ms: int):
        """Floating animation (client side only)."""
        offset_y = math.sin(time_ms / 700 + self.phase) * 5.0
        self.rect.centery = int(self.y_base + offset_y)
        self.rect.centerx = int(self.x_base)

    def try_collect(self, player) -> bool:
        if self.is_picked_up:
            return False
        if self.ability == 'double_jump' and player.can_double_jump:
            return False
        if self.ability == 'dash' and player.can_dash:
            return False

        # Cost in souls (double jump 30, dash 50)
        cost = COST_PER_ABILITY.get(self.ability, 50)
        if player.money < cost:
            return False

        player.money -= cost
        self.is_picked_up = True

        if self.ability == 'double_jump':
            player.can_double_jump = True
            print(f"[ORB] player {player.id} unlocked: double jump")
        elif self.ability == 'dash':
            player.can_dash = True
            print(f"[ORB] player {player.id} unlocked: dash")

        player.sounds_to_play.append('free_soul')
        return True

    # ------------------------------------------------------------------
    # NETWORK
    # ------------------------------------------------------------------

    def get_state(self) -> dict:
        # The (fixed) BASE position is sent. The floating animation
        # is replayed client side through update() on every frame.
        return {
            'id':          self.id,
            'x':           int(self.x_base),
            'y':           int(self.y_base),
            'ability':    self.ability,
            'is_picked_up': self.is_picked_up,
        }

    def set_state(self, data: dict):
        self.x_base       = float(data['x'])
        self.y_base       = float(data['y'])
        self.rect.centerx = int(self.x_base)
        self.rect.centery = int(self.y_base)
        self.ability     = data['ability']
        self.is_picked_up  = data['is_picked_up']

    # ------------------------------------------------------------------
    # CLIENT RENDERING
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, camera_offset=(0, 0), time_ms: int = 0):
        """Draw the orb with a pulsing halo and an icon."""
        if self.is_picked_up:
            return

        off_x, off_y = camera_offset
        cx = self.rect.centerx - off_x
        cy = self.rect.centery - off_y

        pulse = 0.65 + 0.35 * math.sin(time_ms / 500 + self.phase)
        r, g, b = self.color
        r2, g2, b2 = self.color2

        # --- Outer halo (reused surface) ---
        if not hasattr(self, '_halo_surf'):
            self._halo_surf = pygame.Surface((70, 70), pygame.SRCALPHA)
        self._halo_surf.fill((0, 0, 0, 0))
        for radius, alpha_base in [(32, 12), (24, 25), (16, 45)]:
            a = int(alpha_base * pulse)
            pygame.draw.circle(self._halo_surf, (r, g, b, a), (35, 35), radius)
        surface.blit(self._halo_surf, (cx - 35, cy - 35))

        # --- Orb body (reused surface) ---
        if not hasattr(self, '_body_surf'):
            self._body_surf = pygame.Surface(
                (self.RADIUS * 2 + 4, self.RADIUS * 2 + 4), pygame.SRCALPHA)
        self._body_surf.fill((0, 0, 0, 0))
        # Outer circle
        pygame.draw.circle(self._body_surf, (r, g, b, 200),
                           (self.RADIUS + 2, self.RADIUS + 2), self.RADIUS)
        # Inner reflection
        pygame.draw.circle(self._body_surf, (r2, g2, b2, 160),
                           (self.RADIUS + 2 - 3, self.RADIUS + 2 - 3), self.RADIUS - 4)
        # Glowing edge
        pygame.draw.circle(self._body_surf, (r2, g2, b2, 220),
                           (self.RADIUS + 2, self.RADIUS + 2), self.RADIUS, width=2)
        surface.blit(self._body_surf, (cx - self.RADIUS - 2, cy - self.RADIUS - 2))

        # --- Central icon (font + memoised text) ---
        font = get_font_default(30)
        icon_surf = render_text(font, self.icon, (255, 255, 255))
        icon_rect = icon_surf.get_rect(center=(cx, cy))
        surface.blit(icon_surf, icon_rect)

        # --- Label above ---
        font_name = get_font_default(24)
        name_surf = render_text(font_name, self.name, (r2, g2, b2))
        name_rect = name_surf.get_rect(center=(cx, cy - self.RADIUS - 10))
        surface.blit(label_bg(name_rect.width + 8, name_rect.height + 4),
                     (name_rect.x - 4, name_rect.y - 2))
        surface.blit(name_surf, name_rect)

        # Price in souls
        cost = 50
        price_surf = render_text(font_name, get_text("orb_price").format(cost=cost), (200, 160, 255))
        price_rect = price_surf.get_rect(center=(cx, cy - self.RADIUS - 22))
        surface.blit(label_bg(price_rect.width + 8, price_rect.height + 4),
                     (price_rect.x - 4, price_rect.y - 2))
        surface.blit(price_surf, price_rect)