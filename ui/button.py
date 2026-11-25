# button.py
# Button class in the visual style of the Echo art direction (Team Nightberry).
# Design: dark background, neon cyan border, glow effect on hover.

import pygame
from settings import *


class Button:
    def __init__(self, x, y, width, height, text, font,
                 style="normal"):
        """
        style:
          "normal"  - standard cyan/dark button
          "danger"  - red button (negative confirmation)
          "confirm" - violet button (positive confirmation)
          "ghost"   - transparent / disabled button
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.style = style
        self.is_hovered = False

        # Colors per style
        self._define_style(style)

    # ------------------------------------------------------------------
    def _define_style(self, style):
        if style == "danger":
            self.color_background        = (20, 5, 10)
            self.color_background_hover = (40, 10, 20)
            self.color_border     = (220, 50, 50)
            self.color_border_hover = (255, 90, 90)
            self.color_text       = (220, 50, 50)
            self.color_text_hover = (255, 110, 110)

        elif style == "confirm":
            self.color_background        = (14, 5, 35)
            self.color_background_hover = (30, 10, 65)
            self.color_border     = COLOR_VIOLET
            self.color_border_hover = COLOR_VIOLET_LIGHT
            self.color_text       = COLOR_VIOLET_LIGHT
            self.color_text_hover = COLOR_WHITE

        elif style == "disabled":
            self.color_background        = (10, 10, 15)
            self.color_background_hover = (10, 10, 15)
            self.color_border     = (30, 30, 40)
            self.color_border_hover = (30, 30, 40)
            self.color_text       = COLOR_TEXT_DARK
            self.color_text_hover = COLOR_TEXT_DARK

        elif style == "ghost":
            self.color_background        = (0, 0, 0, 0)
            self.color_background_hover = (14, 10, 35)
            self.color_border     = (40, 40, 70)
            self.color_border_hover = (80, 80, 110)
            self.color_text       = COLOR_TEXT_DARK
            self.color_text_hover = COLOR_TEXT

        else:  # "normal" - default Echo style
            self.color_background        = COLOR_BUTTON
            self.color_background_hover = COLOR_BUTTON_HOVER
            self.color_border     = COLOR_CYAN_DARK
            self.color_border_hover = COLOR_CYAN
            self.color_text       = COLOR_TEXT
            self.color_text_hover = COLOR_CYAN

    # ------------------------------------------------------------------
    def draw(self, surface):
        """Draw the button on the surface with the Echo neon effect."""
        hovered = self.is_hovered

        background     = self.color_background_hover  if hovered else self.color_background
        border  = self.color_border_hover if hovered else self.color_border
        text_c  = self.color_text_hover if hovered else self.color_text

        # ---- Outer glow (on hover) ------------------------------------
        if hovered and self.style not in ("ghost",):
            glow_surf = pygame.Surface(
                (self.rect.width + 16, self.rect.height + 16),
                pygame.SRCALPHA
            )
            r, g, b = border
            for i, alpha in enumerate([15, 30, 50]):
                margin = 8 - i * 2
                pygame.draw.rect(
                    glow_surf,
                    (r, g, b, alpha),
                    pygame.Rect(margin // 2, margin // 2,
                                self.rect.width + 8 - margin,
                                self.rect.height + 8 - margin),
                    border_radius=10 + margin
                )
            surface.blit(glow_surf, (self.rect.x - 8, self.rect.y - 8))

        # ---- Button background ----------------------------------------
        pygame.draw.rect(surface, background, self.rect, border_radius=8)

        # ---- Neon border (1 px inside + 1 px outside) -----------------
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=8)
        inner = self.rect.inflate(-2, -2)
        r, g, b = border
        pygame.draw.rect(surface, (r, g, b, 60),
                         inner, width=1, border_radius=7)

        # ---- Top highlight line (glassy effect) -----------------------
        if self.style != "ghost":
            reflection = pygame.Surface((self.rect.width - 4, 2), pygame.SRCALPHA)
            reflection.fill((255, 255, 255, 18))
            surface.blit(reflection, (self.rect.x + 2, self.rect.y + 3))

        # ---- Centered text -------------------------------------------
        text_surf = self.font.render(self.text, True, text_c)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    # ------------------------------------------------------------------
    def verify_click(self, event):
        """Return True if the button was clicked (left click)."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def verify_hover(self, pos_mouse):
        """Update the is_hovered state."""
        self.is_hovered = self.rect.collidepoint(pos_mouse)