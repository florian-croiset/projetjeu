# ui/quete.py
# IconeJournal (haut gauche, remplace le widget HUD) + Journal de quête.

import pygame
import math
import random


# ---------------------------------------------------------------------------
#  Étapes
# ---------------------------------------------------------------------------

ETAPES = [
    {
        "id":     "ennemis",
        "texte":  "Vaincs 5 ennemis",
        "detail": [
            "Les ruines grouillent de créatures corrompues",
            "par le Grand Silence. Prouve ta valeur en",
            "éliminant cinq d'entre elles.",
        ],
    },
    {
        "id":     "ames",
        "texte":  "Récolte 50 âmes",
        "detail": [
            "Les âmes errantes sont la monnaie des morts.",
            "Ramasse-en cinquante pour prouver",
            "que tu maîtrises les ténèbres.",
        ],
    },
    {
        "id":     "cle",
        "texte":  "Trouve la clé",
        "detail": [
            "Une vieille clé en fer forgé se trouve",
            "quelque part dans les ruines. Elle est",
            "le seul moyen d'ouvrir la Porte de l'Aurore.",
        ],
    },
    {
        "id":     "porte",
        "texte":  "Ouvre la Porte de l'Aurore",
        "detail": [
            "La Porte de l'Aurore est scellée depuis",
            "des siècles au fond des ruines. Derrière",
            "elle se trouve la source de la Première Lumière.",
        ],
    },
]

# --- Palette HUD ---
_CYAN  = (0,   220, 255)
_VERT  = (80,  240, 120)
_GRIS  = (80,   70, 110)
_BLANC = (210, 200, 255)
_FOND  = (6,    4,  18)

# --- Palette parchemin ---
_PC_BASE  = (222, 203, 158)   # crème chaud
_PC_BORD  = (170, 145, 100)   # bord plus sombre
_PC_LIGHT = (240, 226, 188)   # highlight léger
_INK      = ( 52,  30,  10)   # encre brune foncée
_INK_FADE = (110,  85,  50)   # encre secondaire
_INK_DONE = ( 55, 100,  45)   # encre verte (terminé)
_INK_GREY = (145, 120,  75)   # encre grise (inactif)
_INK_RED  = (130,  40,  25)   # encre rouge (accent)


def _formatter_touche_journal(touche):
    if not touche:
        return "I"
    texte = str(touche)
    if texte.startswith("mouse_"):
        return "M" + texte.split("_", 1)[1]
    alias = {
        "space": "ESPACE",
        "return": "ENTREE",
        "escape": "ECHAP",
        "left shift": "LSHIFT",
        "right shift": "RSHIFT",
    }
    return alias.get(texte.lower(), texte).upper()


# ---------------------------------------------------------------------------
#  Helpers parchemin
# ---------------------------------------------------------------------------

def _bords_dechires(surf: pygame.Surface, seed: int = 7):
    """Bords déchirés irréguliers — uniquement découpe transparente."""
    rng  = random.Random(seed)
    w, h = surf.get_size()
    T    = (0, 0, 0, 0)
    pas  = 10
    prof = 6

    def dents_h(y0, exterieur_y):
        pts = [(-2, exterieur_y)]
        xi  = 0
        while xi <= w + pas:
            dy = rng.randint(0, prof)
            pts.append((xi, y0 + dy * (1 if exterieur_y < y0 else -1)))
            xi += pas + rng.randint(-2, 3)
        pts.append((w + 2, exterieur_y))
        return pts

    def dents_v(x0, exterieur_x):
        pts = [(exterieur_x, -2)]
        yi  = 0
        while yi <= h + pas:
            dx = rng.randint(0, prof)
            pts.append((x0 + dx * (1 if exterieur_x < x0 else -1), yi))
            yi += pas + rng.randint(-2, 3)
        pts.append((exterieur_x, h + 2))
        return pts

    pygame.draw.polygon(surf, T, dents_h(0,   -2)   + [(-2, -2)])
    pygame.draw.polygon(surf, T, dents_h(h,  h+2)   + [(-2, h+2)])
    pygame.draw.polygon(surf, T, dents_v(0,   -2)   + [(-2, h+2), (-2, -2)])
    pygame.draw.polygon(surf, T, dents_v(w,  w+2)   + [(w+2, h+2), (w+2, -2)])


def _fond_parchemin(surf: pygame.Surface):
    """Fond parchemin : dégradé de bords, sans BLEND ni set_at intensif."""
    w, h = surf.get_size()
    surf.fill(_PC_BASE)

    ombre = pygame.Surface((w, h), pygame.SRCALPHA)
    prof  = min(55, w // 7)
    for i in range(prof):
        a = int(100 * (1 - i / prof) ** 1.6)
        col = (*_PC_BORD, a)
        pygame.draw.line(ombre, col, (i,     0), (i,     h))
        pygame.draw.line(ombre, col, (w-1-i, 0), (w-1-i, h))
    prof2 = min(45, h // 7)
    for i in range(prof2):
        a = int(85 * (1 - i / prof2) ** 1.6)
        col = (*_PC_BORD, a)
        pygame.draw.line(ombre, col, (0, i),     (w, i))
        pygame.draw.line(ombre, col, (0, h-1-i), (w, h-1-i))
    surf.blit(ombre, (0, 0))

    hl = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(min(80, w // 5)):
        a = int(28 * (1 - i / (w // 5)))
        pygame.draw.line(hl, (*_PC_LIGHT, a), (i, 0), (0, i))
    surf.blit(hl, (0, 0))

    rng = random.Random(99)
    nb  = (w * h) // 120
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(nb):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        a = rng.randint(8, 28)
        tmp.set_at((x, y), (90, 65, 30, a))
    surf.blit(tmp, (0, 0))

    rng2 = random.Random(42)
    for _ in range(rng2.randint(4, 7)):
        tx = rng2.randint(30, w - 30)
        ty = rng2.randint(30, h - 30)
        tr = rng2.randint(8, 22)
        ta = rng2.randint(18, 42)
        ts = pygame.Surface((tr * 2, tr * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ts, (*_PC_BORD, ta), ts.get_rect())
        surf.blit(ts, (tx - tr, ty - tr))


def _ligne_ink(surf, x1, y1, x2, y2, col=None, ep=1):
    col = col or _INK_FADE
    pygame.draw.line(surf, col, (x1, y1), (x2, y2), ep)


def _ornement(surf, cx, y, largeur, col):
    """Petite ligne décorative centrée avec losange au centre."""
    aw = largeur // 2 - 10
    _ligne_ink(surf, cx - aw, y, cx - 8, y, col, 1)
    _ligne_ink(surf, cx + 8,  y, cx + aw, y, col, 1)
    pygame.draw.polygon(surf, col, [
        (cx, y - 4), (cx + 5, y), (cx, y + 4), (cx - 5, y)
    ])


# ---------------------------------------------------------------------------
#  Icône Journal (remplace le widget HUD)
# ---------------------------------------------------------------------------

def _dessiner_icone_journal(surf: pygame.Surface, x: int, y: int,
                             police_label: pygame.font.Font,
                             police_hint: pygame.font.Font,
                             ticks: int,
                             nb_completes: int, nb_total: int,
                             touche_journal="i"):
    W, H = 32, 36
    cx   = x + W // 2

    pulse = 0.6 + 0.4 * math.sin(ticks / 600)
    bord_alpha = int(180 * pulse) if nb_completes < nb_total else 220

    pages_col  = (210, 192, 148)
    cover_col  = (90,  60,  30)
    spine_col  = (65,  42,  18)
    line_col   = (160, 138, 95)

    pygame.draw.rect(surf, cover_col,  pygame.Rect(x + 4, y + 1, W - 4, H - 1), border_radius=3)
    pygame.draw.rect(surf, spine_col,  pygame.Rect(x, y + 1, 6, H - 1), border_radius=2)
    pygame.draw.rect(surf, pages_col,  pygame.Rect(x + 6, y + 3, W - 10, H - 5), border_radius=1)

    for i in range(3):
        ly = y + 9 + i * 7
        pygame.draw.line(surf, line_col, (x + 9, ly), (x + W - 7, ly), 1)

    if nb_completes == nb_total:
        bord_col = (*_VERT,  bord_alpha)
    elif nb_completes > 0:
        bord_col = (*_CYAN,  bord_alpha)
    else:
        bord_col = (160, 130, 80, bord_alpha)

    bord_surf = pygame.Surface((W + 2, H + 2), pygame.SRCALPHA)
    pygame.draw.rect(bord_surf, bord_col,
                     bord_surf.get_rect(), width=1, border_radius=3)
    surf.blit(bord_surf, (x - 1, y))

    f_count = pygame.font.Font(None, max(14, police_hint.get_height() - 2))
    count_s = f_count.render(f"{nb_completes}/{nb_total}", True, pages_col)
    surf.blit(count_s, (x + W // 2 - count_s.get_width() // 2 + 2,
                        y + H - count_s.get_height() - 3))

    y_after_book = y + H + 4

    f_quetes = pygame.font.Font(None, max(13, police_hint.get_height()))
    label_s = f_quetes.render("QUÊTES", True, (140, 190, 210))
    surf.blit(label_s, (cx - label_s.get_width() // 2, y_after_book))
    y_after_book += label_s.get_height() + 2

    hint_alpha = int(160 + 95 * math.sin(ticks / 400))
    hint_col   = (max(0, min(255, hint_alpha)),) * 3
    hint_s = police_hint.render(f"[{_formatter_touche_journal(touche_journal)}]", True, hint_col)
    surf.blit(hint_s, (cx - hint_s.get_width() // 2, y_after_book))
    y_after_book += hint_s.get_height()

    return y_after_book - y


class IconeJournal:
    """
    Remplace WidgetQuete : affiche uniquement une petite icône de journal
    avec le label 'QUÊTES' et la touche configurée pour indiquer l'ouverture.
    """

    def __init__(self, police_label: pygame.font.Font, police_hint: pygame.font.Font):
        self.police_label = police_label
        self.police_hint  = police_hint
        self._etat        = {e["id"]: False for e in ETAPES}
        self._ticks       = 0
        self._porte_vue   = False
        self.touche_journal = "i"

    def mettre_a_jour(self, cle, porte, boss, ennemis_tues=0, ames=0):
        self._ticks = pygame.time.get_ticks()

        def _noter(eid, fait):
            new = bool(fait)
            if new != self._etat.get(eid):
                self._etat[eid] = new

        _noter("ennemis", ennemis_tues >= 5)
        _noter("ames",    ames >= 50)
        _noter("cle",     bool(cle and getattr(cle, 'est_ramassee', False)))

        if porte and (getattr(porte, 'en_ouverture', False) or
                      getattr(porte, 'ouverte',      False)):
            self._porte_vue = True
        _noter("porte", self._porte_vue)

    def dessiner(self, ecran: pygame.Surface, y_offset: int, touche_journal=None, x_offset: int = 30):
        if touche_journal is not None:
            self.touche_journal = touche_journal
        nb_total     = len(ETAPES)
        nb_completes = sum(1 for e in ETAPES if self._etat.get(e["id"]) is True)

        surf_w = 80
        surf_h = 80
        surf   = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

        hauteur = _dessiner_icone_journal(
            surf, x=8, y=0,
            police_label=self.police_label,
            police_hint=self.police_hint,
            ticks=self._ticks,
            nb_completes=nb_completes,
            nb_total=nb_total,
            touche_journal=self.touche_journal,
        )

        ecran.blit(surf, (x_offset, y_offset))
        return hauteur


# Alias pour rétrocompatibilité
WidgetQuete = IconeJournal


# ---------------------------------------------------------------------------
#  Journal de quête — parchemin
# ---------------------------------------------------------------------------

class JournalQuete:
    _FADE_MS = 200

    def __init__(self, largeur_ecran, hauteur_ecran,
                 police_titre, police_texte, police_petit):
        self.larg = largeur_ecran
        self.haut = hauteur_ecran
        h = hauteur_ecran
        self._p_titre  = pygame.font.Font(None, max(48, h // 17))
        self._p_sous   = pygame.font.Font(None, max(26, h // 38))
        self._p_etape  = pygame.font.Font(None, max(32, h // 26))
        self._p_detail = pygame.font.Font(None, max(24, h // 40))
        self._p_hint   = pygame.font.Font(None, max(20, h // 48))

        self.ouvert     = False
        self._alpha     = 0
        self._ouvert_ms = 0
        self._ferme_ms  = 0

        self._etat          = {e["id"]: False for e in ETAPES}
        self._completion_ms = {}
        self._ticks         = 0
        self._porte_vue     = False
        self.touche_journal = "i"

        # Compteurs de progression (pour affichage dans le journal)
        self._ennemis_tues = 0
        self._ames_total   = 0

        self._pw = min(660, int(largeur_ecran * 0.58))
        self._ph = min(560, int(hauteur_ecran * 0.72))
        self._px = (largeur_ecran  - self._pw) // 2
        self._py = (hauteur_ecran  - self._ph) // 2

        self._surf_parche  = None
        self._surf_contenu = None
        self._etat_hash    = -1
        self._construire_parchemin()

    # --- toggle ---

    def toggle(self):
        self.ouvert = not self.ouvert
        now = pygame.time.get_ticks()
        if self.ouvert: self._ouvert_ms = now
        else:           self._ferme_ms  = now

    # --- état ---

    def mettre_a_jour(self, cle, porte, boss, ennemis_tues=0, ames=0):
        self._ticks = pygame.time.get_ticks()
        now = self._ticks

        # Mémorise les compteurs pour l'affichage
        if ennemis_tues != self._ennemis_tues or ames != self._ames_total:
            self._ennemis_tues = ennemis_tues
            self._ames_total   = ames
            self._etat_hash    = -1

        def _noter(eid, fait):
            ancien = self._etat.get(eid)
            new = bool(fait)
            if new != ancien:
                if fait: self._completion_ms[eid] = now
                self._etat[eid] = new
                self._etat_hash = -1

        _noter("ennemis", ennemis_tues >= 5)
        _noter("ames",    ames >= 50)
        _noter("cle",     bool(cle and getattr(cle, 'est_ramassee', False)))

        if porte and (getattr(porte, 'en_ouverture', False) or
                      getattr(porte, 'ouverte',      False)):
            self._porte_vue = True
        _noter("porte", self._porte_vue)

        if self.ouvert:
            el = now - self._ouvert_ms
            self._alpha = min(255, int(255 * el / self._FADE_MS))
        else:
            el = now - self._ferme_ms
            self._alpha = max(0,   int(255 * (1 - el / self._FADE_MS)))

    # --- rendu ---

    def dessiner(self, ecran, touche_journal=None):
        if touche_journal is not None and touche_journal != self.touche_journal:
            self.touche_journal = touche_journal
            self._etat_hash = -1
        if self._alpha <= 0:
            return

        ov = pygame.Surface((self.larg, self.haut), pygame.SRCALPHA)
        ov.fill((0, 0, 0, int(self._alpha * 0.60)))
        ecran.blit(ov, (0, 0))

        px, py = self._px, self._py

        sh = pygame.Surface((self._pw + 20, self._ph + 20), pygame.SRCALPHA)
        sh.fill((0, 0, 0, int(self._alpha * 0.45)))
        ecran.blit(sh, (px - 6, py + 10))

        tmp = self._surf_parche.copy()
        tmp.set_alpha(self._alpha)
        ecran.blit(tmp, (px, py))

        hsh = hash((
            tuple(self._etat.get(e["id"]) for e in ETAPES),
            self._ennemis_tues,
            self._ames_total,
        ))
        if hsh != self._etat_hash or self._surf_contenu is None:
            self._surf_contenu = self._construire_contenu()
            self._etat_hash    = hsh
        ct = self._surf_contenu.copy()
        ct.set_alpha(self._alpha)
        ecran.blit(ct, (px, py))

    # --- construction parchemin (statique) ---

    def _construire_parchemin(self):
        pw, ph = self._pw, self._ph
        surf   = pygame.Surface((pw, ph), pygame.SRCALPHA)
        _fond_parchemin(surf)
        _bords_dechires(surf, seed=7)
        self._surf_parche = surf

    # --- construction contenu (dynamique) ---

    def _construire_contenu(self):
        pw, ph = self._pw, self._ph
        surf   = pygame.Surface((pw, ph), pygame.SRCALPHA)
        padx   = max(32, pw // 11)
        pady   = max(22, ph // 16)
        cx     = pw // 2
        y      = pady

        # ── Titre ──
        t_s = self._p_titre.render("Journal de Quête", True, _INK)
        surf.blit(t_s, t_s.get_rect(centerx=cx, top=y))
        y += t_s.get_height() + 3

        sub_s = self._p_sous.render("— Chroniques de l'Éclaireur —", True, _INK_FADE)
        surf.blit(sub_s, sub_s.get_rect(centerx=cx, top=y))
        y += sub_s.get_height() + 10

        _ornement(surf, cx, y + 5, pw - padx * 2, _INK_FADE)
        y += 18

        # ── Étapes ──
        lh_e  = self._p_etape.get_height()
        lh_d  = self._p_detail.get_height()
        gap   = max(18, ph // 26)

        for i, etape in enumerate(ETAPES):
            etat  = self._etat.get(etape["id"])
            actif = all(self._etat.get(e["id"]) is True
                        for e in ETAPES[:i])

            # Fond discret pour l'étape active
            if actif and etat is False:
                bloc_h = lh_e + 8 + lh_d * len(etape["detail"]) + gap
                fond   = pygame.Surface((pw - padx * 2, bloc_h + 6), pygame.SRCALPHA)
                fond.fill((*_PC_BORD, 35))
                pygame.draw.rect(fond, (*_INK, 40), fond.get_rect(), 1, border_radius=3)
                surf.blit(fond, (padx - 4, y - 4))

            # Icône + texte étape
            if etat is True:
                ic_txt = "✓"; c_ic = _INK_DONE; c_et = _INK_DONE
            elif actif:
                ic_txt = "▶"; c_ic = _INK;      c_et = _INK
            else:
                ic_txt = "○"; c_ic = _INK_GREY; c_et = _INK_GREY

            # Texte de l'étape avec compteur progressif pour ennemis/âmes
            texte_etape = etape["texte"]
            if etape["id"] == "ennemis" and etat is False:
                texte_etape = f"Vaincs 5 ennemis  ({min(self._ennemis_tues, 5)}/5)"
            elif etape["id"] == "ames" and etat is False:
                texte_etape = f"Récolte 50 âmes  ({min(self._ames_total, 50)}/50)"

            ic_s  = self._p_etape.render(ic_txt, True, c_ic)
            et_s  = self._p_etape.render(texte_etape, True, c_et)
            ligne_w = ic_s.get_width() + 8 + et_s.get_width()
            x_start = cx - ligne_w // 2
            tx      = x_start + ic_s.get_width() + 8
            surf.blit(ic_s, (x_start, y))
            surf.blit(et_s, (tx, y))

            if etat is True:
                my = y + lh_e // 2
                pygame.draw.line(surf, _INK_DONE, (tx, my), (tx + et_s.get_width(), my), 1)

            y += lh_e + 8

            # Détail
            c_det = _INK_FADE if actif else _INK_GREY
            for ligne in etape["detail"]:
                d_s = self._p_detail.render(ligne, True, c_det)
                surf.blit(d_s, d_s.get_rect(centerx=cx, top=y))
                y += lh_d + 3
            y += gap

            # Séparateur
            if i < len(ETAPES) - 1:
                sep_x1 = padx + 20
                sep_x2 = pw - padx - 20
                sep_y  = y - gap // 2
                for xi in range(sep_x1, sep_x2):
                    t = (xi - sep_x1) / max(sep_x2 - sep_x1 - 1, 1)
                    fade = math.sin(t * math.pi)
                    a = max(0, int(fade * 80))
                    surf.set_at((xi, sep_y), (*_INK_GREY, a))

        # ── Hint bas ──
        touche = _formatter_touche_journal(self.touche_journal)
        hint = self._p_hint.render(f"[ {touche} ]  Fermer le journal", True, _INK_GREY)
        surf.blit(hint, hint.get_rect(centerx=cx, bottom=ph - pady // 2))

        return surf
