# sequence_fin_cristal.py
# Remplace / enrichit jouer_sequence_fin() dans boucle_jeu.py
#
# FLUX :
#   1. Fade noir depuis le dernier frame de jeu
#   2. Écran cristal intact  → le joueur spame K pour le briser
#   3. Animation d'explosion (5 images Destruction_Solaris_*)
#   4. Fond noir + message "Vous êtes sorti…"
#   5. Séquence ending.png + teaser_echo2.png (identique à l'original)
#
# INTÉGRATION :
#   • Copiez ce fichier à la racine du projet.
#   • Dans boucle_jeu.py, remplacez la méthode jouer_sequence_fin() par celle ci-dessous.
#   • Ajoutez les chemins des 5 images de destruction dans les constantes FIN_CRISTAL_* .

import os
import sys
import pygame


# ──────────────────────────────────────────────────────────────────────────────
#  PATCH DE BoucleJeuMixin  (coller dans boucle_jeu.py à la place de l'ancienne
#  méthode, ou appeler depuis celle-ci)
# ──────────────────────────────────────────────────────────────────────────────

def _chemin_asset(nom):
    """Résout un chemin d'asset compatible mode frozen (PyInstaller) et dev."""
    base = (sys._MEIPASS if getattr(sys, 'frozen', False)
            else os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", nom)


# Chemins des 5 frames de destruction (dans assets/)
FIN_CRISTAL_FRAMES = [
    _chemin_asset("Destruction_Solaris_1_-_Instabilité.png"),
    _chemin_asset("Destruction_Solaris_2_-_Fissures.png"),
    _chemin_asset("Destruction_Solaris_3_-_Explosion.png"),
    _chemin_asset("Destruction_Solaris_4_-_Aftermath.png"),
    _chemin_asset("Destruction_Solaris_5_-_Noir.png"),
]

# ──────────────────────────────────────────────────────────────────────────────
#  NOUVELLE MÉTHODE  jouer_sequence_fin
#  (remplace l'ancienne dans BoucleJeuMixin)
# ──────────────────────────────────────────────────────────────────────────────

def jouer_sequence_fin(self):
    """
    Cinématique de fin :
      1. Fade noir (depuis jeu)
      2. Image cristal intact — spam touche K pour le briser
      3. Animation destruction 5 frames
      4. Fond noir + texte de sortie
      5. ending.png → teaser_echo2.png → retour menu
    """
    from utils import music          # import local pour éviter les circularités
    FPS        = 60
    lw, lh     = self.largeur_ecran, self.hauteur_ecran


    police_medium = pygame.font.Font(None, int(lh * 0.038))
    
    # ── Helpers communs ────────────────────────────────────────────────────────

    def _pomper_quit():
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

    def _charger_image(chemin):
        try:
            img = pygame.image.load(chemin).convert()
        except Exception:
            img = pygame.Surface((lw, lh))
            img.fill((10, 10, 20))
        ratio = min(lw / img.get_width(), lh / img.get_height())
        nw = int(img.get_width()  * ratio)
        nh = int(img.get_height() * ratio)
        img = pygame.transform.scale(img, (nw, nh))
        return img, (lw - nw) // 2, (lh - nh) // 2

    def _fade_vers_noir(duree_ms, snapshot=None):
        debut   = pygame.time.get_ticks()
        overlay = pygame.Surface((lw, lh), pygame.SRCALPHA)
        while True:
            elapsed = pygame.time.get_ticks() - debut
            t = min(elapsed / duree_ms, 1.0)
            self.ecran.fill((0, 0, 0))
            if snapshot:
                self.ecran.blit(snapshot, (0, 0))
            overlay.fill((0, 0, 0, int(255 * t)))
            self.ecran.blit(overlay, (0, 0))
            pygame.display.flip()
            _pomper_quit()
            self.horloge.tick(FPS)
            if elapsed >= duree_ms:
                break

    def _afficher_image_avec_attente(image, ix, iy,
                                     fadein_ms=800, lock_ms=3000,
                                     hint="Appuyez sur une touche pour continuer…"):
        """Fade-in d'une image, puis attend une touche (après lock_ms)."""
        debut_fi = pygame.time.get_ticks()
        while True:
            elapsed = pygame.time.get_ticks() - debut_fi
            t = min(elapsed / fadein_ms, 1.0)
            self.ecran.fill((0, 0, 0))
            tmp = image.copy()
            tmp.set_alpha(int(255 * t))
            self.ecran.blit(tmp, (ix, iy))
            pygame.display.flip()
            _pomper_quit()
            self.horloge.tick(FPS)
            if elapsed >= fadein_ms:
                break

        debut_lock = pygame.time.get_ticks()
        pygame.event.clear()
        while True:
            now = pygame.time.get_ticks()
            peut_continuer = now - debut_lock >= lock_ms
            self.ecran.fill((0, 0, 0))
            self.ecran.blit(image, (ix, iy))
            if peut_continuer and (now // 600) % 2 == 0:
                surf = self.police_texte.render(hint, True, (180, 180, 180))
                self.ecran.blit(surf, surf.get_rect(centerx=lw // 2, bottom=lh - 28))
            pygame.display.flip()
            self.horloge.tick(FPS)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if peut_continuer and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return

    # ── ÉTAPE 1 : Fade noir depuis le jeu ─────────────────────────────────────
    snapshot_jeu = self.ecran.copy()
    _fade_vers_noir(1500, snapshot=snapshot_jeu)
    pygame.time.wait(300)

    music.demarrer()   # musique de fond pour toute la cinématique

    # ── ÉTAPE 2 : Cristal intact — spam K pour le briser ──────────────────────

    img_cristal, cx, cy = _charger_image(FIN_CRISTAL_FRAMES[0])

    # Paramètres de la barre de spam
    PRESSIONS_REQUISES   = 30      # nombre de K à presser
    DECAY_PAR_SEC        = 0.08    # la barre recule légèrement si on s'arrête
    BAR_W, BAR_H         = int(lw * 0.55), 22
    bar_x = (lw - BAR_W) // 2
    bar_y = lh - 80

    progression = 0.0   # 0.0 → 1.0
    pressions   = 0
    k_code      = pygame.K_k
    t_dernier   = pygame.time.get_ticks()
    shake_frames = 0   # frames de tremblement restantes après un appui

    pygame.event.clear()

    # Pré-charge frame 2 (fissures) pour anticipation visuelle
    img_fissures, fx, fy = _charger_image(FIN_CRISTAL_FRAMES[1])

    # Petite intro fade-in du cristal
    debut_fi = pygame.time.get_ticks()
    while pygame.time.get_ticks() - debut_fi < 1000:
        t = min((pygame.time.get_ticks() - debut_fi) / 1000, 1.0)
        self.ecran.fill((0, 0, 0))
        tmp = img_cristal.copy()
        tmp.set_alpha(int(255 * t))
        self.ecran.blit(tmp, (cx, cy))
        pygame.display.flip()
        _pomper_quit()
        self.horloge.tick(FPS)

    while progression < 1.0:
        now = pygame.time.get_ticks()
        dt  = (now - t_dernier) / 1000.0
        t_dernier = now

        # Décroissance passive (très légère)
        progression = max(0.0, progression - DECAY_PAR_SEC * dt)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == k_code:
                pressions   += 1
                progression  = min(1.0, progression + 1.0 / PRESSIONS_REQUISES)
                shake_frames = 6   # petite vibration

        # Image du cristal : bascule sur fissures à 50 %
        if progression >= 0.5:
            img_fond, bx, bz = img_fissures, fx, fy
        else:
            img_fond, bx, bz = img_cristal, cx, cy

        # Tremblement d'écran
        off_x = off_y = 0
        if shake_frames > 0:
            import random
            intensity = int(4 * (shake_frames / 6))
            off_x = random.randint(-intensity, intensity)
            off_y = random.randint(-intensity, intensity)
            shake_frames -= 1

        self.ecran.fill((0, 0, 0))
        self.ecran.blit(img_fond, (bx + off_x, bz + off_y))

        # ── Barre de progression ──
        # Fond barre
        pygame.draw.rect(self.ecran, (40, 30, 20),
                         (bar_x - 2, bar_y - 2, BAR_W + 4, BAR_H + 4), border_radius=4)
        # Remplissage (gradient chaud)
        fill_w = int(BAR_W * progression)
        if fill_w > 0:
            # Couleur qui vire de l'ambre au blanc à 100 %
            r = min(255, int(180 + 75 * progression))
            g = min(255, int(90  + 165 * progression))
            b = int(20  * (1 - progression))
            pygame.draw.rect(self.ecran, (r, g, b),
                             (bar_x, bar_y, fill_w, BAR_H), border_radius=3)
        # Bord
        pygame.draw.rect(self.ecran, (220, 180, 80),
                         (bar_x - 2, bar_y - 2, BAR_W + 4, BAR_H + 4),
                         2, border_radius=4)

        # ── Instruction ──
        if (now // 500) % 2 == 0 or progression > 0.1:
            hint_surf = police_medium.render(
                "[ K ]  —  Brisez le cristal", True, (230, 200, 120))
            self.ecran.blit(hint_surf,
                            hint_surf.get_rect(centerx=lw // 2, bottom=bar_y - 18))

        pygame.display.flip()
        self.horloge.tick(FPS)

    # ── ÉTAPE 3 : Animation d'explosion (5 frames) ────────────────────────────
    DUREE_PAR_FRAME_MS = [
        120,   # frame 1 → 2
        200,   # frame 2 → 3
        400,   # frame 3 (explosion peak) — plus long
        600,   # frame 4 (aftermath)
        800,   # frame 5 (noir progressif)
    ]

    try:
        music.jouer_sfx('explosion')   # son d'explosion si disponible
    except Exception:
        pass

    frames_explosion = []
    for chemin in FIN_CRISTAL_FRAMES:
        img, ix, iy = _charger_image(chemin)
        frames_explosion.append((img, ix, iy))

    for i, (img_exp, ix, iy) in enumerate(frames_explosion):
        duree = DUREE_PAR_FRAME_MS[i]
        debut = pygame.time.get_ticks()

        # Tremblement intense sur les frames 2-3
        shake = 8 if i in (1, 2) else (4 if i == 0 else 0)

        while pygame.time.get_ticks() - debut < duree:
            import random
            ox = random.randint(-shake, shake) if shake else 0
            oy = random.randint(-shake, shake) if shake else 0
            self.ecran.fill((0, 0, 0))
            self.ecran.blit(img_exp, (ix + ox, iy + oy))
            pygame.display.flip()
            _pomper_quit()
            self.horloge.tick(FPS)

    # ── ÉTAPE 4 : Fond noir + message de sortie ───────────────────────────────
    # Fade vers le noir depuis la dernière frame d'explosion
    snap_explo = self.ecran.copy()
    _fade_vers_noir(1200, snapshot=snap_explo)
    pygame.time.wait(600)

    # Affichage du message
    LIGNES_MESSAGE = [
        "Solaris est détruit.",
        "",
        "La lumière qui vous avait emprisonnés ici",
        "s'est éteinte pour toujours.",
        "",
        "Vous êtes libres.",
    ]

    def _afficher_message_noir(lignes, duree_totale_ms=5000):
        """Fait apparaître les lignes une à une puis attend."""
        surfaces = []
        for ligne in lignes:
            if ligne:
                s = police_medium.render(ligne, True, (200, 190, 170))
            else:
                s = pygame.Surface((1, self.police_texte.get_height()), pygame.SRCALPHA)
            surfaces.append(s)

        hauteur_bloc = sum(s.get_height() + 8 for s in surfaces)
        y_start = (lh - hauteur_bloc) // 2
        debut = pygame.time.get_ticks()
        delai_par_ligne = 600

        pygame.event.clear()
        while True:
            now = pygame.time.get_ticks()
            elapsed = now - debut
            self.ecran.fill((0, 0, 0))

            y = y_start
            for idx, s in enumerate(surfaces):
                if elapsed >= idx * delai_par_ligne:
                    age = elapsed - idx * delai_par_ligne
                    alpha = min(255, int(age / 400 * 255))
                    tmp = s.copy()
                    tmp.set_alpha(alpha)
                    self.ecran.blit(tmp, tmp.get_rect(centerx=lw // 2, top=y))
                y += s.get_height() + 8

            if elapsed >= duree_totale_ms:
                # Hint clignotant
                if (now // 600) % 2 == 0:
                    h = self.police_texte.render(
                        "Appuyez sur une touche pour continuer…",
                        True, (120, 110, 100))
                    self.ecran.blit(h, h.get_rect(centerx=lw // 2, bottom=lh - 30))

            pygame.display.flip()
            self.horloge.tick(FPS)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if elapsed >= duree_totale_ms and ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return

    _afficher_message_noir(LIGNES_MESSAGE, duree_totale_ms=5500)

    # ── ÉTAPE 5 : Fade → ending.png ───────────────────────────────────────────
    _fade_vers_noir(800)
    pygame.time.wait(200)

    img_ending, ex, ey = _charger_image(self.FIN_ENDING_IMAGE)
    _afficher_image_avec_attente(img_ending, ex, ey)

    # Transition
    snap_ending = self.ecran.copy()
    _fade_vers_noir(1000, snapshot=snap_ending)
    pygame.time.wait(200)

    # ── ÉTAPE 6 : teaser_echo2.png ────────────────────────────────────────────
    img_teaser, tx, ty = _charger_image(self.FIN_TEASER_IMAGE)
    _afficher_image_avec_attente(img_teaser, tx, ty)

    snap_teaser = self.ecran.copy()
    _fade_vers_noir(1000, snapshot=snap_teaser)

    pygame.mixer.music.stop()

    # ── Retour menu ───────────────────────────────────────────────────────────
    self.etat_jeu = "MENU_PRINCIPAL"
    self.nettoyer_connexion()
    self.actualiser_langues_widgets()