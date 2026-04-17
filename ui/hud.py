# ui/hud.py
# Mixin pour le HUD en jeu.
# Indicateur Echo repensé : grand, lisible, avec label explicite et animation d'activation.

import pygame
import math
import os
import sys

from parametres import *
from utils import envoyer_logs


class HudMixin:
    """Méthodes d'affichage du HUD en jeu."""

    # ------------------------------------------------------------------
    #  CACHE HUD (fonts + surfaces réutilisables)
    # ------------------------------------------------------------------

    def _init_hud_cache(self):
        """Initialise les fonts et surfaces cachées du HUD. Appelé une seule fois."""
        if hasattr(self, '_hud_cache_ok'):
            return
        self._font_echo_icon   = pygame.font.Font(None, max(20, 22))  # rayon=22
        self._font_label_small = pygame.font.Font(None, 16)
        self._font_label_medium = pygame.font.Font(None, 22)
        self._font_capacite    = pygame.font.Font(None, 13)
        # Surfaces réutilisables pour le widget echo (taille fixe)
        self._widget_surf_cache = pygame.Surface((130, 22 * 2 + 4), pygame.SRCALPHA)
        self._surf_c_cache      = pygame.Surface((22 * 2 + 2, 22 * 2 + 2), pygame.SRCALPHA)
        # Surface halo flash ennemi (60x60)
        self._flash_halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        # Cache des surfaces tmp flash par taille d'ennemi
        self._flash_tmp_cache = {}
        # Surface overlay debug
        self._debug_panel_cache = None
        # Surface overlay mort
        self._mort_overlay_cache = None
        self._mort_overlay_size  = None
        self._hud_cache_ok = True

    # ------------------------------------------------------------------
    #  ENTRÉE PRINCIPALE
    # ------------------------------------------------------------------

    def dessiner_hud(self):
        """Dessine le HUD complet."""
        self._init_hud_cache()
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur:
            return

        x0 = 24
        y0 = 24

        # PV
        lc  = max(24, self.largeur_ecran // 60)   # largeur coeur
        hc  = max(20, self.hauteur_ecran // 45)   # hauteur coeur
        pad = 6
        for i in range(mon_joueur.pv_max):
            rx = x0 + i * (lc + pad)
            pygame.draw.rect(self.ecran, COULEUR_PV_PERDU,
                             pygame.Rect(rx, y0, lc, hc), border_radius=4)
            pygame.draw.rect(self.ecran, COULEUR_CYAN_SOMBRE,
                             pygame.Rect(rx, y0, lc, hc), width=1, border_radius=4)
        for i in range(mon_joueur.pv):
            rx = x0 + i * (lc + pad)
            pygame.draw.rect(self.ecran, COULEUR_PV,
                             pygame.Rect(rx, y0, lc, hc), border_radius=4)

        # Barre boss
        if hasattr(self, '_derniere_data_boss') and self._derniere_data_boss:
            d = self._derniere_data_boss
            if d.get('fight_started') and not d.get('boss_defeated'):
                bd = d['boss']
                self._dessiner_barre_boss(bd['hp'], bd['hp_max'])

        # Argent
        argent_surf = self.police_texte.render(
            f"Âmes : {mon_joueur.argent}", True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(argent_surf, (x0, y0 + hc + 10))

        # Clé
        y_cur = y0 + hc + 10 + argent_surf.get_height() + 6
        if getattr(mon_joueur, 'have_key', False):
            self._dessiner_icone_cle(x0, y_cur)
            y_cur += 24

        # Indicateur Echo (le plus important après les PV)
        y_cur += 4
        self._dessiner_indicateur_echo(x0, y_cur, mon_joueur)
        y_cur += 68   # hauteur du widget echo

        # Capacités débloquées
        self._dessiner_indicateurs_capacites(x0, y_cur, mon_joueur)

        if MODE_DEV:
            self._dessiner_debug_hud()


    # ------------------------------------------------------------------
    #  INDICATEUR COOLDOWN ECHO — WIDGET COMPLET
    # ------------------------------------------------------------------

    def _dessiner_indicateur_echo(self, x, y, joueur):
        """
        Widget d'indicateur de cooldown Echo.

        Layout :
          [ cercle 28px ] [ label  ]
                           ECHO
                           PRÊT  ← vert quand dispo
                           ou
                           1.8s  ← décompte rouge→jaune→vert

        Le cercle est un arc qui se remplit dans le sens horaire
        depuis le haut (12h). Vide = vient d'être utilisé, plein = prêt.
        Une animation de flash pulse brièvement à l'activation.
        """
        temps_actuel = pygame.time.get_ticks()
        rayon        = 22
        cx_cercle    = x + rayon
        cy_cercle    = y + rayon

        dernier_echo = getattr(joueur, 'dernier_echo_temps', 0)
        elapsed      = temps_actuel - dernier_echo
        ratio        = min(1.0, elapsed / COOLDOWN_ECHO)  # 0=juste utilisé, 1=prêt
        pret         = ratio >= 1.0

        # ---- Fond du widget (panneau semi-transparent) ----
        widget_surf = self._widget_surf_cache
        widget_surf.fill((0, 0, 0, 0))
        widget_surf.fill((8, 6, 20, 160))
        pygame.draw.rect(widget_surf, (30, 20, 60, 180),
                         widget_surf.get_rect(), width=1, border_radius=6)
        self.ecran.blit(widget_surf, (x - 2, y - 2))

        # ---- Cercle de cooldown ----
        surf_c = self._surf_c_cache
        surf_c.fill((0, 0, 0, 0))
        scx    = rayon + 1
        scy    = rayon + 1

        # Piste de fond (anneau gris)
        pygame.draw.circle(surf_c, (25, 18, 45, 220), (scx, scy), rayon)
        pygame.draw.circle(surf_c, (50, 35, 80, 255), (scx, scy), rayon, width=2)

        if pret:
            # Cercle plein cyan pulsant
            pulse = 0.82 + 0.18 * math.sin(temps_actuel / 450)
            r, g, b = COULEUR_CYAN
            # Remplissage intérieur semi-transparent
            pygame.draw.circle(surf_c, (r, g, b, int(60 * pulse)), (scx, scy), rayon - 3)
            # Anneau lumineux
            pygame.draw.circle(surf_c, (r, g, b, 255), (scx, scy), rayon, width=3)
            # Halo externe pulsant
            halo_r = int((rayon + 5) * pulse)
            pygame.draw.circle(surf_c, (r, g, b, int(40 * pulse)), (scx, scy), halo_r, width=2)
        else:
            # Arc de progression — dessine N petits secteurs pour simuler l'arc
            self._dessiner_arc_cooldown(surf_c, scx, scy, rayon - 2, ratio)
            # Bord fixe de la piste
            pygame.draw.circle(surf_c, (55, 38, 85, 200), (scx, scy), rayon, width=1)

        # Flash d'activation (dans les 200ms suivant l'utilisation)
        if 0 <= elapsed < 200:
            flash_alpha = min(255, int(180 * (1.0 - elapsed / 200)))
            pygame.draw.circle(surf_c, (255, 255, 255, flash_alpha), (scx, scy), rayon - 4)

        # Icône centrale "E" (touche d'activation)
        couleur_e = COULEUR_CYAN if pret else (100, 80, 140)
        icone_e = self._font_echo_icon.render("E", True, couleur_e)
        surf_c.blit(icone_e, icone_e.get_rect(center=(scx, scy)))

        self.ecran.blit(surf_c, (cx_cercle - rayon - 1, cy_cercle - rayon - 1))

        # ---- Labels à droite du cercle ----
        lx = cx_cercle + rayon + 10
        ly = cy_cercle - 18

        # Ligne 1 : mot "ECHO" en petit gris
        label_titre = self._font_label_small.render("ECHO", True, (100, 85, 130))
        self.ecran.blit(label_titre, (lx, ly))
        ly += label_titre.get_height() + 2

        # Ligne 2 : état principal — grand, lisible
        if pret:
            # "PRÊT" en vert/cyan lumineux
            etat_surf = self._font_label_medium.render("PRÊT", True, COULEUR_CYAN)
        else:
            # Décompte en secondes avec couleur progressive
            restant   = (COOLDOWN_ECHO - elapsed) / 1000
            t_ratio   = 1.0 - ratio           # 1 = vient d'être utilisé, 0 = presque prêt
            r_c = int(220 * t_ratio + 0   * (1 - t_ratio))
            g_c = int(60  * t_ratio + 200 * (1 - t_ratio))
            b_c = int(60  * t_ratio + 80  * (1 - t_ratio))
            etat_surf = self._font_label_medium.render(f"{restant:.1f}s", True, (r_c, g_c, b_c))

        self.ecran.blit(etat_surf, (lx, ly))
        ly += etat_surf.get_height() + 2

        # Ligne 3 : barre de progression linéaire fine sous le texte
        bar_w   = 68
        bar_h   = 3
        bar_rect = pygame.Rect(lx, ly, bar_w, bar_h)
        pygame.draw.rect(self.ecran, (40, 28, 60), bar_rect, border_radius=2)
        if ratio > 0:
            fill_w = int(bar_w * ratio)
            r_b = int(180 * (1 - ratio) + 0   * ratio)
            g_b = int(60  * (1 - ratio) + 210 * ratio)
            b_b = int(60  * (1 - ratio) + 190 * ratio)
            pygame.draw.rect(self.ecran, (r_b, g_b, b_b),
                             pygame.Rect(lx, ly, fill_w, bar_h), border_radius=2)

    def _dessiner_arc_cooldown(self, surf, cx, cy, rayon, ratio):
        """
        Dessine un arc de progression de 0° à ratio*360°, sens horaire depuis 12h.
        Utilisé pendant le cooldown. Couleur : rouge vif → jaune → cyan.
        """
        if ratio <= 0:
            return

        nb_points = max(4, int(ratio * 16))  # résolution de l'arc
        epaisseur  = 4                         # épaisseur de la piste colorée
        angle_debut = -math.pi / 2             # 12h = -90°

        for i in range(nb_points):
            t_local = i / nb_points             # 0 à 1 sur la portion de l'arc
            angle   = angle_debut + t_local * ratio * 2 * math.pi

            # Couleur : rouge vif (début) → orange → jaune → cyan (fin)
            # interpolée sur l'avancement de l'arc
            r_c = int(220 * (1 - t_local * ratio) + 0   * (t_local * ratio))
            g_c = int(50  * (1 - t_local * ratio) + 200 * (t_local * ratio))
            b_c = int(50  * (1 - t_local * ratio) + 195 * (t_local * ratio))

            # On dessine des petits cercles le long de l'arc pour éviter les gaps
            px = int(cx + math.cos(angle) * rayon)
            py = int(cy + math.sin(angle) * rayon)
            pygame.draw.circle(surf, (r_c, g_c, b_c, 240), (px, py), epaisseur // 2 + 1)

        # Point de tête (bout de l'arc) — plus lumineux
        angle_fin = angle_debut + ratio * 2 * math.pi
        px_fin    = int(cx + math.cos(angle_fin) * rayon)
        py_fin    = int(cy + math.sin(angle_fin) * rayon)
        pygame.draw.circle(surf, (255, 255, 255, 200), (px_fin, py_fin), epaisseur // 2)

    # ------------------------------------------------------------------
    #  CAPACITÉS DÉBLOQUÉES
    # ------------------------------------------------------------------

    def _dessiner_indicateurs_capacites(self, x, y, joueur):
        """Petites pastilles pour les capacités actives."""
        taille  = 16
        espace  = 4
        cx      = x
        capacites = []
        if getattr(joueur, 'peut_double_saut', False):
            capacites.append(('↑↑', (80, 160, 255)))
        if getattr(joueur, 'peut_dash',        False):
            capacites.append(('»',  (180, 80, 255)))
        if getattr(joueur, 'peut_echo_dir',    False):
            capacites.append(('◎',  (0, 200, 180)))
        for icone, couleur in capacites:
            pygame.draw.circle(self.ecran, couleur,
                               (cx + taille // 2, y + taille // 2), taille // 2)
            s = self._font_capacite.render(icone, True, (255, 255, 255))
            self.ecran.blit(s, s.get_rect(center=(cx + taille // 2, y + taille // 2)))
            cx += taille + espace

    # ------------------------------------------------------------------
    #  CLÉ
    # ------------------------------------------------------------------

    def _dessiner_icone_cle(self, x, y):
        if not hasattr(self, '_sprite_cle_hud'):
            try:
                base = (sys._MEIPASS if getattr(sys, 'frozen', False)
                        else os.path.dirname(os.path.dirname(__file__)))
                img  = pygame.image.load(os.path.join(base, 'assets', 'cle.png')).convert_alpha()
                self._sprite_cle_hud = pygame.transform.scale(img, (18, 18))
            except Exception:
                self._sprite_cle_hud = None

        if self._sprite_cle_hud:
            self.ecran.blit(self._sprite_cle_hud, (x, y))
        else:
            pygame.draw.rect(self.ecran, (255, 215, 0),
                             pygame.Rect(x, y, 14, 14), border_radius=3)
        lbl = self.police_texte.render("Clé", True, (255, 215, 0))
        self.ecran.blit(lbl, (x + 20, y + 1))

    # ------------------------------------------------------------------
    #  DEBUG
    # ------------------------------------------------------------------

    def _dessiner_debug_hud(self):
        fps = self.horloge.get_fps()
        couleur_fps = ((0, 220, 120) if fps >= FPS * 0.85
                       else (255, 180, 0) if fps >= FPS * 0.5
                       else (255, 60, 60))
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        lignes = [
            (f"FPS : {fps:.0f} / {FPS}", couleur_fps),
            (f"Pos : {mon_joueur.rect.x}, {mon_joueur.rect.y}" if mon_joueur else "Pos : —",
             COULEUR_TEXTE_SOMBRE),
            (f"Joueurs : {len(self.joueurs_locaux)}",  COULEUR_TEXTE_SOMBRE),
            (f"Ennemis : {len(self.ennemis_locaux)}",  COULEUR_TEXTE_SOMBRE),
            (f"Entités : {len(self.joueurs_locaux)+len(self.ennemis_locaux)+len(self.ames_perdues_locales)+len(self.ames_libres_locales)}",
             COULEUR_TEXTE_SOMBRE),
            (f"Torche : {'ON' if self.torche.allumee else 'OFF'}",
             (255, 160, 30) if self.torche.allumee else COULEUR_TEXTE_SOMBRE),
        ]
        p      = self.police_petit
        lh     = p.get_height() + 4
        pad    = 8
        lw_pan = 160
        ht_pan = len(lignes) * lh + pad * 2
        x0     = self.largeur_ecran - lw_pan - 12
        y0     = 12
        if self._debug_panel_cache is None or self._debug_panel_cache.get_size() != (lw_pan, ht_pan):
            self._debug_panel_cache = pygame.Surface((lw_pan, ht_pan), pygame.SRCALPHA)
        panel = self._debug_panel_cache
        panel.fill((8, 8, 20, 180))
        pygame.draw.rect(panel, COULEUR_CYAN_SOMBRE,
                         panel.get_rect(), width=1, border_radius=6)
        self.ecran.blit(panel, (x0, y0))
        for i, (texte, couleur) in enumerate(lignes):
            self.ecran.blit(p.render(texte, True, couleur),
                            (x0 + pad, y0 + pad + i * lh))

    # ------------------------------------------------------------------
    #  MORT
    # ------------------------------------------------------------------

    def _dessiner_ecran_mort(self, surface):
        if self._mort_depuis is None:
            self._mort_depuis = pygame.time.get_ticks()
        elapsed = pygame.time.get_ticks() - self._mort_depuis
        alpha   = min(200, int(200 * min(elapsed, 800) / 800))
        sz = surface.get_size()
        if self._mort_overlay_cache is None or self._mort_overlay_size != sz:
            self._mort_overlay_cache = pygame.Surface(sz, pygame.SRCALPHA)
            self._mort_overlay_size = sz
        self._mort_overlay_cache.fill((80, 0, 0, alpha))
        surface.blit(self._mort_overlay_cache, (0, 0))
        if elapsed > 600:
            if not hasattr(self, '_police_mort'):
                self._police_mort = pygame.font.Font(None, 48)
                self._police_sub  = pygame.font.Font(None, 28)
            lw, lh = surface.get_size()
            t1 = self._police_mort.render("VOUS ETES MORT", True, (220, 50, 50))
            t2 = self._police_sub.render("Respawn en cours...", True, (160, 100, 100))
            surface.blit(t1, t1.get_rect(center=(lw // 2, lh // 2 - 20)))
            surface.blit(t2, t2.get_rect(center=(lw // 2, lh // 2 + 20)))

    # ------------------------------------------------------------------
    #  BOSS
    # ------------------------------------------------------------------

    def _dessiner_barre_boss(self, hp, hp_max):
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


    def _dessiner_badge_torche(self, surface, camera_offset):
        """
        Affiche un petit badge [L] au-dessus de la torche
        pour indiquer la touche d'interaction, avant la première utilisation.
        """
        if not hasattr(self, '_font_badge_torche'):
            self._font_badge_torche = pygame.font.Font(None, 18)

        off_x, off_y = camera_offset
        temps_ms = pygame.time.get_ticks()

        # Position : centré au-dessus du sprite torche, avec flottement
        flottement = math.sin(temps_ms / 400) * 3
        bx = self.torche.x + TAILLE_TUILE // 2 - off_x
        by = self.torche.y - 18 + int(flottement) - off_y

        # Nom de la touche (depuis les paramètres, fallback "L")
        nom_touche = self.parametres.get('controles', {}).get('torche', 'l').upper()

        # Fond arrondi
        label = self._font_badge_torche.render(nom_touche, True, (255, 255, 255))
        pad_x, pad_y = 6, 3
        w = label.get_width() + pad_x * 2
        h = label.get_height() + pad_y * 2
        badge = pygame.Surface((w, h), pygame.SRCALPHA)
        badge.fill((0, 0, 0, 0))
        pygame.draw.rect(badge, (30, 20, 60, 210),
                        badge.get_rect(), border_radius=4)
        pygame.draw.rect(badge, COULEUR_CYAN_SOMBRE,
                        badge.get_rect(), width=1, border_radius=4)
        badge.blit(label, (pad_x, pad_y))

        surface.blit(badge, (bx - w // 2, by - h))

        # Petite flèche pointant vers la torche
        arrow_x = bx
        arrow_y = by + 2
        pygame.draw.polygon(surface, COULEUR_CYAN_SOMBRE, [
            (arrow_x - 4, arrow_y),
            (arrow_x + 4, arrow_y),
            (arrow_x,     arrow_y + 5),
        ])