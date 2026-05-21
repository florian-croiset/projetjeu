# core/pancarte_lore.py
# Stèle de lore ancienne : pierre gravée de runes incompréhensibles.
# Interaction → paiement en âmes → traduction du message de l'Éclaireur.

import pygame
import math
import os
import sys
import random
from parametres import TAILLE_TUILE, COULEUR_TEXTE, COULEUR_FOND


# ── Texte de lore ──────────────────────────────────────────────────────────
TEXTE_LORE = [
    "Ici repose le serment des Premiers Éclaireurs.",
    "",
    "« Nous étions cinq quand le Silence tomba.",
    "  Nous avons cru que nos voix suffiraient",
    "  à tenir l'obscurité à distance.",
    "",
    "  Nous avions tort.",
    "",
    "  Le dernier d'entre nous grave ces mots",
    "  pour celui qui viendra après :",
    "",
    "  L'écho n'est pas une arme.",
    "  C'est un souvenir.",
    "  Et les souvenirs ne meurent jamais",
    "  tant qu'il reste quelqu'un pour les entendre. »",
    "",
    "                    — Aelys, Dernière Éclaireure,",
    "                      An 1 du Grand Silence",
]

TEXTE_LORE_DASH = [
    "Ici fut gravé le Pas de l'Éclaireur.",
    "",
    "« Avant que le Silence nous engloutisse,",
    "  nous courions entre les ombres.",
    "  Pas pour fuir —",
    "  pour exister encore une seconde de plus.",
    "",
    "  Ce mouvement n'est pas une technique.",
    "  C'est un réflexe de survivant.",
    "  Le corps qui refuse de s'arrêter",
    "  quand tout lui dit de tomber.",
    "",
    "  Si tu lis ces mots,",
    "  c'est que tu as encore quelque chose",
    "  qui vaut la peine d'être couru. »",
    "",
    "                    — Aelys, Dernière Éclaireure,",
    "                      An 1 du Grand Silence",
]

COUT_AMES = 30
COUT_DASH = 50
LARGEUR_PANCARTE = 48
HAUTEUR_PANCARTE = 56

# ── Formes runiques dessinées à la main ────────────────────────────────────
# Chaque rune est une liste de segments (x1, y1, x2, y2) dans une grille 8×12.
_RUNES_FORMES = [
    [(4, 0, 4, 12), (2, 3, 6, 3), (2, 9, 6, 9)],           # 0 : I ramifié
    [(1, 1, 7, 11), (7, 1, 1, 11)],                          # 1 : X
    [(2, 0, 7, 6), (7, 6, 2, 12)],                           # 2 : zigzag
    [(4, 0, 4, 12), (4, 4, 1, 1), (4, 4, 7, 1)],             # 3 : flèche haut
    [(2, 0, 2, 12), (2, 3, 7, 1), (2, 7, 7, 5)],             # 4 : tige branches
    [(4, 0, 7, 4), (7, 4, 4, 8), (4, 8, 1, 4), (1, 4, 4, 0)], # 5 : losange
    [(2, 0, 2, 12), (7, 0, 7, 12), (2, 0, 7, 12)],           # 6 : N
    [(4, 0, 4, 12), (1, 4, 7, 4)],                           # 7 : T
    [(3, 0, 3, 12), (3, 5, 7, 2), (3, 5, 7, 8)],             # 8 : flèche droite
    [(3, 0, 3, 12), (3, 4, 7, 7), (7, 7, 3, 10)],            # 9 : serpent
]

# Séquences de runes sur chaque ligne d'inscription (indices dans _RUNES_FORMES)
_LIGNES_INSCRIPTION = [
    [4, 7, 0, 2, 8],
    [1, 3, 9, 6, 4],
    [7, 0, 5, 8, 3],
]

# Couleurs pierre
_PIERRE      = (72,  68,  80)
_PIERRE_BORD = (38,  35,  46)
_PIERRE_LUM  = (108, 103, 120)
_PIERRE_OMBR = (50,  47,  58)


def _dessiner_rune(surf, formes, x, y, scale, couleur):
    """Dessine une rune (liste de segments) à (x, y) avec l'échelle donnée."""
    ep = max(1, scale // 7)
    for x1, y1, x2, y2 in formes:
        sx1 = x + x1 * scale // 8
        sy1 = y + y1 * scale // 12
        sx2 = x + x2 * scale // 8
        sy2 = y + y2 * scale // 12
        pygame.draw.line(surf, couleur, (sx1, sy1), (sx2, sy2), ep)


class PancarteLore:
    """
    Stèle de pierre gravée de runes incompréhensibles.
    - Interaction → paiement → traduction débloquée.
    - Interagir une fois débloquée → lecture du message de l'Éclaireur.
    """

    PORTEE_INTERACTION = 80

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, LARGEUR_PANCARTE, HAUTEUR_PANCARTE)
        self.est_debloquee = False
        self._phase = 0.0
        self._font_lore  = None
        self._font_titre = None
        self._font_ui    = None
        self._surf_cache = None
        self._surf_etat  = None

    # ── Réseau ──────────────────────────────────────────────────────────────

    def get_etat(self, id_pancarte: int = None) -> dict:
        d = {'x': self.x, 'y': self.y, 'est_debloquee': self.est_debloquee, 'type_pancarte': getattr(self, 'type_pancarte', 'lore'),}
        if id_pancarte is not None:
            d['id'] = id_pancarte
        return d

    def set_etat(self, data: dict):
        self.x             = data['x']
        self.y             = data['y']
        self.est_debloquee = data['est_debloquee']
        self.type_pancarte = data.get('type_pancarte', 'lore')
        self.rect.topleft  = (self.x, self.y)
        self._surf_cache   = None

    # ── Logique serveur ─────────────────────────────────────────────────────

    def tenter_paiement(self, joueur) -> str:
        if self.est_debloquee:
            return 'deja_debloquee'
        if getattr(self, 'type_pancarte', 'lore') == 'shop_dash':
            if joueur.argent < COUT_DASH:
                return 'pauvre'
            if joueur.peut_dash:
                return 'deja_debloquee'
            joueur.argent -= COUT_DASH
            joueur.peut_dash = True
            self.est_debloquee = True
            joueur.sons_a_jouer.append('ame_libre')
            return 'debloquee'
        if joueur.argent < COUT_AMES:
            return 'pauvre'
        joueur.argent -= COUT_AMES
        self.est_debloquee = True
        joueur.sons_a_jouer.append('ame_perdue')
        return 'debloquee'

    def mettre_a_jour(self, temps_ms: int):
        self._phase = (temps_ms / 1200.0) % (2 * math.pi)

    # ── Rendu client ────────────────────────────────────────────────────────

    def _init_fonts(self):
        if self._font_lore is not None:
            return
        self._font_lore  = pygame.font.Font(None, 28)
        self._font_titre = pygame.font.Font(None, 34)
        self._font_ui    = pygame.font.Font(None, 28)

    def dessiner(self, surface: pygame.Surface, camera_offset=(0, 0),
                 temps_ms: int = 0, touche_interagir: str = 'F'):
        self._init_fonts()
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        # Halo ambiant
        self._dessiner_halo(surface, sx, sy)

        # Surface stèle (mise en cache)
        etat_actuel = 'unlocked' if self.est_debloquee else 'locked'
        if self._surf_cache is None or self._surf_etat != etat_actuel:
            self._surf_cache = self._construire_surface_pancarte(etat_actuel)
            self._surf_etat  = etat_actuel
        # La surface est 8px plus large et 12px plus haute que le rect
        surface.blit(self._surf_cache, (sx - 4, sy - 6))

        # Particules runiques
        self._dessiner_particules(surface, sx, sy, temps_ms)

        # Badge d'interaction
        self._dessiner_indicateur(surface, sx, sy, temps_ms, touche_interagir)

    # ── Construction de la surface stèle ────────────────────────────────────

    def _construire_surface_pancarte(self, etat: str) -> pygame.Surface:
        W = LARGEUR_PANCARTE + 8   # 56
        H = HAUTEUR_PANCARTE + 12  # 68
        surf = pygame.Surface((W, H), pygame.SRCALPHA)

        rng_t = random.Random(314)

        # ── Socle / piédestal ──
        socle = pygame.Rect(W // 2 - 12, H - 10, 24, 8)
        pygame.draw.rect(surf, _PIERRE_OMBR, socle, border_radius=2)
        pygame.draw.rect(surf, _PIERRE_BORD, socle, 1, border_radius=2)

        # ── Corps de la stèle (légèrement arrondi au sommet) ──
        stele = pygame.Rect(2, 2, W - 4, H - 12)
        pygame.draw.rect(surf, _PIERRE, stele, border_radius=5)

        # Texture grain pierre (points aléatoires, cachés, Random fixe)
        for _ in range(220):
            gx = rng_t.randint(3, W - 4)
            gy = rng_t.randint(3, H - 13)
            ga = rng_t.randint(10, 35)
            gc = rng_t.choice((_PIERRE_OMBR, _PIERRE_LUM))
            surf.set_at((gx, gy), (*gc, ga))

        # Fissure diagonale (décorative)
        for fi in range(stele.top + 8, stele.bottom - 6):
            fx = W // 3 + int(math.sin(fi * 0.25) * 2)
            if 3 <= fx < W - 3:
                surf.set_at((fx, fi), (*_PIERRE_BORD, 160))

        # Bords de la stèle
        pygame.draw.rect(surf, _PIERRE_BORD, stele, 2, border_radius=5)
        # Highlight gauche et haut (effet lumière)
        pygame.draw.line(surf, (*_PIERRE_LUM, 100), (3, 6), (3, H - 14), 1)
        pygame.draw.line(surf, (*_PIERRE_LUM, 70),  (4, 4), (W - 5, 4),  1)

        # ── Zone d'inscription gravée ──
        marge  = 7
        zone   = pygame.Rect(marge, marge + 4, W - marge * 2, H - marge * 2 - 10)
        zone_s = pygame.Surface((zone.w, zone.h), pygame.SRCALPHA)
        zone_s.fill((*_PIERRE_OMBR, 80))
        surf.blit(zone_s, zone.topleft)
        pygame.draw.rect(surf, (*_PIERRE_BORD, 180), zone, 1)

        # Coins gravés de la zone
        sz = 3
        for cx, cy in [(zone.x, zone.y), (zone.right - sz, zone.y),
                       (zone.x, zone.bottom - sz), (zone.right - sz, zone.bottom - sz)]:
            pygame.draw.rect(surf, (*_PIERRE_LUM, 120), pygame.Rect(cx, cy, sz, sz))

        type_p = getattr(self, 'type_pancarte', 'lore')

        if etat == 'locked':
            # Runes incompréhensibles gravées dans la pierre
            if type_p == 'shop_dash':
                coul_rune = (70, 210, 225)
                coul_ombr = (15, 55, 65, 180)
            else:
                coul_rune = (145, 85, 255)
                coul_ombr = (25, 10, 55, 180)

            scale  = 7
            rune_w = scale + 4
            rune_h = scale + 5
            nb_cols = max(1, (zone.w - 6) // rune_w)
            nb_rows = len(_LIGNES_INSCRIPTION)
            tot_w  = nb_cols * rune_w
            tot_h  = nb_rows * rune_h
            sx0    = zone.x + (zone.w - tot_w) // 2
            sy0    = zone.y + (zone.h - tot_h) // 2

            for li, ligne in enumerate(_LIGNES_INSCRIPTION):
                for ri in range(nb_cols):
                    ridx  = ligne[ri % len(ligne)]
                    rx    = sx0 + ri * rune_w
                    ry    = sy0 + li * rune_h
                    frome = _RUNES_FORMES[ridx % len(_RUNES_FORMES)]
                    # Ombre de gravure (décalage +1)
                    _dessiner_rune(surf, frome, rx + 1, ry + 1, scale, coul_ombr)
                    # Rune principale
                    _dessiner_rune(surf, frome, rx, ry, scale, (*coul_rune, 215))

        else:
            # État déverrouillé : mandala runique doré
            cx_s = W // 2
            cy_s = zone.y + zone.h // 2

            # Cercle de base gravé
            pygame.draw.circle(surf, _PIERRE_OMBR, (cx_s, cy_s), 14)
            pygame.draw.circle(surf, (110, 85, 22), (cx_s, cy_s), 14, 2)

            # 6 petites runes en couronne
            for i in range(6):
                a = i * math.pi / 3
                rx = int(cx_s + math.cos(a) * 20) - 3
                ry = int(cy_s + math.sin(a) * 20) - 5
                f  = _RUNES_FORMES[i % len(_RUNES_FORMES)]
                _dessiner_rune(surf, f, rx + 1, ry + 1, 6, (40, 30, 5, 160))
                _dessiner_rune(surf, f, rx, ry, 6, (185, 145, 40))

            # Étoile centrale
            f_star = pygame.font.Font(None, 30)
            star   = f_star.render("✦", True, (255, 200, 55))
            surf.blit(star, star.get_rect(center=(cx_s, cy_s)))

        return surf

    # ── Halo ambiant ────────────────────────────────────────────────────────

    def _dessiner_halo(self, surface, sx, sy):
        pulse = 0.5 + 0.5 * math.sin(self._phase)
        sz    = 64
        halo  = pygame.Surface((sz, sz), pygame.SRCALPHA)
        cx, cy = sz // 2, sz // 2

        if self.est_debloquee:
            col = (255, 190, 50)
            for r, a in [(26, 8), (18, 18), (10, 35)]:
                pygame.draw.circle(halo, (*col, int(a * pulse)),
                                   (cx, cy + 10), r)
        else:
            type_p = getattr(self, 'type_pancarte', 'lore')
            col = (60, 200, 220) if type_p == 'shop_dash' else (130, 70, 255)
            for r, a in [(26, 10), (18, 22), (10, 42)]:
                pygame.draw.circle(halo, (*col, int(a * pulse)),
                                   (cx, cy + 10), r)

        # Particules de lumière montantes sur le halo
        for i in range(3):
            ph  = self._phase + i * 2.1
            hpx = int(cx + math.cos(ph * 0.8) * 9)
            hpy = int(cy + 4 - (i * 6) - (math.sin(ph) * 4))
            ha  = max(0, int(70 * math.sin(ph + 1.5)))
            if 0 <= hpx < sz and 0 <= hpy < sz:
                pygame.draw.circle(halo, (*col, ha), (hpx, hpy), 2)

        surface.blit(halo, (sx + LARGEUR_PANCARTE // 2 - cx,
                            sy + HAUTEUR_PANCARTE // 2 - cy))

    # ── Particules runiques flottantes ───────────────────────────────────────

    def _dessiner_particules(self, surface, sx, sy, temps_ms):
        """Petites runes flottant autour de la stèle."""
        type_p  = getattr(self, 'type_pancarte', 'lore')
        col_r   = (60, 200, 220) if type_p == 'shop_dash' else (130, 70, 255)
        col_u   = (255, 195, 50)
        couleur = col_u if self.est_debloquee else col_r
        nb      = 4 if not self.est_debloquee else 3

        for i in range(nb):
            ph  = self._phase + i * (2 * math.pi / nb)
            px  = sx + LARGEUR_PANCARTE // 2 + math.cos(ph) * (20 + i * 3)
            py  = sy + HAUTEUR_PANCARTE // 2 + math.sin(ph * 0.7) * 9 - i * 4
            a   = max(0, int(90 + 80 * math.sin(ph * 2)))
            ridx = (i * 3) % len(_RUNES_FORMES)
            # Mini rune (scale 5)
            tmp = pygame.Surface((9, 11), pygame.SRCALPHA)
            _dessiner_rune(tmp, _RUNES_FORMES[ridx], 0, 0, 5, (*couleur, a))
            surface.blit(tmp, (int(px) - 4, int(py) - 5))

    # ── Badge d'interaction ──────────────────────────────────────────────────

    def _dessiner_indicateur(self, surface, sx, sy, temps_ms, touche: str = 'F'):
        f  = pygame.font.Font(None, 26)
        tk = (touche or 'F').upper()
        if not self.est_debloquee:
            type_p = getattr(self, 'type_pancarte', 'lore')
            cout   = COUT_DASH if type_p == 'shop_dash' else COUT_AMES
            label  = f"[{tk}]  {cout} âmes"
            coul   = (80, 210, 230) if type_p == 'shop_dash' else (160, 100, 255)
        else:
            label = f"[{tk}]  Lire"
            coul  = (255, 200, 70)

        s = f.render(label, True, coul)
        flot = int(3 * math.sin(self._phase * 2))
        bx   = sx + LARGEUR_PANCARTE // 2 - s.get_width() // 2
        by   = sy - 24 + flot

        bg = pygame.Surface((s.get_width() + 10, s.get_height() + 6), pygame.SRCALPHA)
        # Fond pierre sombre
        pygame.draw.rect(bg, (22, 18, 35, 200), bg.get_rect(), border_radius=4)
        pygame.draw.rect(bg, (*coul, 160), bg.get_rect(), 1, border_radius=4)
        bg.blit(s, (5, 3))
        surface.blit(bg, (bx - 5, by - 3))


# ── Bulle de dialogue de lore ────────────────────────────────────────────────

class BulleLore:
    """
    Panneau de traduction : affiche le message de l'Éclaireur
    une fois l'inscription déchiffrée.
    Style : tablette de pierre sombre avec texte doré gravé.
    """

    LARGEUR = 640
    HAUTEUR = 460
    MARGE   = 34

    def __init__(self, largeur_ecran: int, hauteur_ecran: int):
        self.lw   = largeur_ecran
        self.lh   = hauteur_ecran
        self.rect = pygame.Rect(
            largeur_ecran  // 2 - self.LARGEUR // 2,
            hauteur_ecran  // 2 - self.HAUTEUR // 2,
            self.LARGEUR, self.HAUTEUR,
        )
        self.visible    = False
        self._scroll    = 0
        self._temps_ouv = 0

        self._font_texte  = pygame.font.Font(None, 27)
        self._font_titre  = pygame.font.Font(None, 34)
        self._font_fermer = pygame.font.Font(None, 24)

        # Surface de fond pré-construite (statique)
        self._surf_fond   = None
        self._construire_fond()

    def _construire_fond(self):
        W, H = self.LARGEUR, self.HAUTEUR
        surf  = pygame.Surface((W, H), pygame.SRCALPHA)

        # Gradient vertical sombre (granit profond)
        for y in range(H):
            t = y / H
            r = int(24 + t * 14)
            g = int(20 + t * 10)
            b = int(32 + t * 18)
            pygame.draw.line(surf, (r, g, b, 248), (0, y), (W, y))

        # Grain de pierre
        rng = random.Random(555)
        for _ in range(500):
            gx = rng.randint(0, W - 1)
            gy = rng.randint(0, H - 1)
            ga = rng.randint(6, 22)
            surf.set_at((gx, gy), (90, 85, 105, ga))

        # Bordure extérieure or-brun
        pygame.draw.rect(surf, (115, 88, 22), pygame.Rect(0, 0, W, H), 3, border_radius=7)
        # Bordure intérieure fine
        pygame.draw.rect(surf, (75, 57, 12), pygame.Rect(6, 6, W - 12, H - 12), 1, border_radius=5)

        # Coins ornés : petites runes gravées
        for cx, cy in [(10, 10), (W - 22, 10), (10, H - 22), (W - 22, H - 22)]:
            # Fond de coin
            pygame.draw.rect(surf, (50, 45, 60), pygame.Rect(cx, cy, 12, 12))
            pygame.draw.rect(surf, (100, 78, 18), pygame.Rect(cx, cy, 12, 12), 1)
            # Mini rune
            _dessiner_rune(surf, _RUNES_FORMES[5], cx + 1, cy, 8, (160, 125, 35))

        # Séparateur horizontal au niveau du titre (y=56)
        for px in range(self.MARGE, W - self.MARGE):
            t = (px - self.MARGE) / max(W - self.MARGE * 2 - 1, 1)
            fade = math.sin(t * math.pi)
            a = int(180 * fade)
            surf.set_at((px, 55), (115, 88, 22, a))
            surf.set_at((px, 56), (55,  42, 10, a // 2))

        # Petites runes décoratives le long du séparateur
        for i, ridx in enumerate([2, 7, 5, 0, 7, 2]):
            rx = self.MARGE + i * ((W - self.MARGE * 2) // 6) - 3
            _dessiner_rune(surf, _RUNES_FORMES[ridx], rx, 47, 7, (130, 100, 28))

        # Séparateur du bas (au-dessus du hint)
        sep_bot = H - 28
        for px in range(self.MARGE, W - self.MARGE):
            t = (px - self.MARGE) / max(W - self.MARGE * 2 - 1, 1)
            fade = math.sin(t * math.pi)
            a = int(100 * fade)
            surf.set_at((px, sep_bot), (115, 88, 22, a))

        self._surf_fond = surf

    def ouvrir(self, texte=None):
        self.visible    = True
        self._scroll    = 0
        self._temps_ouv = pygame.time.get_ticks()
        self._texte     = texte if texte is not None else TEXTE_LORE

    def fermer(self):
        self.visible = False

    def gerer_event(self, event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.fermer(); return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(event.pos):
                self.fermer(); return True
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - event.y * 18)
            return True
        return False

    def dessiner(self, surface: pygame.Surface):
        if not self.visible:
            return

        temps_ms = pygame.time.get_ticks()
        elapsed  = temps_ms - self._temps_ouv

        # Overlay sombre (fondu)
        ov = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, min(185, int(185 * elapsed / 350))))
        surface.blit(ov, (0, 0))

        # Ombre portée
        sh = pygame.Surface((self.LARGEUR + 18, self.HAUTEUR + 18), pygame.SRCALPHA)
        sh.fill((0, 0, 0, min(130, int(130 * elapsed / 350))))
        surface.blit(sh, (self.rect.x - 4, self.rect.y + 12))

        # Fond tablette
        surface.blit(self._surf_fond, self.rect.topleft)

        # ── Titre ────────────────────────────────────────────────────────
        titre = self._font_titre.render("✦   Inscription Traduite   ✦", True, (220, 178, 58))
        surface.blit(titre, titre.get_rect(center=(self.rect.centerx, self.rect.y + 32)))

        # Sous-titre attribution
        f_sub = pygame.font.Font(None, 22)
        sub   = f_sub.render("— Message gravé en Langue des Éclaireurs —", True, (120, 92, 28))
        surface.blit(sub, sub.get_rect(center=(self.rect.centerx, self.rect.y + 49)))

        # ── Zone de texte scrollable ─────────────────────────────────────
        zone_y  = self.rect.y + 66
        zone_h  = self.HAUTEUR - 92
        zone_rect = pygame.Rect(
            self.rect.x + self.MARGE, zone_y,
            self.LARGEUR - self.MARGE * 2, zone_h,
        )

        clip_orig = surface.get_clip()
        surface.set_clip(zone_rect)

        lh       = self._font_texte.get_height() + 5
        y_cursor = zone_y + 10 - self._scroll

        texte = self._texte if hasattr(self, '_texte') else TEXTE_LORE
        for ligne in texte:
            if ligne == "":
                y_cursor += lh // 2
                continue
            if ligne.startswith("  ") or ligne.startswith("«"):
                couleur = (210, 178, 100)   # citation : or plus chaud
            elif ligne.startswith("—"):
                couleur = (175, 138, 62)    # attribution : or plus terne
                y_cursor += 4
            else:
                couleur = (238, 215, 150)   # corps : crème dorée

            s = self._font_texte.render(ligne, True, couleur)
            surface.blit(s, (zone_rect.x + 6, y_cursor))
            y_cursor += lh

        surface.set_clip(clip_orig)

        # ── Hint fermeture ────────────────────────────────────────────────
        hint = self._font_fermer.render(
            "[ Échap ] ou cliquer en dehors pour fermer", True, (95, 72, 22))
        surface.blit(hint, hint.get_rect(
            center=(self.rect.centerx, self.rect.bottom - 14)))


# ── Popup de paiement / confirmation ────────────────────────────────────────

class PopupPaiement:
    """
    Popup de confirmation du paiement en âmes (style pierre).
    """

    LARGEUR = 400
    HAUTEUR = 210

    def __init__(self, largeur_ecran: int, hauteur_ecran: int):
        self.lw   = largeur_ecran
        self.lh   = hauteur_ecran
        self.rect = pygame.Rect(
            largeur_ecran  // 2 - self.LARGEUR // 2,
            hauteur_ecran  // 2 - self.HAUTEUR // 2,
            self.LARGEUR, self.HAUTEUR,
        )
        self.visible   = False
        self.mode      = 'confirmer'
        self._callback = None
        self._font     = pygame.font.Font(None, 29)
        self._font_btn = pygame.font.Font(None, 33)
        self._font_sub = pygame.font.Font(None, 24)
        self._temps_msg = 0
        self._btn_oui   = pygame.Rect(0, 0, 118, 38)
        self._btn_non   = pygame.Rect(0, 0, 118, 38)

    def ouvrir_confirmation(self, argent_joueur: int, callback, cout: int = COUT_AMES):
        self.mode      = 'confirmer' if argent_joueur >= cout else 'pauvre'
        self._callback = callback
        self.visible   = True
        self._cout     = cout

    def ouvrir_message(self, mode: str):
        self.mode       = mode
        self._callback  = None
        self.visible    = True
        self._temps_msg = pygame.time.get_ticks()

    def gerer_event(self, event) -> bool:
        if not self.visible:
            return False
        if self._temps_msg and pygame.time.get_ticks() - self._temps_msg > 2500:
            self.visible = False; self._temps_msg = 0
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False; return True
            if event.key == pygame.K_RETURN and self.mode == 'confirmer':
                self._confirmer(); return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == 'confirmer':
                if self._btn_oui.collidepoint(event.pos):
                    self._confirmer(); return True
                if self._btn_non.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
                    self.visible = False; return True
            else:
                self.visible = False; return True
        return self.visible

    def _confirmer(self):
        if self._callback:
            self._callback()
        self.visible = False

    def dessiner(self, surface: pygame.Surface):
        if not self.visible:
            return

        # Overlay
        ov = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        surface.blit(ov, (0, 0))

        # Fond popup pierre
        fond = pygame.Surface((self.LARGEUR, self.HAUTEUR), pygame.SRCALPHA)
        for y in range(self.HAUTEUR):
            t = y / self.HAUTEUR
            r = int(26 + t * 10)
            g = int(22 + t * 8)
            b = int(36 + t * 14)
            pygame.draw.line(fond, (r, g, b, 245), (0, y), (self.LARGEUR, y))

        coul_bord = (200, 50, 50) if self.mode == 'pauvre' else (115, 88, 22)
        pygame.draw.rect(fond, coul_bord, fond.get_rect(), 2, border_radius=8)
        pygame.draw.rect(fond, (50, 38, 10), pygame.Rect(5, 5, self.LARGEUR - 10, self.HAUTEUR - 10),
                         1, border_radius=6)

        # Coins runiques
        for cx, cy in [(8, 8), (self.LARGEUR - 20, 8)]:
            _dessiner_rune(fond, _RUNES_FORMES[7], cx, cy, 8, (120, 92, 20))

        surface.blit(fond, self.rect.topleft)

        cx = self.rect.centerx
        cy = self.rect.centery

        if self.mode == 'confirmer':
            titre = getattr(self, '_titre_popup', "Stèle Mystérieuse")
            t1 = self._font.render(titre, True, (215, 175, 58))
            surface.blit(t1, t1.get_rect(center=(cx, self.rect.y + 30)))

            msg = getattr(self, '_message_popup', f"Payer {COUT_AMES} âmes pour déchiffrer ?")
            t2 = self._font.render(msg, True, (200, 188, 150))
            surface.blit(t2, t2.get_rect(center=(cx, cy - 12)))

            t3 = self._font_sub.render("L'écho des anciens coulera en vous.", True, (130, 110, 70))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 12)))

            btn_y = self.rect.bottom - 54
            self._btn_oui.center = (cx - 68, btn_y)
            self._btn_non.center = (cx + 68, btn_y)
            mx, my = pygame.mouse.get_pos()

            # Bouton Payer
            survol = self._btn_oui.collidepoint(mx, my)
            pygame.draw.rect(surface, (35, 28, 8) if not survol else (60, 48, 12),
                             self._btn_oui, border_radius=5)
            pygame.draw.rect(surface, (140, 108, 28), self._btn_oui, 1, border_radius=5)
            s = self._font_btn.render("Payer", True, (220, 180, 60))
            surface.blit(s, s.get_rect(center=self._btn_oui.center))

            # Bouton Renoncer
            survol2 = self._btn_non.collidepoint(mx, my)
            pygame.draw.rect(surface, (35, 12, 12) if not survol2 else (60, 20, 20),
                             self._btn_non, border_radius=5)
            pygame.draw.rect(surface, (180, 50, 50), self._btn_non, 1, border_radius=5)
            s2 = self._font_btn.render("Renoncer", True, (220, 80, 80))
            surface.blit(s2, s2.get_rect(center=self._btn_non.center))

            hint = self._font_sub.render("[Entrée] Confirmer  |  [Échap] Annuler", True, (80, 65, 30))
            surface.blit(hint, hint.get_rect(center=(cx, self.rect.bottom - 14)))

        elif self.mode == 'pauvre':
            t1 = self._font.render("!  Âmes insuffisantes", True, (220, 80, 80))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 22)))
            t2 = self._font.render(f"Il vous faut {self._cout} âmes.", True, (180, 100, 100))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 2)))
            t3 = self._font_sub.render("Continuez votre chemin...", True, (130, 80, 80))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 22)))

        elif self.mode == 'debloquee':
            t1 = self._font.render("✦  Mémoire absorbée  ✦", True, (220, 178, 58))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 14)))
            t2 = self._font_sub.render("Vous portez désormais le pas des Éclaireurs.", True, (175, 148, 80))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 10)))



# ── Notification de capacité débloquée ──────────────────────────────────────

class NotificationCapacite:
    """
    Bandeau de notification quand une capacité est débloquée.
    Style : pierre sombre translucide, runes, texte doré.
    """
    DUREE_MS    = 4500
    FONDU_MS    = 600
    LARGEUR     = 420
    HAUTEUR     = 72

    _ICONES = {
        'dash':        [((-10,0),(10,0)), ((0,-8),(10,0)), ((0,8),(10,0)), ((-14,-5),(-6,0)), ((-14,5),(-6,0))],
        'double_saut': [((-8,8),(0,-8)), ((0,-8),(8,8)), ((-8,-2),(0,-12)), ((0,-12),(8,-2))],
    }

    def __init__(self, largeur_ecran: int, hauteur_ecran: int):
        self.lw = largeur_ecran
        self.lh = hauteur_ecran
        self._queue   = []   # liste de dicts en attente
        self._actuel  = None
        self._debut   = 0
        self._font_titre = pygame.font.Font(None, 28)
        self._font_sub   = pygame.font.Font(None, 22)
        self._font_touche = pygame.font.Font(None, 24)

    def notifier(self, capacite: str, touche: str = ''):
        """Ajoute une notification à la file."""
        labels = {
            'dash':        ("Pas de l'Éclaireur absorbé", "Le souffle des anciens vous porte — Dash"),
            'double_saut': ("Mémoire du bond retrouvée",  "L'élan des Éclaireurs vous habite — Double Saut"),
        }
        titre, sous = labels.get(capacite, ("Capacité débloquée", capacite))
        self._queue.append({
            'capacite': capacite,
            'titre':    titre,
            'sous':     sous,
            'touche':   touche.upper(),
        })

    def mettre_a_jour(self, temps_ms: int):
        if self._actuel is None and self._queue:
            self._actuel = self._queue.pop(0)
            self._debut  = temps_ms
        if self._actuel:
            if temps_ms - self._debut > self.DUREE_MS:
                self._actuel = None

    def dessiner(self, surface: pygame.Surface, temps_ms: int):
        if self._actuel is None:
            return

        elapsed = temps_ms - self._debut
        # Calcul alpha (fondu entrant + sortant)
        if elapsed < self.FONDU_MS:
            alpha = int(255 * elapsed / self.FONDU_MS)
        elif elapsed > self.DUREE_MS - self.FONDU_MS:
            alpha = int(255 * (self.DUREE_MS - elapsed) / self.FONDU_MS)
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        W, H = self.LARGEUR, self.HAUTEUR
        # Position : bas de l'écran, centré
        x = self.lw // 2 - W // 2
        y = self.lh - H - 32

        # Fond pierre sombre
        fond = pygame.Surface((W, H), pygame.SRCALPHA)
        for fy in range(H):
            t = fy / H
            r = int(18 + t * 10)
            g = int(14 + t * 8)
            b = int(26 + t * 14)
            a = int(210 * alpha / 255)
            pygame.draw.line(fond, (r, g, b, a), (0, fy), (W, fy))

        # Bordure dorée
        coul_bord = (115, 88, 22, alpha)
        pygame.draw.rect(fond, coul_bord, pygame.Rect(0, 0, W, H), 2, border_radius=6)
        pygame.draw.rect(fond, (75, 57, 12, alpha // 2),
                         pygame.Rect(3, 3, W - 6, H - 6), 1, border_radius=4)

        # Ligne dorée gauche (accentuation)
        for fy in range(6, H - 6):
            a_line = int(180 * alpha / 255)
            fond.set_at((4, fy), (180, 140, 40, a_line))

        # Runes décoratives coins
        _dessiner_rune(fond, _RUNES_FORMES[5], 8, 8, 8,
                       (140, 108, 28, int(160 * alpha / 255)))
        _dessiner_rune(fond, _RUNES_FORMES[2], W - 18, 8, 8,
                       (140, 108, 28, int(160 * alpha / 255)))

        surface.blit(fond, (x, y))

        # Icône de la capacité (dessinée à la main)
        cap = self._actuel['capacite']
        icone_x = x + 28
        icone_y = y + H // 2

        # Cercle de fond icône
        circ = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(circ, (40, 35, 55, int(200 * alpha / 255)), (18, 18), 17)
        pygame.draw.circle(circ, (100, 78, 18, int(180 * alpha / 255)), (18, 18), 17, 2)
        surface.blit(circ, (icone_x - 18, icone_y - 18))

        # Segments de l'icône
        segs = self._ICONES.get(cap, [])
        col_icone = (80, 210, 230) if cap == 'dash' else (180, 130, 255)
        if segs:
            tmp_icone = pygame.Surface((36, 36), pygame.SRCALPHA)
            for (x1, y1), (x2, y2) in segs:
                pygame.draw.line(tmp_icone, (*col_icone, int(220 * alpha / 255)),
                                (18 + x1, 18 + y1), (18 + x2, 18 + y2), 2)
            surface.blit(tmp_icone, (icone_x - 18, icone_y - 18))

        # Texte
        tx = x + 56
        col_titre = (220, 178, 58, alpha)
        col_sous  = (160, 135, 80, alpha)

        # Titre
        s_titre = self._font_titre.render(self._actuel['titre'], True, (220, 178, 58))
        tmp = pygame.Surface(s_titre.get_size(), pygame.SRCALPHA)
        tmp.blit(s_titre, (0, 0))
        tmp.set_alpha(alpha)
        surface.blit(tmp, (tx, y + 12))

        # Sous-titre
        s_sous = self._font_sub.render(self._actuel['sous'], True, (160, 135, 80))
        tmp2 = pygame.Surface(s_sous.get_size(), pygame.SRCALPHA)
        tmp2.blit(s_sous, (0, 0))
        tmp2.set_alpha(alpha)
        surface.blit(tmp2, (tx, y + 36))

        # Touche
        if self._actuel['touche']:
            tk_label = f"[ {self._actuel['touche']} ]"
            s_tk = self._font_touche.render(tk_label, True, (80, 210, 230))
            tmp3 = pygame.Surface(s_tk.get_size(), pygame.SRCALPHA)
            tmp3.blit(s_tk, (0, 0))
            tmp3.set_alpha(alpha)
            surface.blit(tmp3, (x + W - s_tk.get_width() - 16, y + H // 2 - s_tk.get_height() // 2))