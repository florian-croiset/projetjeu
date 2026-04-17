# core/pancarte_lore.py
# Pancarte de lore interactive : verrouillée par défaut, débloquée contre des âmes.
# Une fois payée, affiche un texte de lore dans une bulle de dialogue stylisée.
# L'état est persistant (sauvegardé via gestion_sauvegarde).

import pygame
import math
import os
import sys
from parametres import TAILLE_TUILE, COULEUR_TEXTE, COULEUR_FOND


# ── Texte de lore affiché après déverrouillage ──────────────────────────────
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

COUT_AMES = 30          # Coût en âmes pour déverrouiller
LARGEUR_PANCARTE = 48   # Pixels (1.5 tuile)
HAUTEUR_PANCARTE = 56


class PancarteLore:
    """
    Pancarte mystérieuse verrouillée par défaut.
    - Interagir (touche E à portée) → invite de paiement.
    - Si assez d'âmes → déverrouillage permanent + son.
    - Une fois déverrouillée → interagir ouvre la bulle de lore.
    """

    PORTEE_INTERACTION = 80   # pixels

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x, y, LARGEUR_PANCARTE, HAUTEUR_PANCARTE)
        self.est_debloquee = False

        # Phase sinusoïdale pour les particules d'âmes
        self._phase = 0.0
        self._particules = []
        self._particules_init = False

        # Fonts (initialisées au premier dessin)
        self._font_lore   = None
        self._font_titre  = None
        self._font_ui     = None
        self._font_runic  = None

        # Cache surface pancarte (rebuilt si état change)
        self._surf_cache   = None
        self._surf_etat    = None   # 'locked' | 'unlocked'

    # ── Réseau ──────────────────────────────────────────────────────────────

    def get_etat(self) -> dict:
        return {
            'x':             self.x,
            'y':             self.y,
            'est_debloquee': self.est_debloquee,
        }

    def set_etat(self, data: dict):
        self.x             = data['x']
        self.y             = data['y']
        self.est_debloquee = data['est_debloquee']
        self.rect.topleft  = (self.x, self.y)

    # ── Logique serveur ─────────────────────────────────────────────────────

    def tenter_paiement(self, joueur) -> str:
        """
        Tente de déverrouiller la pancarte.
        Retourne : 'debloquee' | 'deja_debloquee' | 'pauvre'
        """
        if self.est_debloquee:
            return 'deja_debloquee'
        if joueur.argent < COUT_AMES:
            return 'pauvre'
        joueur.argent    -= COUT_AMES
        self.est_debloquee = True
        joueur.sons_a_jouer.append('ame_perdue')   # Son mystique au déverrouillage
        return 'debloquee'

    def mettre_a_jour(self, temps_ms: int):
        """Mise à jour animation particules."""
        self._phase = (temps_ms / 1200.0) % (2 * math.pi)

    # ── Rendu client ────────────────────────────────────────────────────────

    def _init_fonts(self):
        if self._font_lore is not None:
            return
        self._font_lore  = pygame.font.Font(None, 18)
        self._font_titre = pygame.font.Font(None, 22)
        self._font_ui    = pygame.font.Font(None, 20)
        self._font_runic = pygame.font.Font(None, 24)

    def dessiner(self, surface: pygame.Surface, camera_offset=(0, 0), temps_ms: int = 0):
        self._init_fonts()
        off_x, off_y = camera_offset
        sx = self.x - off_x
        sy = self.y - off_y

        # ── Halo d'âmes flottantes autour de la pancarte ────────────────
        halo_surf = pygame.Surface((LARGEUR_PANCARTE + 40, HAUTEUR_PANCARTE + 40), pygame.SRCALPHA)
        pulse = 0.6 + 0.4 * math.sin(self._phase)
        if self.est_debloquee:
            # Halo doré chaleureux une fois déverrouillée
            for r, a in [(28, 12), (20, 22), (12, 40)]:
                pygame.draw.ellipse(halo_surf, (255, 200, 80, int(a * pulse)),
                                    pygame.Rect(20 - r, 20 - r + HAUTEUR_PANCARTE // 2,
                                                r * 2, r * 2))
        else:
            # Halo violet mystérieux
            for r, a in [(28, 15), (20, 28), (12, 50)]:
                pygame.draw.ellipse(halo_surf, (140, 80, 255, int(a * pulse)),
                                    pygame.Rect(20 - r, 20 - r + HAUTEUR_PANCARTE // 2,
                                                r * 2, r * 2))
        surface.blit(halo_surf, (sx - 20, sy - 20))

        # ── Corps de la pancarte ────────────────────────────────────────
        etat_actuel = 'unlocked' if self.est_debloquee else 'locked'
        if self._surf_cache is None or self._surf_etat != etat_actuel:
            self._surf_cache = self._construire_surface_pancarte(etat_actuel)
            self._surf_etat  = etat_actuel

        surface.blit(self._surf_cache, (sx, sy))

        # ── Particules d'âmes flottantes ────────────────────────────────
        self._dessiner_particules(surface, sx, sy, temps_ms)

        # ── Indicateur d'interaction (si non déverrouillée) ─────────────
        self._dessiner_indicateur(surface, sx, sy, temps_ms)

    def _construire_surface_pancarte(self, etat: str) -> pygame.Surface:
        """Construit et retourne la surface de la pancarte (cachée)."""
        w, h = LARGEUR_PANCARTE, HAUTEUR_PANCARTE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Fond bois usé
        couleur_bois = (85, 52, 28) if etat == 'locked' else (100, 65, 35)
        couleur_bord = (55, 32, 12)
        pygame.draw.rect(surf, couleur_bois, pygame.Rect(0, 0, w, h), border_radius=4)
        pygame.draw.rect(surf, couleur_bord, pygame.Rect(0, 0, w, h), width=2, border_radius=4)

        # Veinures du bois (lignes horizontales très fines)
        for i in range(3, h - 3, 7):
            alpha = 30 + (i % 14) * 2
            ligne = pygame.Surface((w - 6, 1), pygame.SRCALPHA)
            ligne.fill((200, 140, 70, alpha))
            surf.blit(ligne, (3, i))

        # Reflet supérieur (effet vieux bois ciré)
        reflet = pygame.Surface((w - 8, 3), pygame.SRCALPHA)
        reflet.fill((255, 200, 120, 25))
        surf.blit(reflet, (4, 3))

        if etat == 'locked':
            # Symbole cadenas au centre
            cx, cy = w // 2, h // 2 - 4
            # Corps du cadenas
            pygame.draw.rect(surf, (60, 40, 10), pygame.Rect(cx - 7, cy, 14, 10), border_radius=2)
            pygame.draw.rect(surf, (100, 70, 20), pygame.Rect(cx - 7, cy, 14, 10), width=1, border_radius=2)
            # Anneau du cadenas
            pygame.draw.arc(surf, (100, 70, 20),
                            pygame.Rect(cx - 5, cy - 8, 10, 12), 0, math.pi, 2)
            # Chaînes (traits obliques sur les bords)
            for dx in [4, 9, 14, 19]:
                pygame.draw.line(surf, (80, 60, 20), (dx, 8), (dx + 3, 14), 1)
                pygame.draw.line(surf, (80, 60, 20), (w - dx, h - 8), (w - dx - 3, h - 14), 1)
            # Texte "???"
            f = pygame.font.Font(None, 16)
            s = f.render("???", True, (160, 120, 60))
            surf.blit(s, s.get_rect(center=(cx, cy + 16)))
        else:
            # Rune lumineuse centrale
            f = pygame.font.Font(None, 28)
            s = f.render("✦", True, (255, 200, 80))
            surf.blit(s, s.get_rect(center=(w // 2, h // 2 - 4)))
            f2 = pygame.font.Font(None, 14)
            s2 = f2.render("LORE", True, (200, 160, 60))
            surf.blit(s2, s2.get_rect(center=(w // 2, h // 2 + 14)))

        return surf

    def _dessiner_particules(self, surface, sx, sy, temps_ms):
        """Petites âmes flottantes autour de la pancarte."""
        nb = 5 if not self.est_debloquee else 3
        for i in range(nb):
            phase_i = self._phase + i * (2 * math.pi / nb)
            px = sx + LARGEUR_PANCARTE // 2 + math.cos(phase_i) * (18 + i * 4)
            py = sy + HAUTEUR_PANCARTE // 2 + math.sin(phase_i * 0.7) * 10 - i * 3
            alpha = int(120 + 80 * math.sin(phase_i * 2))
            r = max(1, int(2 + math.sin(phase_i) * 1.5))
            couleur = (140, 80, 255, alpha) if not self.est_debloquee else (255, 200, 80, alpha)
            p_surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(p_surf, couleur, (r + 1, r + 1), r)
            surface.blit(p_surf, (int(px) - r - 1, int(py) - r - 1))

    def _dessiner_indicateur(self, surface, sx, sy, temps_ms):
        """Badge [E] au-dessus de la pancarte pour signaler l'interaction."""
        f = pygame.font.Font(None, 18)
        if not self.est_debloquee:
            label = f"[E]  {COUT_AMES} âmes"
            couleur = (160, 100, 255)
        else:
            label = "[E]  Lire"
            couleur = (255, 200, 80)

        s = f.render(label, True, couleur)
        flottement = int(3 * math.sin(self._phase * 2))
        bx = sx + LARGEUR_PANCARTE // 2 - s.get_width() // 2
        by = sy - 22 + flottement

        # Fond semi-transparent
        bg = pygame.Surface((s.get_width() + 8, s.get_height() + 4), pygame.SRCALPHA)
        bg.fill((10, 5, 25, 180))
        pygame.draw.rect(bg, couleur, bg.get_rect(), width=1, border_radius=3)
        surface.blit(bg, (bx - 4, by - 2))
        surface.blit(s, (bx, by))


# ── Bulle de dialogue de lore ────────────────────────────────────────────────

class BulleLore:
    """
    Bulle de dialogue affichant le texte de lore.
    Rendue directement sur l'écran (pas sur la surface virtuelle zoomée).
    Se ferme avec Échap ou clic en dehors.
    """

    LARGEUR = 620
    HAUTEUR = 440
    MARGE   = 32

    def __init__(self, largeur_ecran: int, hauteur_ecran: int):
        self.lw = largeur_ecran
        self.lh = hauteur_ecran
        self.rect = pygame.Rect(
            largeur_ecran // 2 - self.LARGEUR // 2,
            hauteur_ecran // 2 - self.HAUTEUR // 2,
            self.LARGEUR, self.HAUTEUR
        )
        self.visible    = False
        self._scroll    = 0
        self._surf      = None   # Cache de la bulle
        self._temps_ouv = 0

        self._font_texte = pygame.font.Font(None, 19)
        self._font_titre = pygame.font.Font(None, 24)
        self._font_fermer = pygame.font.Font(None, 18)

    def ouvrir(self):
        self.visible    = True
        self._scroll    = 0
        self._surf      = None
        self._temps_ouv = pygame.time.get_ticks()

    def fermer(self):
        self.visible = False

    def gerer_event(self, event) -> bool:
        """Retourne True si la bulle a consommé l'événement."""
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.fermer()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(event.pos):
                self.fermer()
                return True
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - event.y * 18)
            return True
        return False

    def dessiner(self, surface: pygame.Surface):
        if not self.visible:
            return

        temps_ms = pygame.time.get_ticks()

        # Overlay sombre
        overlay = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        elapsed = temps_ms - self._temps_ouv
        alpha_overlay = min(160, int(160 * elapsed / 300))
        overlay.fill((0, 0, 0, alpha_overlay))
        surface.blit(overlay, (0, 0))

        # ── Fond parchemin ───────────────────────────────────────────────
        fond = pygame.Surface((self.LARGEUR, self.HAUTEUR), pygame.SRCALPHA)

        # Fond vieux parchemin
        for y in range(self.HAUTEUR):
            ratio = y / self.HAUTEUR
            r = int(42 + ratio * 18)
            g = int(28 + ratio * 12)
            b = int(8  + ratio * 6)
            pygame.draw.line(fond, (r, g, b, 240), (0, y), (self.LARGEUR, y))

        # Bordure ornementale
        pygame.draw.rect(fond, (120, 80, 30), pygame.Rect(0, 0, self.LARGEUR, self.HAUTEUR),
                         width=3, border_radius=8)
        pygame.draw.rect(fond, (80, 50, 15), pygame.Rect(4, 4, self.LARGEUR - 8, self.HAUTEUR - 8),
                         width=1, border_radius=6)

        # Coins ornés (petits carrés)
        for cx, cy in [(8, 8), (self.LARGEUR - 18, 8),
                       (8, self.HAUTEUR - 18), (self.LARGEUR - 18, self.HAUTEUR - 18)]:
            pygame.draw.rect(fond, (160, 110, 40), pygame.Rect(cx, cy, 10, 10))
            pygame.draw.rect(fond, (80, 50, 15), pygame.Rect(cx, cy, 10, 10), width=1)

        # Séparateur titre
        for px in range(self.MARGE, self.LARGEUR - self.MARGE):
            ratio = (px - self.MARGE) / (self.LARGEUR - self.MARGE * 2)
            dist = abs(ratio - 0.5) * 2
            a = int(180 * (1 - dist ** 2))
            fond.set_at((px, 52), (160, 110, 40, a))
            fond.set_at((px, 53), (80, 50, 15, a // 2))

        surface.blit(fond, self.rect.topleft)

        # ── Titre ────────────────────────────────────────────────────────
        titre = self._font_titre.render("✦  Inscription ancienne  ✦", True, (220, 170, 60))
        surface.blit(titre, titre.get_rect(center=(self.rect.centerx, self.rect.y + 30)))

        # ── Zone de texte scrollable ─────────────────────────────────────
        zone_y = self.rect.y + 62
        zone_h = self.HAUTEUR - 80
        zone_rect = pygame.Rect(self.rect.x + self.MARGE, zone_y,
                                self.LARGEUR - self.MARGE * 2, zone_h)

        # Clip pour ne pas dépasser
        clip_orig = surface.get_clip()
        surface.set_clip(zone_rect)

        lh = self._font_texte.get_height() + 4
        y_cursor = zone_y + 8 - self._scroll
        for ligne in TEXTE_LORE:
            if ligne == "":
                y_cursor += lh // 2
                continue
            # Couleur légèrement différente pour les lignes de citation
            if ligne.startswith("  ") or ligne.startswith("«") or ligne.startswith("»"):
                couleur = (200, 160, 80)
            elif ligne.startswith("—"):
                couleur = (160, 120, 50)
                # Italique simulé (décalage léger)
                y_cursor += 4
            else:
                couleur = (220, 185, 100)
            s = self._font_texte.render(ligne, True, couleur)
            surface.blit(s, (zone_rect.x + 4, y_cursor))
            y_cursor += lh

        surface.set_clip(clip_orig)

        # ── Indication fermeture ─────────────────────────────────────────
        hint = self._font_fermer.render("[ Échap ] ou cliquer en dehors pour fermer", True, (120, 85, 30))
        surface.blit(hint, hint.get_rect(center=(self.rect.centerx,
                                                  self.rect.bottom - 14)))


# ── Popup de paiement / confirmation ────────────────────────────────────────

class PopupPaiement:
    """
    Popup demandant la confirmation du paiement en âmes.
    Affiche aussi les messages d'erreur (pas assez d'âmes).
    """

    LARGEUR = 380
    HAUTEUR = 200

    def __init__(self, largeur_ecran: int, hauteur_ecran: int):
        self.lw = largeur_ecran
        self.lh = hauteur_ecran
        self.rect = pygame.Rect(
            largeur_ecran // 2 - self.LARGEUR // 2,
            hauteur_ecran // 2 - self.HAUTEUR // 2,
            self.LARGEUR, self.HAUTEUR
        )
        self.visible    = False
        self.mode       = 'confirmer'   # 'confirmer' | 'pauvre' | 'debloquee'
        self._callback  = None          # Appelé si confirmation
        self._font      = pygame.font.Font(None, 20)
        self._font_btn  = pygame.font.Font(None, 22)
        self._temps_msg = 0             # Pour les messages temporaires

        # Rects des boutons (calculés dans dessiner)
        self._btn_oui = pygame.Rect(0, 0, 110, 36)
        self._btn_non = pygame.Rect(0, 0, 110, 36)

    def ouvrir_confirmation(self, argent_joueur: int, callback):
        self.mode = 'confirmer' if argent_joueur >= COUT_AMES else 'pauvre'
        self._callback = callback
        self.visible   = True

    def ouvrir_message(self, mode: str):
        """Affiche un message temporaire ('pauvre' | 'debloquee')."""
        self.mode       = mode
        self._callback  = None
        self.visible    = True
        self._temps_msg = pygame.time.get_ticks()

    def gerer_event(self, event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False
                return True
            if event.key == pygame.K_RETURN and self.mode == 'confirmer':
                self._confirmer()
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == 'confirmer':
                if self._btn_oui.collidepoint(event.pos):
                    self._confirmer()
                    return True
                if self._btn_non.collidepoint(event.pos) or not self.rect.collidepoint(event.pos):
                    self.visible = False
                    return True
            else:
                self.visible = False
                return True
        # Auto-fermeture des messages temporaires après 2.5s
        if self._temps_msg and pygame.time.get_ticks() - self._temps_msg > 2500:
            self.visible    = False
            self._temps_msg = 0
        return self.visible

    def _confirmer(self):
        if self._callback:
            self._callback()
        self.visible = False

    def dessiner(self, surface: pygame.Surface):
        if not self.visible:
            return

        # Overlay léger
        overlay = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        surface.blit(overlay, (0, 0))

        # Fond popup
        fond = pygame.Surface((self.LARGEUR, self.HAUTEUR), pygame.SRCALPHA)
        fond.fill((20, 10, 40, 240))
        pygame.draw.rect(fond, (140, 80, 255) if self.mode != 'pauvre' else (200, 50, 50),
                         fond.get_rect(), width=2, border_radius=8)
        surface.blit(fond, self.rect.topleft)

        cx = self.rect.centerx
        cy = self.rect.centery

        if self.mode == 'confirmer':
            # Titre
            t1 = self._font.render("Pancarte mystérieuse", True, (200, 160, 255))
            surface.blit(t1, t1.get_rect(center=(cx, self.rect.y + 30)))
            # Message
            t2 = self._font.render(
                f"Payer {COUT_AMES} âmes pour révéler ce secret ?", True, (200, 185, 230))
            surface.blit(t2, t2.get_rect(center=(cx, cy - 10)))
            # Sous-message
            t3 = self._font.render(
                "Cette connaissance est permanente.", True, (140, 120, 160))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 14)))

            # Boutons
            btn_y = self.rect.bottom - 56
            self._btn_oui.center = (cx - 65, btn_y)
            self._btn_non.center = (cx + 65, btn_y)

            # Oui
            mx, my = pygame.mouse.get_pos()
            survol_oui = self._btn_oui.collidepoint(mx, my)
            pygame.draw.rect(surface, (30, 15, 60) if not survol_oui else (50, 25, 100),
                             self._btn_oui, border_radius=6)
            pygame.draw.rect(surface, (140, 80, 255), self._btn_oui, width=1, border_radius=6)
            s_oui = self._font_btn.render("Payer", True, (200, 160, 255))
            surface.blit(s_oui, s_oui.get_rect(center=self._btn_oui.center))

            # Non
            survol_non = self._btn_non.collidepoint(mx, my)
            pygame.draw.rect(surface, (30, 10, 10) if not survol_non else (55, 18, 18),
                             self._btn_non, border_radius=6)
            pygame.draw.rect(surface, (180, 50, 50), self._btn_non, width=1, border_radius=6)
            s_non = self._font_btn.render("Renoncer", True, (220, 80, 80))
            surface.blit(s_non, s_non.get_rect(center=self._btn_non.center))

            # Hint clavier
            hint = self._font.render("[Entrée] Confirmer  |  [Échap] Annuler", True, (80, 60, 100))
            surface.blit(hint, hint.get_rect(center=(cx, self.rect.bottom - 16)))

        elif self.mode == 'pauvre':
            t1 = self._font.render("⚠  Âmes insuffisantes", True, (220, 80, 80))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 25)))
            t2 = self._font.render(
                f"Il vous faut {COUT_AMES} âmes.", True, (180, 120, 120))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 2)))
            t3 = self._font.render("Continuez votre chemin...", True, (140, 90, 90))
            surface.blit(t3, t3.get_rect(center=(cx, cy + 24)))

        elif self.mode == 'debloquee':
            t1 = self._font.render("✦  Secret révélé  ✦", True, (255, 200, 80))
            surface.blit(t1, t1.get_rect(center=(cx, cy - 15)))
            t2 = self._font.render("Interagissez à nouveau pour lire.", True, (200, 170, 100))
            surface.blit(t2, t2.get_rect(center=(cx, cy + 10)))