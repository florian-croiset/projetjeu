# ui/hud.py
# Mixin pour le HUD en jeu (vie, argent, boss, mort, debug, cooldown Echo).
# Hérité par la classe Client.

import pygame
import math
import os
import sys

from parametres import *
from utils import envoyer_logs


class HudMixin:
    """Méthodes d'affichage du HUD en jeu."""

    def _dessiner_icone_cle(self, x, y):
        """Dessine l'icône de clé dans le HUD avec texte."""
        if not hasattr(self, '_sprite_cle_hud'):
            try:
                if getattr(sys, 'frozen', False):
                    base = sys._MEIPASS
                else:
                    base = os.path.dirname(os.path.dirname(__file__))
                chemin = os.path.join(base, 'assets', 'cle.png')
                img = pygame.image.load(chemin).convert_alpha()
                self._sprite_cle_hud = pygame.transform.scale(img, (18, 18))
            except Exception:
                self._sprite_cle_hud = None

        if self._sprite_cle_hud:
            self.ecran.blit(self._sprite_cle_hud, (x, y))
            lbl = self.police_texte.render("  Clé", True, (255, 215, 0))
            self.ecran.blit(lbl, (x + 20, y))
        else:
            pygame.draw.rect(self.ecran, (255, 215, 0),
                             pygame.Rect(x, y, 14, 14), border_radius=3)
            lbl = self.police_texte.render("  Clé", True, (255, 215, 0))
            self.ecran.blit(lbl, (x + 16, y))

    def dessiner_hud(self):
        """Dessine le HUD complet (vie, argent, clé, echo, boss, debug)."""
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur:
            return

        pv     = mon_joueur.pv
        pv_max = mon_joueur.pv_max

        largeur_coeur = max(24, self.largeur_ecran // 60)
        hauteur_coeur = max(20, self.hauteur_ecran // 45)
        padding = 6
        x0 = 24
        y0 = 24

        # --- Barres de PV ---
        for i in range(pv_max):
            rx = x0 + i * (largeur_coeur + padding)
            fond_r = pygame.Rect(rx, y0, largeur_coeur, hauteur_coeur)
            pygame.draw.rect(self.ecran, COULEUR_PV_PERDU, fond_r, border_radius=4)
            pygame.draw.rect(self.ecran, COULEUR_CYAN_SOMBRE, fond_r,
                             width=1, border_radius=4)

        for i in range(pv):
            rx = x0 + i * (largeur_coeur + padding)
            plein_r = pygame.Rect(rx, y0, largeur_coeur, hauteur_coeur)
            pygame.draw.rect(self.ecran, COULEUR_PV, plein_r, border_radius=4)

        # --- Barre Boss ---
        if hasattr(self, '_derniere_data_boss') and self._derniere_data_boss:
            d = self._derniere_data_boss
            if d.get('fight_started') and not d.get('boss_defeated'):
                boss_data = d['boss']
                self._dessiner_barre_boss(boss_data['hp'], boss_data['hp_max'])

        # --- Argent ---
        argent_txt = self.police_texte.render(
            f"Âmes : {mon_joueur.argent}", True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(argent_txt, (x0, y0 + hauteur_coeur + 10))

        # --- Clé ---
        if hasattr(mon_joueur, 'have_key') and mon_joueur.have_key:
            y_inv = y0 + hauteur_coeur + 36
            self._dessiner_icone_cle(x0, y_inv)

        # --- Indicateur cooldown Echo ---
        y_echo = y0 + hauteur_coeur + 62
        self._dessiner_indicateur_echo(x0, y_echo, mon_joueur)

        # --- Capacités débloquées ---
        y_cap = y_echo + 46
        self._dessiner_indicateurs_capacites(x0, y_cap, mon_joueur)

        if MODE_DEV:
            self._dessiner_debug_hud()

    # ------------------------------------------------------------------
    #  INDICATEUR COOLDOWN ECHO
    # ------------------------------------------------------------------

    def _dessiner_indicateur_echo(self, x, y, joueur):
        """
        Cercle de cooldown pour l'Echo.
        - Plein et cyan  : Echo disponible.
        - Arc qui se remplit progressivement : cooldown en cours.
        - Animation de flash au déclenchement.
        """
        temps_actuel = pygame.time.get_ticks()
        rayon        = 18
        cx           = x + rayon
        cy           = y + rayon

        dernier_echo = getattr(joueur, 'dernier_echo_temps', 0)
        elapsed      = temps_actuel - dernier_echo
        ratio_rempli = min(1.0, elapsed / COOLDOWN_ECHO)   # 0 = juste utilisé, 1 = prêt
        pret         = (ratio_rempli >= 1.0)

        # Surface SRCALPHA pour les dessins transparents
        taille_surf = (rayon * 2 + 4, rayon * 2 + 4)
        surf = pygame.Surface(taille_surf, pygame.SRCALPHA)
        scx  = rayon + 2
        scy  = rayon + 2

        # Fond sombre
        pygame.draw.circle(surf, (10, 8, 25, 200), (scx, scy), rayon)

        if pret:
            # Disponible : cercle plein cyan avec légère pulsation
            pulse = 0.8 + 0.2 * math.sin(temps_actuel / 600)
            a     = int(220 * pulse)
            pygame.draw.circle(surf, (*COULEUR_CYAN, a), (scx, scy), rayon - 3)
            pygame.draw.circle(surf, (*COULEUR_CYAN, 255), (scx, scy), rayon, width=2)
        else:
            # Cooldown : arc progressif
            # Arc de fond (gris)
            pygame.draw.circle(surf, (40, 40, 60, 180), (scx, scy), rayon - 2)
            pygame.draw.circle(surf, (60, 60, 90, 220), (scx, scy), rayon, width=2)

            # Arc coloré indiquant la progression
            if ratio_rempli > 0.02:
                angle_fin  = -90 + ratio_rempli * 360   # commence en haut
                # Dessin de l'arc avec des segments fins
                nb_segs    = max(4, int(ratio_rempli * 32))
                for i in range(nb_segs):
                    a_deg_start = -90 + (i / nb_segs) * ratio_rempli * 360
                    a_deg_end   = -90 + ((i + 1) / nb_segs) * ratio_rempli * 360
                    a_start = math.radians(a_deg_start)
                    a_end   = math.radians(a_deg_end)
                    # Point sur le cercle
                    p1 = (scx + math.cos(a_start) * (rayon - 2),
                           scy + math.sin(a_start) * (rayon - 2))
                    p2 = (scx + math.cos(a_end)   * (rayon - 2),
                           scy + math.sin(a_end)   * (rayon - 2))
                    p3 = (scx + math.cos(a_end)   * (rayon - 6),
                           scy + math.sin(a_end)   * (rayon - 6))
                    p4 = (scx + math.cos(a_start) * (rayon - 6),
                           scy + math.sin(a_start) * (rayon - 6))
                    # Couleur : cyan→violet selon progression
                    t_col = i / max(1, nb_segs - 1)
                    r_c   = int(COULEUR_CYAN[0] * (1 - t_col) + COULEUR_VIOLET[0] * t_col)
                    g_c   = int(COULEUR_CYAN[1] * (1 - t_col) + COULEUR_VIOLET[1] * t_col)
                    b_c   = int(COULEUR_CYAN[2] * (1 - t_col) + COULEUR_VIOLET[2] * t_col)
                    pygame.draw.polygon(surf, (r_c, g_c, b_c, 230), [p1, p2, p3, p4])

        # Icône "E" au centre
        police_icone = pygame.font.Font(None, max(18, rayon))
        icone        = police_icone.render("E", True,
                                           COULEUR_CYAN if pret else COULEUR_TEXTE_SOMBRE)
        icone_rect   = icone.get_rect(center=(scx, scy))
        surf.blit(icone, icone_rect)

        self.ecran.blit(surf, (cx - rayon - 2, cy - rayon - 2))

        # Étiquette
        label_couleur = COULEUR_CYAN if pret else COULEUR_TEXTE_SOMBRE
        label_texte   = "Echo" if pret else f"Echo {(COOLDOWN_ECHO - elapsed) / 1000:.1f}s"
        label         = pygame.font.Font(None, 16).render(label_texte, True, label_couleur)
        self.ecran.blit(label, (cx + rayon + 6, cy - label.get_height() // 2))

    # ------------------------------------------------------------------
    #  INDICATEURS CAPACITÉS
    # ------------------------------------------------------------------

    def _dessiner_indicateurs_capacites(self, x, y, joueur):
        """Petites icônes indiquant les capacités débloquées."""
        taille = 16
        espace  = 4
        cx      = x

        capacites = []
        if getattr(joueur, 'peut_double_saut', False):
            capacites.append(('⬆', (80, 160, 255), 'Dbl Saut'))
        if getattr(joueur, 'peut_dash', False):
            capacites.append(('»', (180, 80, 255), 'Dash'))
        if getattr(joueur, 'peut_echo_dir', False):
            capacites.append(('◎', (0, 200, 180), 'Echo Dir'))

        for icone, couleur, nom in capacites:
            # Pastille
            pygame.draw.circle(self.ecran, couleur, (cx + taille // 2, y + taille // 2), taille // 2)
            p = pygame.font.Font(None, 14)
            s = p.render(icone, True, (255, 255, 255))
            self.ecran.blit(s, s.get_rect(center=(cx + taille // 2, y + taille // 2)))
            cx += taille + espace

    # ------------------------------------------------------------------
    #  DEBUG
    # ------------------------------------------------------------------

    def _dessiner_debug_hud(self):
        """Affiche les infos de performance en haut à droite (MODE_DEV)."""
        fps_actuel = self.horloge.get_fps()
        nb_joueurs = len(self.joueurs_locaux)
        nb_ennemis = len(self.ennemis_locaux)
        nb_ames    = len(self.ames_perdues_locales) + len(self.ames_libres_locales)
        nb_entites = nb_joueurs + nb_ennemis + nb_ames

        if fps_actuel >= FPS * 0.85:
            couleur_fps = (0, 220, 120)
        elif fps_actuel >= FPS * 0.5:
            couleur_fps = (255, 180, 0)
        else:
            couleur_fps = (255, 60, 60)

        lignes = [
            (f"FPS : {fps_actuel:.0f} / {FPS}", couleur_fps),
            (f"Joueurs : {nb_joueurs}", COULEUR_TEXTE_SOMBRE),
            (f"Ennemis : {nb_ennemis}", COULEUR_TEXTE_SOMBRE),
            (f"Entités : {nb_entites}", COULEUR_TEXTE_SOMBRE),
            (f"Torche : {'ON' if self.torche.allumee else 'OFF'}",
             (255, 160, 30) if self.torche.allumee else COULEUR_TEXTE_SOMBRE),
            (f"Zoom : x{ZOOM_CAMERA}", COULEUR_TEXTE_SOMBRE),
        ]

        police    = self.police_petit
        ligne_h   = police.get_height() + 4
        padding   = 8
        larg_panel = 160
        haut_panel = len(lignes) * ligne_h + padding * 2

        x0 = self.largeur_ecran - larg_panel - 12
        y0 = 12

        panel = pygame.Surface((larg_panel, haut_panel), pygame.SRCALPHA)
        panel.fill((8, 8, 20, 180))
        pygame.draw.rect(panel, COULEUR_CYAN_SOMBRE,
                         pygame.Rect(0, 0, larg_panel, haut_panel),
                         width=1, border_radius=6)
        self.ecran.blit(panel, (x0, y0))

        for i, (texte, couleur) in enumerate(lignes):
            surf = police.render(texte, True, couleur)
            self.ecran.blit(surf, (x0 + padding, y0 + padding + i * ligne_h))

    # ------------------------------------------------------------------
    #  MORT
    # ------------------------------------------------------------------

    def _dessiner_ecran_mort(self, surface):
        """Overlay de mort semi-transparent avec message."""
        if self._mort_depuis is None:
            self._mort_depuis = pygame.time.get_ticks()

        elapsed = pygame.time.get_ticks() - self._mort_depuis
        alpha   = min(200, int(200 * min(elapsed, 800) / 800))

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((80, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

        if elapsed > 600:
            if not hasattr(self, '_police_mort'):
                self._police_mort = pygame.font.Font(None, 48)
                self._police_sub  = pygame.font.Font(None, 28)
            lw, lh = surface.get_size()
            txt1 = self._police_mort.render("VOUS ETES MORT", True, (220, 50, 50))
            txt2 = self._police_sub.render("Respawn en cours...", True, (160, 100, 100))
            surface.blit(txt1, txt1.get_rect(center=(lw // 2, lh // 2 - 20)))
            surface.blit(txt2, txt2.get_rect(center=(lw // 2, lh // 2 + 20)))

    # ------------------------------------------------------------------
    #  BOSS
    # ------------------------------------------------------------------

    def _dessiner_barre_boss(self, hp, hp_max):
        """Barre de vie du boss fixée en haut de l'écran."""
        bar_w = 400
        bar_h = 16
        bar_x = self.largeur_ecran // 2 - bar_w // 2
        bar_y = 20
        ratio = max(0.0, hp / hp_max)

        pygame.draw.rect(self.ecran, (40, 10, 10),  (bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4))
        pygame.draw.rect(self.ecran, (90, 20, 20),  (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(self.ecran, (200, 50, 50), (bar_x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(self.ecran, (220, 180, 180), (bar_x, bar_y, bar_w, bar_h), 1)
        nom = self.police_petit.render("Demon Slime", True, (220, 180, 180))
        self.ecran.blit(nom, (bar_x, bar_y - 18))