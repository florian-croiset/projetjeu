# slider.py
# Horizontal slider in the Echo art direction (neon cyan, glow on hover).

import pygame
from settings import (COLOR_CYAN, COLOR_CYAN_LIGHT, COLOR_CYAN_DARK,
                        COLOR_TEXT, COLOR_BUTTON)


class Slider:
    def __init__(self, x, y, width, height, value=0.5, font=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.value = max(0.0, min(1.0, float(value)))
        self.font = font
        self.is_hovered = False
        self._drag = False

    # ------------------------------------------------------------------
    def _radius_knob(self):
        return max(10, self.rect.height // 2 + 2)

    def _x_knob(self):
        return self.rect.x + int(self.value * self.rect.width)

    def _knob_rect(self):
        r = self._radius_knob()
        return pygame.Rect(self._x_knob() - r, self.rect.centery - r, r * 2, r * 2)

    # ------------------------------------------------------------------
    def _value_since_x(self, x_mouse):
        if self.rect.width <= 0:
            return 0.0
        rel = (x_mouse - self.rect.x) / self.rect.width
        return max(0.0, min(1.0, rel))

    # ------------------------------------------------------------------
    def verify_hover(self, pos_mouse):
        zone = self.rect.inflate(0, self._radius_knob() * 2)
        self.is_hovered = zone.collidepoint(pos_mouse) or self._knob_rect().collidepoint(pos_mouse)

    def handle_event(self, event):
        """Return True if the value changed."""
        old = self.value
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zone = self.rect.inflate(0, self._radius_knob() * 2)
            if zone.collidepoint(event.pos) or self._knob_rect().collidepoint(event.pos):
                self._drag = True
                self.value = self._value_since_x(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            self.value = self._value_since_x(event.pos[0])
        return self.value != old

    # ------------------------------------------------------------------
    def draw(self, surface):
        hovered = self.is_hovered or self._drag

        # --- Outer glow on hover ---
        if hovered:
            r, g, b = COLOR_CYAN
            glow = pygame.Surface((self.rect.width + 16, self.rect.height + 16),
                                  pygame.SRCALPHA)
            for i, alpha in enumerate([15, 30, 50]):
                margin = 8 - i * 2
                pygame.draw.rect(
                    glow, (r, g, b, alpha),
                    pygame.Rect(margin // 2, margin // 2,
                                self.rect.width + 8 - margin,
                                self.rect.height + 8 - margin),
                    border_radius=self.rect.height // 2 + margin
                )
            surface.blit(glow, (self.rect.x - 8, self.rect.y - 8))

        # --- Track (bar background) ---
        pygame.draw.rect(surface, COLOR_BUTTON, self.rect,
                         border_radius=self.rect.height // 2)
        pygame.draw.rect(surface, COLOR_CYAN_DARK, self.rect,
                         width=1, border_radius=self.rect.height // 2)

        # --- Filled portion (left of the knob) ---
        fill_w = max(0, self._x_knob() - self.rect.x)
        if fill_w > 0:
            rect_fill = pygame.Rect(self.rect.x, self.rect.y,
                                    fill_w, self.rect.height)
            pygame.draw.rect(surface, COLOR_CYAN_DARK, rect_fill,
                             border_radius=self.rect.height // 2)
            inner = rect_fill.inflate(-2, -2)
            if inner.width > 0:
                pygame.draw.rect(surface, COLOR_CYAN, inner,
                                 border_radius=self.rect.height // 2)

        # --- Knob ---
        radius = self._radius_knob()
        cx_knob = self._x_knob()
        cy_knob = self.rect.centery
        color_knob = COLOR_CYAN_LIGHT if hovered else COLOR_CYAN
        pygame.draw.circle(surface, (8, 8, 20), (cx_knob, cy_knob), radius)
        pygame.draw.circle(surface, color_knob, (cx_knob, cy_knob),
                           radius, width=2)
        pygame.draw.circle(surface, color_knob, (cx_knob, cy_knob),
                           max(3, radius - 5))

        # --- Percentage label, above the knob ---
        if self.font is not None:
            txt = f"{int(round(self.value * 100))} %"
            surf_txt = self.font.render(txt, True, COLOR_TEXT)
            rect_txt = surf_txt.get_rect(midbottom=(cx_knob, self.rect.y - 8))
            surface.blit(surf_txt, rect_txt)
