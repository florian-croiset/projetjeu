# core/porte.py
# Porte sprite — 3 frames : fermée / entrouverte / ouverte.
# Spritesheet horizontale : porte_sheet.png (3 × 507×653 px).

import pygame
from parametres import TAILLE_TUILE


# ── Timings ──────────────────────────────────────────────────────────
_DUREE_AJAR   = 400   # ms entre fermée → entrouverte
_DUREE_OUVRIR = 400   # ms entre entrouverte → ouverte

# ── Frames dans la spritesheet ───────────────────────────────────────
_FRAME_FERMEE      = 0
_FRAME_ENTROUVERTE = 1
_FRAME_OUVERTE     = 2

_SHEET_FRAME_W = 507
_SHEET_FRAME_H = 653


class Porte:
    """
    Porte sprite 3 états.

    Dimensions affichées : 2 tuiles × 3 tuiles (64×96 px).
    Seule la frame 0 bloque le joueur ; dès la frame 1 le passage est libre.
    """

    LARGEUR = TAILLE_TUILE * 2   # 64
    HAUTEUR = TAILLE_TUILE * 3   # 96

    # Cache de classe partagé — chargé une seule fois
    _frames: list[pygame.Surface] | None = None

    # ── Chargement ────────────────────────────────────────────────────

    @classmethod
    def charger_assets(cls, chemin: str = "assets/porte_sheet.png"):
        if cls._frames is not None:
            return
        sheet = pygame.image.load(chemin).convert_alpha()
        frame_w = sheet.get_width() // 3
        frame_h = sheet.get_height()
        cls._frames = []
        for i in range(3):
            rect  = pygame.Rect(i * frame_w, 0, frame_w, frame_h)
            frame = sheet.subsurface(rect)
            frame = pygame.transform.scale(frame, (cls.LARGEUR, cls.HAUTEUR))
            cls._frames.append(frame)

    # ── Init ──────────────────────────────────────────────────────────

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, self.LARGEUR, self.HAUTEUR)

        self.est_ouverte   = False
        self.en_ouverture  = False
        self._frame_courante = _FRAME_FERMEE
        self._t_transition   = 0   # timestamp du début de la transition en cours

    # ── Logique ───────────────────────────────────────────────────────

    def tenter_ouverture(self, joueur) -> bool:
        if self.est_ouverte or self.en_ouverture:
            return False
        if not joueur.have_key:
            return False
        self.en_ouverture    = True
        self._t_transition   = pygame.time.get_ticks()
        self._frame_courante = _FRAME_FERMEE
        return True

    def mettre_a_jour(self, temps_ms: int):
        if not self.en_ouverture:
            return

        elapsed = temps_ms - self._t_transition

        if self._frame_courante == _FRAME_FERMEE:
            if elapsed >= _DUREE_AJAR:
                self._frame_courante = _FRAME_ENTROUVERTE
                self._t_transition   = temps_ms

        elif self._frame_courante == _FRAME_ENTROUVERTE:
            if elapsed >= _DUREE_OUVRIR:
                self._frame_courante = _FRAME_OUVERTE
                self.en_ouverture    = False
                self.est_ouverte     = True
                self.rect.width      = 0
                self.rect.height     = 0

    @property
    def rect_collision(self) -> pygame.Rect:
        # Dès la frame entrouverte le joueur peut passer
        if self._frame_courante >= _FRAME_ENTROUVERTE:
            return pygame.Rect(self.x, self.y, 0, 0)
        return pygame.Rect(self.x, self.y, self.LARGEUR, self.HAUTEUR)

    # ── Réseau ────────────────────────────────────────────────────────

    def get_etat(self) -> dict:
        return {
            'x': self.x, 'y': self.y,
            'est_ouverte': self.est_ouverte,
            'en_ouverture': self.en_ouverture,
            'frame': self._frame_courante,
        }

    def set_etat(self, data: dict):
        self.x               = data['x']
        self.y               = data['y']
        self.est_ouverte     = data['est_ouverte']
        self.en_ouverture    = data['en_ouverture']
        self._frame_courante = data['frame']

    # ── Rendu ─────────────────────────────────────────────────────────

    def dessiner(self, surface: pygame.Surface,
                 camera_offset=(0, 0), temps_ms: int = 0):
        if self._frames is None:
            return   # assets non chargés

        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        surface.blit(self._frames[self._frame_courante], (sx, sy))
