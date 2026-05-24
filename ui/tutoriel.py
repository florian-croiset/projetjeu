# ui/tutoriel.py
# Tutoriel refactorisé — version améliorée visuellement.
#   Slide 0 — Mécaniques de gameplay
#   Slide 1 — Lore et contexte narratif

import pygame
import math
import random
from parametres import *
from ui.effets_visuels import dessiner_fond_echo
from ui.bouton import Bouton


# ---------------------------------------------------------------------------
#  Utilitaires de rendu
# ---------------------------------------------------------------------------

def _surface_arrondie(w, h, rayon, couleur, alpha):
    """Retourne une Surface SRCALPHA avec un rect arrondi."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (*couleur, alpha), surf.get_rect(), border_radius=rayon)
    return surf

def _badge(ecran, police, texte, x, y, bg_color, texte_color, alpha_bg=35, alpha_bord=90):
    """Dessine un petit badge coloré et retourne la hauteur occupée."""
    s  = police.render(texte, True, texte_color)
    pw = s.get_width() + 20
    ph = s.get_height() + 8

    fond = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(fond, (*bg_color, alpha_bg), fond.get_rect(), border_radius=4)
    pygame.draw.rect(fond, (*bg_color, alpha_bord), fond.get_rect(), 1, border_radius=4)
    ecran.blit(fond, (x, y))
    ecran.blit(s, (x + 10, y + 4))
    return ph + 10


def _ligne_kv(ecran, police_cle, police_val, x, y, cle, val,
              couleur_cle=(180, 150, 255), couleur_val=(180, 170, 220)):
    """Dessine une paire [TOUCHE] description sur une ligne."""
    # Fond de touche
    ks = police_cle.render(cle, True, couleur_cle)
    kw = ks.get_width() + 14
    kh = ks.get_height() + 6
    kfond = pygame.Surface((kw, kh), pygame.SRCALPHA)
    pygame.draw.rect(kfond, (255, 255, 255, 18), kfond.get_rect(), border_radius=3)
    pygame.draw.rect(kfond, (255, 255, 255, 35), kfond.get_rect(), 1, border_radius=3)
    # Ombre basse
    pygame.draw.line(kfond, (255, 255, 255, 50), (1, kh - 1), (kw - 2, kh - 1))
    ecran.blit(kfond, (x, y))
    ecran.blit(ks, (x + 7, y + 3))

    vs = police_val.render(val, True, couleur_val)
    ecran.blit(vs, (x + kw + 10, y + (kh - vs.get_height()) // 2))
    return y + kh + 6


def _texte_wrap(ecran, police, texte, x, y, max_w, couleur, interligne=5):
    """Dessine un texte multi-lignes (split sur \\n)."""
    for ligne in texte.split('\n'):
        if ligne.strip() == '':
            y += police.get_height() // 2
            continue
        s = police.render(ligne, True, couleur)
        ecran.blit(s, (x, y))
        y += s.get_height() + interligne
    return y + 4


def _bloc_highlight(ecran, x, y, w, h,
                    bord_color=(120, 60, 255), bg_alpha=20, bord_alpha=180):
    """Bloc avec bordure gauche colorée."""
    fond = pygame.Surface((w, h), pygame.SRCALPHA)
    fond.fill((*bord_color, bg_alpha))
    pygame.draw.rect(fond, (*bord_color, 0),   fond.get_rect(), border_radius=4)
    pygame.draw.rect(fond, (*bord_color, bg_alpha), fond.get_rect(), border_radius=4)
    pygame.draw.rect(fond, (*bord_color, bord_alpha), (0, 0, 2, h))
    ecran.blit(fond, (x, y))


def _separateur_gradient(ecran, x, y, w,
                          c1=(120, 60, 255), c2=(0, 220, 255)):
    """Séparateur horizontal dégradé via points."""
    for i in range(w):
        t = i / max(w - 1, 1)
        # Fade-in puis fade-out
        fade = math.sin(t * math.pi)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        a = int(fade * 100)
        ecran.set_at((x + i, y), (r, g, b, a))   # nécessite surface SRCALPHA ou direct
    # On utilise une surface intermédiaire pour le blending
    surf = pygame.Surface((w, 2), pygame.SRCALPHA)
    for i in range(w):
        t = i / max(w - 1, 1)
        fade = math.sin(t * math.pi)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        a = int(fade * 90)
        surf.set_at((i, 0), (r, g, b, a))
        surf.set_at((i, 1), (r, g, b, a // 3))
    ecran.blit(surf, (x, y))


# ---------------------------------------------------------------------------
#  Particules / Anneaux d'écho en arrière-plan
# ---------------------------------------------------------------------------

class _Anneau:
    def __init__(self, cx, cy, rayon_max, vitesse, couleur):
        self.cx = cx
        self.cy = cy
        self.r  = random.uniform(0, rayon_max * 0.3)
        self.rmax = rayon_max
        self.v  = vitesse
        self.col = couleur

    def update(self, dt):
        self.r += self.v * dt
        return self.r < self.rmax

    def draw(self, ecran):
        prog = self.r / self.rmax
        alpha = int((1 - prog) * 55)
        if alpha <= 0:
            return
        surf = pygame.Surface((int(self.r * 2 + 2), int(self.r * 2 + 2)), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*self.col, alpha),
                           (int(self.r + 1), int(self.r + 1)), int(self.r), 1)
        ecran.blit(surf, (self.cx - int(self.r) - 1, self.cy - int(self.r) - 1))


class _EtoileAmbiante:
    def __init__(self, w, h):
        self.x = random.randint(0, w)
        self.y = random.randint(0, h)
        self.r = random.uniform(0.5, 1.8)
        self.phase = random.uniform(0, math.pi * 2)
        self.vitesse = random.uniform(0.5, 1.5)

    def draw(self, ecran, temps):
        flicker = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(temps / 700 * self.vitesse + self.phase))
        alpha = int(flicker * 80)
        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (160, 140, 255, alpha), (2, 2), int(self.r))
        ecran.blit(surf, (self.x - 2, self.y - 2))


# ---------------------------------------------------------------------------
#  Classe principale
# ---------------------------------------------------------------------------

class Tutoriel:
    """
    Tutoriel en 2 slides visuellement améliorées.

    Usage :
        tuto = Tutoriel(ecran, largeur, hauteur, params_controles,
                        police_titre, police_texte, police_bouton, police_petit)
        tuto.lancer()
    """

    # Palette de couleurs
    CYAN   = (0,  220, 255)
    VIOLET = (120, 60, 255)
    MAUVE  = (179, 136, 255)
    OR     = (255, 200,  70)
    ROSE   = (255,  80, 140)

    def __init__(self, ecran, largeur, hauteur, params_controles,
                 police_titre, police_texte, police_bouton, police_petit=None):
        self.ecran   = ecran
        self.largeur = largeur
        self.hauteur = hauteur
        self.cx      = largeur // 2
        self.cy      = hauteur // 2

        self.police_titre  = police_titre
        self.police_texte  = police_texte
        self.police_bouton = police_bouton
        self.police_petit  = police_petit or police_texte

        self.params_controles = params_controles

        self.index   = 0
        self.total   = 2
        self.horloge = pygame.time.Clock()

        # Transition fade
        self._alpha_transition = 255   # 0=opaque → 255=transparent
        self._transition_dir   = -1    # -1 = fade in, +1 = fade out
        self._prochaine_slide  = None
        self._FADE_VITESSE     = 18

        # Particules
        self._anneaux  = []
        self._etoiles  = [_EtoileAmbiante(largeur, hauteur) for _ in range(60)]
        self._timer_anneau = 0

        # --- Boutons ---
        bh  = max(38, hauteur // 22)
        bw  = max(150, largeur //  9)
        bot = hauteur - bh - 28

        self.btn_suivant   = Bouton(self.cx + 15,    bot, bw, bh, "Suivant  >>",   police_bouton)
        self.btn_precedent = Bouton(self.cx - bw - 15, bot, bw, bh, "<<  Retour", police_bouton, style="ghost")
        self.btn_fermer    = Bouton(self.cx + 15,    bot, bw, bh, "Commencer !",  police_bouton)
        self.btn_passer    = Bouton(largeur - 200,   22,  175, bh - 10, "Passer ×",
                                    police_petit or police_bouton, style="ghost")

    # ------------------------------------------------------------------
    #  Boucle principale
    # ------------------------------------------------------------------

    def lancer(self):
        self._alpha_transition = 0     # commence opaque (fade in)
        self._transition_dir   = -1   # fade in

        running = True
        while running:
            dt  = self.horloge.tick(FPS) / 16.67   # normalisé à 60 fps
            tms = pygame.time.get_ticks()
            pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys; sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                        if self.index < self.total - 1:
                            self._lancer_transition(self.index + 1)
                        else:
                            running = False
                    elif event.key == pygame.K_LEFT and self.index > 0:
                        self._lancer_transition(self.index - 1)
                    elif event.key == pygame.K_ESCAPE:
                        running = False

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_passer.rect.collidepoint(event.pos):
                        running = False
                    elif self.index == self.total - 1:
                        if self.btn_fermer.rect.collidepoint(event.pos):
                            running = False
                    else:
                        if self.btn_suivant.rect.collidepoint(event.pos):
                            self._lancer_transition(self.index + 1)
                    if self.index > 0 and self.btn_precedent.rect.collidepoint(event.pos):
                        self._lancer_transition(self.index - 1)

            for btn in [self.btn_suivant, self.btn_precedent,
                        self.btn_fermer, self.btn_passer]:
                btn.verifier_survol(pos)

            # Mise à jour des anneaux
            self._maj_particules(dt, tms)
            # Mise à jour de la transition
            self._maj_transition()

            self._dessiner(tms)
            pygame.display.flip()

    # ------------------------------------------------------------------
    #  Gestion des transitions
    # ------------------------------------------------------------------

    def _lancer_transition(self, prochaine):
        if self._prochaine_slide is None:
            self._prochaine_slide = prochaine
            self._transition_dir  = 1      # fade out
            self._alpha_transition = 0

    def _maj_transition(self):
        if self._transition_dir == 1:      # fade out
            self._alpha_transition = min(255, self._alpha_transition + self._FADE_VITESSE)
            if self._alpha_transition >= 255 and self._prochaine_slide is not None:
                self.index = self._prochaine_slide
                self._prochaine_slide = None
                self._transition_dir  = -1
        elif self._transition_dir == -1:   # fade in
            self._alpha_transition = max(0, self._alpha_transition - self._FADE_VITESSE)

    # ------------------------------------------------------------------
    #  Particules
    # ------------------------------------------------------------------

    def _maj_particules(self, dt, tms):
        INTERVAL_MS = 1800
        if tms - self._timer_anneau > INTERVAL_MS:
            self._timer_anneau = tms
            # Un anneau centré au panneau, légèrement aléatoire
            cx = self.cx + random.randint(-self.largeur // 5, self.largeur // 5)
            cy = self.cy + random.randint(-self.hauteur // 5, self.hauteur // 5)
            col = random.choice([self.CYAN, self.VIOLET, self.MAUVE])
            rmax = max(self.largeur, self.hauteur) * 0.55
            self._anneaux.append(_Anneau(cx, cy, rmax, random.uniform(0.8, 1.4), col))

        self._anneaux = [a for a in self._anneaux if a.update(dt)]

    # ------------------------------------------------------------------
    #  Rendu principal
    # ------------------------------------------------------------------

    def _dessiner(self, tms):
        # Fond animé de base (import existant)
        dessiner_fond_echo(self.ecran, self.largeur, self.hauteur, tms)

        # Étoiles ambiantes
        for e in self._etoiles:
            e.draw(self.ecran, tms)

        # Anneaux d'écho
        for a in self._anneaux:
            a.draw(self.ecran)

        # Vignette périphérique
        self._vignette()

        # Panneau central
        pw = int(self.largeur * 0.88)
        ph = int(self.hauteur * 0.82)
        px = (self.largeur - pw) // 2
        py = int(self.hauteur * 0.05)
        self._panneau(px, py, pw, ph, tms)

        if self.index == 0:
            self._slide_gameplay(px, py, pw, ph, tms)
        else:
            self._slide_lore(px, py, pw, ph, tms)

        self._navigation(tms)
        self._indicateur()

        # Overlay de transition
        if self._alpha_transition > 0:
            overlay = pygame.Surface((self.largeur, self.hauteur), pygame.SRCALPHA)
            overlay.fill((4, 2, 14, self._alpha_transition))
            self.ecran.blit(overlay, (0, 0))

    # ------------------------------------------------------------------
    #  Panneau
    # ------------------------------------------------------------------

    def _panneau(self, x, y, w, h, tms):
        # Corps
        fond = pygame.Surface((w, h), pygame.SRCALPHA)
        fond.fill((8, 5, 22, 210))
        self.ecran.blit(fond, (x, y))

        # Bordure pulsée
        pulse = 0.6 + 0.4 * math.sin(tms / 1100)
        bord  = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bord, (*self.VIOLET, int(120 * pulse)), bord.get_rect(), 1, border_radius=10)
        self.ecran.blit(bord, (x, y))

        # Ligne décorative haut dégradée
        _separateur_gradient(self.ecran, x + 30, y, w - 60, self.VIOLET, self.CYAN)

        # Coins décoratifs
        coin_l = 14
        alpha_c = 160
        for dx, dy, hflip, vflip in [(0,0,1,1),(w-coin_l,0,-1,1),(0,h-coin_l,1,-1),(w-coin_l,h-coin_l,-1,-1)]:
            cs = pygame.Surface((coin_l, coin_l), pygame.SRCALPHA)
            pygame.draw.line(cs, (*self.CYAN, alpha_c), (0 if hflip>0 else coin_l-1, 0),
                             (0 if hflip>0 else coin_l-1, coin_l-1), 1)
            pygame.draw.line(cs, (*self.CYAN, alpha_c), (0, 0 if vflip>0 else coin_l-1),
                             (coin_l-1, 0 if vflip>0 else coin_l-1), 1)
            self.ecran.blit(cs, (x + dx, y + dy))

    # ------------------------------------------------------------------
    #  Vignette périphérique
    # ------------------------------------------------------------------

    def _vignette(self):
        v = pygame.Surface((self.largeur, self.hauteur), pygame.SRCALPHA)
        for i, alpha in [(0, 160), (1, 80), (2, 40)]:
            bord_w = (i + 1) * 38
            pygame.draw.rect(v, (0, 0, 0, alpha),
                             (0, 0, self.largeur, self.hauteur),
                             bord_w)
        self.ecran.blit(v, (0, 0))

    # ------------------------------------------------------------------
    #  Slide 0 — Mécaniques
    # ------------------------------------------------------------------

    def _slide_gameplay(self, px, py, pw, ph, tms):
        mh = int(pw * 0.042)
        mv = int(ph * 0.048)
        col_w = (pw - mh * 3) // 2
        c1x = px + mh
        c2x = px + mh * 2 + col_w
        y0  = py + mv

        # Titre
        titre = self.police_titre.render("Mécaniques de jeu", True, self.CYAN)
        self.ecran.blit(titre, (c1x, y0))
        y0 += titre.get_height() + 3

        sous = self.police_texte.render(
            "Tout ce dont tu as besoin pour survivre dans l'obscurité",
            True, (80, 65, 120))
        self.ecran.blit(sous, (c1x, y0))
        y0 += sous.get_height() + 10

        _separateur_gradient(self.ecran, c1x, y0, pw - mh * 2, self.VIOLET, self.CYAN)
        y0 += 14

        self._col_controles(c1x, y0, col_w, tms)
        self._col_systemes(c2x, y0, col_w, tms)

    def _touche(self, cle):
        return self.params_controles.get(cle, '?').upper()

    def _col_controles(self, x, y, w, tms):
        y = y + _badge(self.ecran, self.police_bouton,
                       "  CONTRÔLES", x, y, self.CYAN, self.CYAN, 25, 80)

        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('gauche')} / {self._touche('droite')} ]",
                      "Déplacement horizontal")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('saut')} ]",
                      "Saut  ·  ×2 si Double Saut")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('dash')} ]",
                      "Dash  ·  si débloqué")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('echo')} ]",
                      "Écho radial — révèle l'environnement")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('echo_dir')} ]",
                      "Écho directionnel  ·  si débloqué")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      f"[ {self._touche('attaque')} ]",
                      "Attaque de mêlée")
        y = _ligne_kv(self.ecran, self.police_texte, self.police_texte, x, y,
                      "[ ÉCHAP ]", "Pause")
        y += 16

        y = y + _badge(self.ecran, self.police_bouton,
                       "  COMBAT & SURVIE", x, y, self.ROSE, self.ROSE, 20, 70)

        p = self.police_texte
        lignes = [
            ("Tu as ", "5 PV", ". Chaque contact en retire 1."),
            ("", "1 s", " d'invincibilité après un coup."),
        ]
        for avant, gras, apres in lignes:
            surf_av = p.render(avant, True, (155, 145, 200))
            surf_g  = p.render(gras,  True, (220, 180, 255))
            surf_ap = p.render(apres, True, (155, 145, 200))
            self.ecran.blit(surf_av, (x, y))
            self.ecran.blit(surf_g,  (x + surf_av.get_width(), y))
            self.ecran.blit(surf_ap, (x + surf_av.get_width() + surf_g.get_width(), y))
            y += surf_g.get_height() + 6
        y += 6

        # Bloc highlight avec PV ennemis
        lignes_hp = [
            ("1 PV", "— patrouilleurs rapides"),
            ("2 PV", "— gardes standard"),
            ("3 PV", "— gardiens lourds"),
        ]
        line_h = p.get_height() + 8
        bloc_h = len(lignes_hp) * line_h + 12
        _bloc_highlight(self.ecran, x, y, w - 10, bloc_h, self.VIOLET, 18, 150)
        yb = y + 8
        for pv, desc in lignes_hp:
            sv = p.render(pv,   True, (200, 175, 255))
            sd = p.render(desc, True, (140, 130, 180))
            self.ecran.blit(sv, (x + 12, yb))
            self.ecran.blit(sd, (x + 12 + sv.get_width() + 10, yb))
            yb += line_h

    def _col_systemes(self, x, y, w, tms):
        y = y + _badge(self.ecran, self.police_bouton,
                       "  ÉCHOLOCALISATION", x, y, self.CYAN, self.CYAN, 25, 80)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "Le monde est dans le noir absolu.\n"
                        "Active l'écho pour révéler l'environnement.",
                        x, y, w, (155, 145, 200))
        info_s = self.police_texte.render("Radial : 360°, 150 px, cd 2.5 s",
                                          True, (80, 160, 200))
        self.ecran.blit(info_s, (x, y))
        y += info_s.get_height() + 4
        info_dir = self.police_texte.render("Directionnel : ±25°, 300 px, cd 4 s  (débloquable)",
                                            True, (80, 160, 200))
        self.ecran.blit(info_dir, (x, y))
        y += info_dir.get_height() + 14

        y = y + _badge(self.ecran, self.police_bouton,
                       "  ÂMES PERDUES", x, y, self.MAUVE, self.MAUVE, 22, 75)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "À ta mort → une âme apparaît\n"
                        "avec tout ton argent.\n"
                        "Attaque-la pour récupérer —\n"
                        "ou mourir = perte définitive.",
                        x, y, w, (155, 145, 200))
        y += 12

        y = y + _badge(self.ecran, self.police_bouton,
                       "  CAPACITÉS & PROGRESSION", x, y, self.OR, self.OR, 20, 70)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "Orbe (dans le monde) → Double Saut.\n"
                        "Shop (pancarte, âmes) → Dash (50 â),\n"
                        "écho dir. (10 â), PV+ (20 â)...\n\n"
                        "La porte verrouillée exige la clé.\n"
                        "Checkpoints → sauvegarde auto.",
                        x, y, w, (155, 145, 200))

    # ------------------------------------------------------------------
    #  Slide 1 — Lore
    # ------------------------------------------------------------------

    def _slide_lore(self, px, py, pw, ph, tms):
        mh = int(pw * 0.045)
        mv = int(ph * 0.048)
        x  = px + mh
        y  = py + mv
        tw = pw - mh * 2

        titre = self.police_titre.render("L'Univers d'Écho", True, self.MAUVE)
        self.ecran.blit(titre, (x, y))
        y += titre.get_height() + 3

        sous = self.police_texte.render("L'histoire et le monde derrière l'obscurité",
                                        True, (70, 55, 110))
        self.ecran.blit(sous, (x, y))
        y += sous.get_height() + 10

        _separateur_gradient(self.ecran, x, y, tw, self.MAUVE, self.VIOLET)
        y += 14

        col_w  = (tw - mh) // 2
        col2_x = x + col_w + mh

        self._lore_gauche(x, y, col_w)
        self._lore_droite(col2_x, y, col_w)

    def _lore_gauche(self, x, y, w):
        y = y + _badge(self.ecran, self.police_bouton,
                       "  LE GRAND SILENCE", x, y, self.MAUVE, self.MAUVE, 22, 75)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "Il y a cent ans, le « Grand Silence »\n"
                        "a plongé le monde dans une obscurité\n"
                        "totale et permanente.\n\n"
                        "Les villes sont devenues des labyrinthes\n"
                        "peuplés de créatures corrompues\n"
                        "par l'absence de lumière.",
                        x, y, w, (155, 145, 200))
        y += 12

        y = y + _badge(self.ecran, self.police_bouton,
                       "  LA PORTE INTERDITE", x, y, self.OR, self.OR, 20, 70)
        _texte_wrap(self.ecran, self.police_texte,
                    "Au cœur des ruines :\n"
                    "« La Porte de l'Aurore ».\n\n"
                    "Derrière elle, la Première Lumière —\n"
                    "seule capable d'inverser le Silence.",
                    x, y, w, (155, 145, 200))

    def _lore_droite(self, x, y, w):
        y = y + _badge(self.ecran, self.police_bouton,
                       "  TU ES L'ÉCLAIREUR", x, y, self.CYAN, self.CYAN, 25, 80)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "Tu maîtrises l'Art de l'Écho —\n"
                        "une technique permettant de percevoir\n"
                        "le monde par le son.\n\n"
                        "Là où les autres voient le néant,\n"
                        "toi tu entends contours et dangers.",
                        x, y, w, (155, 145, 200))
        y += 10

        y = y + _badge(self.ecran, self.police_bouton,
                       "  LES ÂMES ERRANTES", x, y, self.ROSE, self.ROSE, 20, 70)
        y = _texte_wrap(self.ecran, self.police_texte,
                        "Ce sont des âmes corrompues par\n"
                        "le Silence, piégées entre deux mondes.\n\n"
                        "En les vaincant tu libères leur énergie.",
                        x, y, w, (155, 145, 200))
        y += 12

        # Call-to-action final
        bloc_h = self.police_texte.get_height() * 3 + 26
        _bloc_highlight(self.ecran, x, y, w - 10, bloc_h, self.CYAN, 15, 200)
        cta_lines = ["Traverse les ruines. Bats les gardiens.",
                     "Trouve la clé. Ouvre la Porte.",
                     "Ramène la lumière."]
        yb = y + 10
        for line in cta_lines:
            s = self.police_texte.render(line, True, self.CYAN)
            self.ecran.blit(s, (x + 14, yb))
            yb += s.get_height() + 6

    # ------------------------------------------------------------------
    #  Navigation
    # ------------------------------------------------------------------

    def _navigation(self, tms):
        est_derniere = (self.index == self.total - 1)
        if est_derniere:
            self.btn_fermer.dessiner(self.ecran)
        else:
            self.btn_suivant.dessiner(self.ecran)
        if self.index > 0:
            self.btn_precedent.dessiner(self.ecran)
        self.btn_passer.dessiner(self.ecran)

    def _indicateur(self):
        rayon  = 5
        espace = 18
        total_w = self.total * rayon * 2 + (self.total - 1) * espace
        x0 = self.cx - total_w // 2
        y  = self.hauteur - 14

        for i in range(self.total):
            cx = x0 + i * (rayon * 2 + espace) + rayon
            if i == self.index:
                # Point actif avec halo
                halo = pygame.Surface((rayon * 4, rayon * 4), pygame.SRCALPHA)
                pygame.draw.circle(halo, (*self.CYAN, 40), (rayon * 2, rayon * 2), rayon * 2)
                self.ecran.blit(halo, (cx - rayon * 2, y - rayon * 2))
                pygame.draw.circle(self.ecran, self.CYAN, (cx, y), rayon)
            else:
                pygame.draw.circle(self.ecran, (50, 40, 80), (cx, y), rayon - 1)
                pygame.draw.circle(self.ecran, (80, 65, 120), (cx, y), rayon - 1, 1)