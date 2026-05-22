import pygame
from parametres import TAILLE_TUILE


class MurPayant:
    PORTEE_INTERACTION = 80

    def __init__(self, tuile_x, tuile_y, cout, message):
        self.x = tuile_x * TAILLE_TUILE
        self.y = tuile_y * TAILLE_TUILE
        self.rect = pygame.Rect(self.x, self.y, TAILLE_TUILE, TAILLE_TUILE)
        self.cout = cout
        self.message = message
        self.debloque = False
        self._font = None

    def _init_font(self):
        if self._font is None:
            self._font = pygame.font.Font(None, 22)

    def tenter_paiement(self, joueur):
        if self.debloque:
            return 'deja_debloque'
        if joueur.argent < self.cout:
            return 'pauvre'
        joueur.argent -= self.cout
        self.debloque = True
        return 'debloque'

    def get_etat(self):
        return {'debloque': self.debloque}

    def set_etat(self, data):
        self.debloque = data.get('debloque', False)

    def dessiner(self, surface, camera_offset, joueur_rect=None):
        if self.debloque:
            return
        if joueur_rect is None:
            return
        dx = joueur_rect.centerx - (self.x + TAILLE_TUILE // 2)
        dy = joueur_rect.centery - (self.y + TAILLE_TUILE // 2)
        if (dx * dx + dy * dy) > self.PORTEE_INTERACTION ** 2:
            return

        self._init_font()
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        lines = [self.message, "[F]"]
        surfs = [self._font.render(l, True, (220, 200, 255)) for l in lines]
        w = max(s.get_width() for s in surfs) + 20
        h = sum(s.get_height() for s in surfs) + 14

        bx = sx + TAILLE_TUILE // 2 - w // 2
        by = sy - h - 6

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((20, 10, 40, 210))
        pygame.draw.rect(bg, (150, 100, 220), pygame.Rect(0, 0, w, h), 1)
        surface.blit(bg, (bx, by))

        y_cur = by + 7
        for s in surfs:
            surface.blit(s, (bx + (w - s.get_width()) // 2, y_cur))
            y_cur += s.get_height()
