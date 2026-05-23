# ui/hud.py
# Mixin pour le HUD en jeu.
# Indicateur Echo repensé : grand, lisible, avec label explicite et animation d'activation.

import pygame
import math
import os
import sys

from parametres import *
from utils import envoyer_logs
from utils.cache import render_text, creer_textes_echo_hud


class HudMixin:
    """Méthodes d'affichage du HUD en jeu."""

    # ------------------------------------------------------------------
    #  UTILITAIRES
    # ------------------------------------------------------------------

    @staticmethod
    def _format_touche_hud(key: str) -> str:
        """Convertit un nom de touche en label court pour les cercles HUD."""
        _MAP = {
            'space': 'SP', 'mouse_1': 'M1', 'mouse_2': 'M2', 'mouse_3': 'M3',
            'left': '←', 'right': '→', 'up': '↑', 'down': '↓',
            'return': 'RT', 'backspace': 'BS', 'tab': 'TB',
            'escape': 'EC', 'lshift': 'SH', 'rshift': 'SH',
            'lctrl': 'CT', 'rctrl': 'CT', 'lalt': 'AL', 'ralt': 'AL',
        }
        k = key.lower()
        if k in _MAP:
            return _MAP[k]
        return key[0].upper() if key else '?'

    # ------------------------------------------------------------------
    #  CACHE HUD (fonts + surfaces réutilisables)
    # ------------------------------------------------------------------

    def _init_hud_cache(self):
        """Initialise les fonts et surfaces cachées du HUD. Recrée les caches
        si la résolution écran a changé depuis le dernier appel."""
        h = self.hauteur_ecran
        w = self.largeur_ecran
        if getattr(self, '_hud_cache_res', None) == (w, h):
            return
        self._font_echo_icon    = pygame.font.Font(None, max(32, h // 28))
        self._font_label_small  = pygame.font.Font(None, max(22, h // 45))
        self._font_label_medium = pygame.font.Font(None, max(32, h // 32))
        self._font_capacite     = pygame.font.Font(None, max(20, h // 50))
        # Dimensions adaptatives du widget Echo
        self._echo_rayon   = max(18, h // 36)
        self._echo_bar_w   = max(50, h // 12)
        widget_w = self._echo_rayon * 2 + 12 + self._echo_bar_w + 8
        widget_h = self._echo_rayon * 2 + 4
        self._widget_surf_cache = pygame.Surface((widget_w, widget_h), pygame.SRCALPHA)
        self._surf_c_cache      = pygame.Surface((self._echo_rayon * 2 + 2,
                                                  self._echo_rayon * 2 + 2),
                                                 pygame.SRCALPHA)
        # Mini cooldown (dash / echo_dir) — même taille que l'écho
        self._mini_rayon = self._echo_rayon
        mini_r = self._mini_rayon
        mini_w = mini_r * 2 + 12 + self._echo_bar_w + 8
        mini_h = mini_r * 2 + 4
        self._mini_widget_cache  = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
        self._mini_circle_cache  = pygame.Surface((mini_r * 2 + 2, mini_r * 2 + 2), pygame.SRCALPHA)
        # Surface halo flash ennemi (60x60)
        self._flash_halo_surf = pygame.Surface((60, 60), pygame.SRCALPHA)
        # Cache des surfaces tmp flash par taille d'ennemi
        self._flash_tmp_cache = {}
        # Surface overlay debug
        self._debug_panel_cache = None
        # Surface overlay mort
        self._mort_overlay_cache = None
        self._mort_overlay_size  = None
        # Pré-rendus de textes statiques du widget Echo (centralisés)
        self._txt_echo = creer_textes_echo_hud(
            self._font_label_small,
            self._font_label_medium,
            self._font_echo_icon,
        )
        self._hud_cache_res = (w, h)

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

        # Argent — compteur animé 1 par 1
        cible = mon_joueur.argent
        if not hasattr(self, '_argent_affiche'):
            self._argent_affiche = cible
            self._t_argent_ms = 0
        now_hud = pygame.time.get_ticks()
        if self._argent_affiche < cible:
            if now_hud - self._t_argent_ms >= 50:
                self._argent_affiche += 1
                self._t_argent_ms = now_hud
        else:
            self._argent_affiche = cible  # sync si argent dépensé
        argent_surf = self.police_texte.render(
            f"Âmes : {self._argent_affiche}", True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(argent_surf, (x0, y0 + hc + 10))

        # Clé
        y_cur = y0 + hc + 10 + argent_surf.get_height() + 6
        if getattr(mon_joueur, 'have_key', False):
            self._dessiner_icone_cle(x0, y_cur)
            y_cur += 24

        # Indicateur Echo (le plus important après les PV)
        y_cur += 4
        self._dessiner_indicateur_echo(x0, y_cur, mon_joueur)
        y_cur += self._echo_rayon * 2 + 10

        # Mini-cooldowns capacités (dash + écho directionnel) + pastille double saut
        y_cur = self._dessiner_indicateurs_capacites(x0, y_cur, mon_joueur)

        # Icône journal — en haut à droite
        if hasattr(self, 'widget_quete') and self.widget_quete:
            self.widget_quete.mettre_a_jour(
                self.cle_locale,
                next(iter(self.portes_locales.values()), None),
                self.boss_local,
                ennemis_tues=getattr(self, '_ennemis_tues_total', 0),
                ames=getattr(self, '_ames_recoltees_total', 0))
            touche_journal = self.parametres.get('controles', {}).get('journal', 'i')
            x_journal = self.largeur_ecran - 100
            self.widget_quete.dessiner(self.ecran, y_offset=24, touche_journal=touche_journal,
                                       x_offset=x_journal)

        self._dessiner_notification_capacite()

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
        rayon        = self._echo_rayon
        cx_cercle    = x + rayon
        cy_cercle    = y + rayon

        dernier_echo = getattr(joueur, 'dernier_echo_temps', 0)
        elapsed      = temps_actuel - dernier_echo
        ratio        = max(0.0, min(1.0, elapsed / COOLDOWN_ECHO))  # 0=juste utilisé, 1=prêt
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

        # Icône centrale : touche d'activation lue depuis les paramètres
        _key_echo = self.parametres.get('controles', {}).get('echo', 'e')
        _label_echo = self._format_touche_hud(_key_echo)
        couleur_icone = COULEUR_CYAN if pret else (100, 80, 140)
        icone_e = render_text(self._font_echo_icon, _label_echo, couleur_icone)
        surf_c.blit(icone_e, icone_e.get_rect(center=(scx, scy)))

        self.ecran.blit(surf_c, (cx_cercle - rayon - 1, cy_cercle - rayon - 1))

        # ---- Labels à droite du cercle ----
        lx = cx_cercle + rayon + 10
        ly = cy_cercle - 18

        # Ligne 1 : mot "ECHO" en petit gris — pré-rendu
        label_titre = self._txt_echo['echo_label']
        self.ecran.blit(label_titre, (lx, ly))
        ly += label_titre.get_height() + 2

        # Ligne 2 : état principal — grand, lisible
        if pret:
            # "PRÊT" en vert/cyan lumineux — pré-rendu
            etat_surf = self._txt_echo['echo_pret']
        else:
            # Décompte en secondes avec couleur progressive
            restant   = max(0.0, (COOLDOWN_ECHO - elapsed) / 1000)
            t_ratio   = 1.0 - ratio           # 1 = vient d'être utilisé, 0 = presque prêt
            r_c = int(220 * t_ratio + 0   * (1 - t_ratio))
            g_c = int(60  * t_ratio + 200 * (1 - t_ratio))
            b_c = int(60  * t_ratio + 80  * (1 - t_ratio))
            # render_text mémoïse par (font, texte, couleur) — ~25 valeurs distinctes
            # pour un cooldown 2.5s affiché au dixième.
            etat_surf = render_text(self._font_label_medium, f"{restant:.1f}s", (r_c, g_c, b_c))

        self.ecran.blit(etat_surf, (lx, ly))
        ly += etat_surf.get_height() + 2

        # Ligne 3 : barre de progression linéaire fine sous le texte
        bar_w   = self._echo_bar_w
        bar_h   = max(3, self.hauteur_ecran // 360)
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
        """Pastille double saut + mini-cooldowns dash et écho directionnel."""
        rayon  = max(10, self.hauteur_ecran // 60)
        espace = max(6, rayon // 2)
        cx     = x + rayon
        cy     = y + rayon

        def _pastille(surface, cx, cy, r, couleur):
            pygame.draw.circle(surface, couleur, (cx, cy), r)
            r2, g2, b2 = min(couleur[0]+60, 255), min(couleur[1]+60, 255), min(couleur[2]+60, 255)
            pygame.draw.circle(surface, (r2, g2, b2), (cx, cy), r, 2)

        def _icone_double_saut(surface, cx, cy, r):
            ep = max(1, r // 5)
            w  = max(4, r // 2)
            for dy_off in (-r // 4, r // 3):
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off + w//2), (cx, cy + dy_off - w//2), ep)
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off - w//2), (cx - w//2, cy + dy_off), ep)
                pygame.draw.line(surface, (255, 255, 255),
                                 (cx, cy + dy_off - w//2), (cx + w//2, cy + dy_off), ep)

        y_cur = y

        # Pastille double saut (pas de cooldown à afficher)
        if getattr(joueur, 'peut_double_saut', False):
            _pastille(self.ecran, cx, cy, rayon, (80, 160, 255))
            _icone_double_saut(self.ecran, cx, cy, rayon)
            y_cur = cy + rayon + espace

        # Mini-cooldown dash
        if getattr(joueur, 'peut_dash', False):
            _dash_key = self.parametres.get('controles', {}).get('dash', 'c')
            y_cur = self._dessiner_mini_cooldown(
                x, y_cur,
                touche_label=self._format_touche_hud(_dash_key),
                titre='DASH',
                couleur_pastille=(180, 80, 255),
                dernier_temps=getattr(joueur, 'dernier_dash_temps', 0),
                cooldown_ms=COOLDOWN_DASH,
                icone_fn=self._dessiner_icone_mini_dash,
            )
            y_cur += espace

        # Mini-cooldown écho directionnel
        if getattr(joueur, 'peut_echo_dir', False):
            _echo_dir_key = self.parametres.get('controles', {}).get('echo_dir', 'y')
            y_cur = self._dessiner_mini_cooldown(
                x, y_cur,
                touche_label=self._format_touche_hud(_echo_dir_key),
                titre='ÉCH.DIR',
                couleur_pastille=(0, 200, 180),
                dernier_temps=getattr(joueur, 'dernier_echo_dir_temps', 0),
                cooldown_ms=COOLDOWN_ECHO_DIR,
                icone_fn=self._dessiner_icone_mini_echo_dir,
            )
            y_cur += espace

        return y_cur

    # ------------------------------------------------------------------
    #  MINI-COOLDOWN WIDGET (dash / écho dir)
    # ------------------------------------------------------------------

    def _dessiner_mini_cooldown(self, x, y, touche_label, titre,
                                couleur_pastille, dernier_temps, cooldown_ms, icone_fn):
        """
        Widget compact de cooldown pour dash / écho directionnel.
        Retourne y + hauteur du widget.
        """
        temps_actuel = pygame.time.get_ticks()
        r   = self._mini_rayon
        cx  = x + r
        cy  = y + r
        elapsed = temps_actuel - dernier_temps
        ratio   = max(0.0, min(1.0, elapsed / cooldown_ms))
        pret    = ratio >= 1.0

        # Fond
        surf = self._mini_widget_cache
        surf.fill((0, 0, 0, 0))
        surf.fill((8, 6, 20, 140))
        pygame.draw.rect(surf, (30, 20, 60, 160),
                         surf.get_rect(), width=1, border_radius=5)
        self.ecran.blit(surf, (x - 2, y - 2))

        # Cercle
        sc = self._mini_circle_cache
        sc.fill((0, 0, 0, 0))
        scx = r + 1
        scy = r + 1
        pygame.draw.circle(sc, (25, 18, 45, 200), (scx, scy), r)
        pygame.draw.circle(sc, (50, 35, 80, 220), (scx, scy), r, width=2)

        if pret:
            pulse = 0.82 + 0.18 * math.sin(temps_actuel / 450)
            rc, gc, bc = couleur_pastille
            pygame.draw.circle(sc, (rc, gc, bc, int(55 * pulse)), (scx, scy), r - 2)
            pygame.draw.circle(sc, (rc, gc, bc, 255), (scx, scy), r, width=2)
        else:
            self._dessiner_arc_cooldown(sc, scx, scy, r - 2, ratio)
            pygame.draw.circle(sc, (55, 38, 85, 180), (scx, scy), r, width=1)

        if 0 <= elapsed < 200:
            flash_a = min(255, int(160 * (1.0 - elapsed / 200)))
            pygame.draw.circle(sc, (255, 255, 255, flash_a), (scx, scy), r - 3)

        # Lettre de touche au centre du cercle (même style que "E" dans l'écho)
        couleur_lettre = COULEUR_CYAN if pret else (100, 80, 140)
        lettre_surf = render_text(self._font_echo_icon, touche_label, couleur_lettre)
        sc.blit(lettre_surf, lettre_surf.get_rect(center=(scx, scy)))
        self.ecran.blit(sc, (cx - r - 1, cy - r - 1))

        # Labels à droite — même disposition que l'écho
        lx = cx + r + 10
        ly = cy - 18

        titre_surf = render_text(self._font_label_small, titre, (100, 85, 130))
        self.ecran.blit(titre_surf, (lx, ly))
        ly += titre_surf.get_height() + 2

        if pret:
            etat_surf = render_text(self._font_label_medium, "PRÊT", COULEUR_CYAN)
        else:
            restant  = max(0.0, (cooldown_ms - elapsed) / 1000)
            t_ratio  = 1.0 - ratio
            r_c = int(220 * t_ratio + 0   * (1 - t_ratio))
            g_c = int(60  * t_ratio + 200 * (1 - t_ratio))
            b_c = int(60  * t_ratio + 80  * (1 - t_ratio))
            etat_surf = render_text(self._font_label_medium, f"{restant:.1f}s", (r_c, g_c, b_c))
        self.ecran.blit(etat_surf, (lx, ly))
        ly += etat_surf.get_height() + 2

        # Barre de progression
        bar_w  = self._echo_bar_w
        bar_h  = max(3, self.hauteur_ecran // 360)
        pygame.draw.rect(self.ecran, (40, 28, 60), pygame.Rect(lx, ly, bar_w, bar_h), border_radius=2)
        if ratio > 0:
            fill_w = int(bar_w * ratio)
            r_b = int(180 * (1 - ratio))
            g_b = int(60  * (1 - ratio) + 210 * ratio)
            b_b = int(60  * (1 - ratio) + 190 * ratio)
            pygame.draw.rect(self.ecran, (r_b, g_b, b_b),
                             pygame.Rect(lx, ly, fill_w, bar_h), border_radius=2)

        return y + r * 2 + 4

    @staticmethod
    def _dessiner_icone_mini_dash(surf, cx, cy, r, pret):
        """Flèche horizontale → (dash)."""
        couleur = COULEUR_CYAN if pret else (100, 80, 140)
        ep = max(1, r // 4)
        w  = max(4, r * 2 // 3)
        pygame.draw.line(surf, couleur, (cx - w//2, cy), (cx + w//2, cy), ep)
        pygame.draw.line(surf, couleur,
                         (cx + w//2, cy), (cx + w//2 - w//3, cy - w//3), ep)
        pygame.draw.line(surf, couleur,
                         (cx + w//2, cy), (cx + w//2 - w//3, cy + w//3), ep)

    @staticmethod
    def _dessiner_icone_mini_echo_dir(surf, cx, cy, r, pret):
        """Petit anneau + traits latéraux (écho directionnel)."""
        couleur = COULEUR_CYAN if pret else (100, 80, 140)
        ep = max(1, r // 5)
        ri = max(3, r // 2)
        pygame.draw.circle(surf, couleur, (cx, cy), ri, ep)
        pygame.draw.line(surf, couleur, (cx - r + 1, cy), (cx - ri - 1, cy), ep)
        pygame.draw.line(surf, couleur, (cx + ri + 1, cy), (cx + r - 1, cy), ep)

    def _dessiner_notification_capacite(self):
        if not hasattr(self, 'notif_capacite') or not self.notif_capacite:
            return
        temps_ms = pygame.time.get_ticks()
        self.notif_capacite.mettre_a_jour(temps_ms)
        self.notif_capacite.dessiner(self.ecran, temps_ms)

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


    def _dessiner_message_fin(self, surface):
        """Affiche le message de fin avec un fondu progressif."""
        if self._fin_message_depuis is None:
            return
        elapsed = pygame.time.get_ticks() - self._fin_message_depuis
        # Fondu d'apparition sur 1500 ms
        alpha = min(255, int(255 * min(elapsed, 1500) / 1500))
        sw, sh = surface.get_size()

        taille_titre = max(48, sh // 14)
        if (not hasattr(self, '_font_fin')
                or getattr(self, '_font_fin_taille', None) != taille_titre):
            self._font_fin = pygame.font.Font(None, taille_titre)
            self._font_fin_taille = taille_titre

        # Voile sombre pour faire ressortir le texte
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(alpha * 0.5)))
        surface.blit(overlay, (0, 0))

        txt = self._font_fin.render("FIN merci d'avoir joué", True, (0, 212, 255))
        txt.set_alpha(alpha)
        rect = txt.get_rect(center=(sw // 2, sh // 2))
        surface.blit(txt, rect)

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
            lw, lh = sz
            # Tailles proportionnelles à la hauteur de la surface (qui est la
            # surface virtuelle = hauteur_ecran / zoom). Permet à l'écran de
            # mort de s'adapter à toutes les résolutions.
            taille_titre = max(32, lh // 8)
            taille_sub   = max(20, lh // 14)
            if (not hasattr(self, '_police_mort')
                    or getattr(self, '_police_mort_taille', None) != taille_titre):
                self._police_mort = pygame.font.Font(None, taille_titre)
                self._police_sub  = pygame.font.Font(None, taille_sub)
                self._police_mort_taille = taille_titre
            t1 = self._police_mort.render("VOUS ETES MORT", True, (220, 50, 50))
            t2 = self._police_sub.render("Respawn en cours...", True, (160, 100, 100))
            offset = max(10, lh // 40)
            surface.blit(t1, t1.get_rect(center=(lw // 2, lh // 2 - offset)))
            surface.blit(t2, t2.get_rect(center=(lw // 2, lh // 2 + offset)))

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
            self._font_badge_torche = pygame.font.Font(None, 32)

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
