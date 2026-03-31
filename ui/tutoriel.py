# ui/tutoriel.py
# Tutoriel interactif affiché au premier lancement du jeu.
# Composé de plusieurs "slides" que le joueur peut parcourir.

import pygame
import math
from parametres import *
from ui.effets_visuels import dessiner_fond_echo
from ui.bouton import Bouton


# ===========================================================
#  DONNÉES DES SLIDES
# ===========================================================

def _get_slides(params_controles):
    """Construit la liste des slides en fonction des contrôles configurés."""

    def touche(cle):
        return params_controles.get(cle, "?").upper()

    slides = [
        # --- 0 : Bienvenue ---
        {
            "titre": "Bienvenue dans Écho !",
            "sous_titre": "Appuie sur → ou ESPACE pour continuer",
            "icone": "🎮",
            "blocs": [
                {
                    "texte": (
                        "Écho est un jeu d'action-plateforme 2D où tu evolues\n"
                        "dans un monde plongé dans l'obscurité totale.\n\n"
                        "Tu ne vois rien... sauf ce que tes échos te révèlent."
                    ),
                    "couleur": COULEUR_TEXTE,
                },
            ],
            "dessin": "bienvenue",
        },

        # --- 1 : Déplacement ---
        {
            "titre": "Se déplacer",
            "sous_titre": "Les bases du mouvement",
            "icone": "🏃",
            "blocs": [
                {
                    "label": f"[ {touche('gauche')} ]",
                    "texte": "Aller à gauche",
                },
                {
                    "label": f"[ {touche('droite')} ]",
                    "texte": "Aller à droite",
                },
                {
                    "label": f"[ {touche('saut')} ]",
                    "texte": "Sauter  (appuie à nouveau en l'air pour le double saut, si débloqué)",
                },
                {
                    "label": f"[ {touche('dash')} ]",
                    "texte": "Dash — propulsion rapide (si débloqué)",
                },
            ],
            "dessin": "deplacement",
        },

        # --- 2 : Écholocalisation ---
        {
            "titre": "L'Écholocalisation",
            "sous_titre": "Ta seule façon de voir",
            "icone": "🔊",
            "blocs": [
                {
                    "texte": (
                        "Le monde est dans le noir. Appuie sur\n"
                        f"[ {touche('echo')} ] pour émettre un écho sonore.\n\n"
                        "L'écho se propage en cercle autour de toi et révèle\n"
                        "les murs, obstacles et points d'intérêt proches.\n\n"
                        "⚠  Cooldown : 6 secondes entre chaque écho.\n"
                        "     Utilise-le avec intelligence !"
                    ),
                    "couleur": COULEUR_CYAN,
                },
            ],
            "dessin": "echo",
        },

        # --- 3 : Combat ---
        {
            "titre": "Le Combat",
            "sous_titre": "Attaque et survie",
            "icone": "⚔️",
            "blocs": [
                {
                    "label": f"[ {touche('attaque')} ]",
                    "texte": "Attaque de mêlée — portée courte, devant toi",
                },
                {
                    "texte": (
                        "Les ennemis patrouillent dans le noir.\n"
                        "Tu as 5 points de vie (PV). Chaque contact en retire 1.\n\n"
                        "Après avoir pris un coup, tu es invincible\n"
                        "pendant 1 seconde — profites-en pour fuir !"
                    ),
                    "couleur": COULEUR_TEXTE,
                },
            ],
            "dessin": "combat",
        },

        # --- 4 : Âmes perdues ---
        {
            "titre": "Les Âmes Perdues",
            "sous_titre": "Inspiré de Dark Souls",
            "icone": "💜",
            "blocs": [
                {
                    "texte": (
                        "Quand tu meurs, tu laisses une Âme Perdue\n"
                        "à l'endroit de ta mort. Elle contient tout ton argent.\n\n"
                        "Tu réapparais au dernier checkpoint, sans argent.\n\n"
                        "Pour récupérer tes âmes :\n"
                        f"  → Retourne à ta mort et attaque l'âme [ {touche('attaque')} ]\n\n"
                        "⚠  Mourir avant de récupérer ton âme la détruit définitivement !"
                    ),
                    "couleur": COULEUR_VIOLET_CLAIR,
                },
            ],
            "dessin": "ame",
        },

        # --- 5 : Checkpoints & Sauvegarde ---
        {
            "titre": "Checkpoints & Sauvegarde",
            "sous_titre": "Progresser sans perdre sa progression",
            "icone": "💾",
            "blocs": [
                {
                    "texte": (
                        "Les tuiles CYAN sur la carte sont des checkpoints.\n\n"
                        "Passe dessus pour :\n"
                        "  ✔  Sauvegarder ta position\n"
                        "  ✔  Sauvegarder la carte révélée\n"
                        "  ✔  Sauvegarder ton argent et tes capacités\n\n"
                        "En cas de mort tu réapparais au dernier checkpoint activé.\n"
                        "Les tuiles grises foncées sont des repères toujours visibles."
                    ),
                    "couleur": COULEUR_SAUVEGARDE,
                },
            ],
            "dessin": "checkpoint",
        },

        # --- 6 : Capacités débloquables ---
        {
            "titre": "Capacités Débloquables",
            "sous_titre": "Explore pour progresser",
            "icone": "⬆️",
            "blocs": [
                {
                    "label": "Double Saut",
                    "texte": f"Appuie sur [ {touche('saut')} ] une 2ᵉ fois en l'air pour sauter plus haut.",
                },
                {
                    "label": "Dash",
                    "texte": f"[ {touche('dash')} ] — propulsion rapide. 1 seul en l'air avant de retoucher le sol.",
                },
                {
                    "texte": (
                        "\nCes capacités sont permanentes une fois débloquées\n"
                        "et persistent entre les sessions de jeu."
                    ),
                    "couleur": COULEUR_TEXTE_SOMBRE,
                },
            ],
            "dessin": "capacites",
        },

        # --- 7 : Multijoueur ---
        {
            "titre": "Multijoueur Coopératif",
            "sous_titre": "Jusqu'à 3 joueurs en réseau local",
            "icone": "👥",
            "blocs": [
                {
                    "label": "Héberger",
                    "texte": "Lance le serveur. Les autres se connectent avec ton IP locale (visible dans Paramètres).",
                },
                {
                    "label": "Rejoindre",
                    "texte": "Entre l'IP de l'hôte pour rejoindre sa partie.",
                },
                {
                    "texte": (
                        "\nChaque joueur a sa propre carte de visibilité.\n"
                        "Les ennemis et les âmes sont partagés entre tous."
                    ),
                    "couleur": COULEUR_TEXTE_SOMBRE,
                },
            ],
            "dessin": "multi",
        },

        # --- 8 : Récapitulatif touches ---
        {
            "titre": "Récapitulatif des Touches",
            "sous_titre": "Tu peux les modifier dans Paramètres",
            "icone": "⌨️",
            "blocs": [
                {"label": f"[ {touche('gauche')} ] / [ {touche('droite')} ]", "texte": "Déplacement"},
                {"label": f"[ {touche('saut')} ]",    "texte": "Saut / Double saut"},
                {"label": f"[ {touche('dash')} ]",    "texte": "Dash"},
                {"label": f"[ {touche('echo')} ]",    "texte": "Écho (révèle l'environnement)"},
                {"label": f"[ {touche('attaque')} ]", "texte": "Attaque"},
                {"label": "[ ÉCHAP ]",                "texte": "Pause"},
            ],
            "dessin": "recap",
        },

        # --- 9 : C'est parti ! ---
        {
            "titre": "C'est parti !",
            "sous_titre": "Bonne exploration dans l'obscurité… 🎮",
            "icone": "🚀",
            "blocs": [
                {
                    "texte": (
                        "Tu peux relancer ce tutoriel à tout moment\n"
                        "depuis le menu principal.\n\n"
                        "Astuce : mémorise la carte révélée,\n"
                        "elle reste permanente entre les sessions.\n\n"
                        "Bonne chance !"
                    ),
                    "couleur": COULEUR_CYAN,
                },
            ],
            "dessin": "fin",
        },
    ]

    return slides


# ===========================================================
#  CLASSE PRINCIPALE
# ===========================================================

class Tutoriel:
    """
    Écran de tutoriel interactif.
    Utilisation :
        tuto = Tutoriel(ecran, largeur, hauteur, params_controles, police_titre, police_texte, police_bouton)
        tuto.lancer()   # bloquant jusqu'à la fin
    """

    def __init__(self, ecran, largeur, hauteur, params_controles,
                 police_titre, police_texte, police_bouton, police_petit=None):
        self.ecran = ecran
        self.largeur = largeur
        self.hauteur = hauteur
        self.cx = largeur // 2
        self.cy = hauteur // 2

        self.police_titre   = police_titre
        self.police_texte   = police_texte
        self.police_bouton  = police_bouton
        self.police_petit   = police_petit or police_texte

        self.slides = _get_slides(params_controles)
        self.index  = 0
        self.total  = len(self.slides)

        self.horloge    = pygame.time.Clock()
        self.temps_anim = 0

        # Boutons navigation
        bh = max(40, hauteur // 22)
        bw = max(160, largeur // 9)

        self.btn_suivant  = Bouton(self.cx + 20,       hauteur - bh - 30, bw, bh, "Suivant  →", police_bouton)
        self.btn_precedent = Bouton(self.cx - bw - 20, hauteur - bh - 30, bw, bh, "←  Précédent", police_bouton, style="ghost")
        self.btn_passer   = Bouton(largeur - 220,       30, 190, bh - 8, "Passer le tutoriel", police_petit or police_bouton, style="ghost")
        self.btn_fermer   = Bouton(self.cx - bw // 2,  hauteur - bh - 30, bw, bh, "Commencer !",   police_bouton, style="primary")

        # Surface semi-trans pour les panneaux
        self._panneau = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)

    # ----------------------------------------------------------
    #  BOUCLE PRINCIPALE
    # ----------------------------------------------------------

    def lancer(self):
        """Lance le tutoriel. Retourne quand l'utilisateur a terminé ou passé."""
        running = True
        while running:
            self.temps_anim = pygame.time.get_ticks()
            pos_souris = pygame.mouse.get_pos()

            # --- Événements ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys; sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                        self._avancer()
                    elif event.key == pygame.K_LEFT:
                        self._reculer()
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
                            self._avancer()
                        if self.btn_precedent.rect.collidepoint(event.pos):
                            self._reculer()

            # Survol
            for btn in [self.btn_suivant, self.btn_precedent, self.btn_passer, self.btn_fermer]:
                btn.verifier_survol(pos_souris)

            # Si on arrive à la dernière slide et qu'on avance, on ferme
            if self.index >= self.total:
                running = False
                break

            # --- Dessin ---
            self._dessiner()
            pygame.display.flip()
            self.horloge.tick(FPS)

    # ----------------------------------------------------------
    #  NAVIGATION
    # ----------------------------------------------------------

    def _avancer(self):
        if self.index < self.total - 1:
            self.index += 1
        else:
            self.index = self.total  # signal de fin

    def _reculer(self):
        if self.index > 0:
            self.index -= 1

    # ----------------------------------------------------------
    #  RENDU
    # ----------------------------------------------------------

    def _dessiner(self):
        # Fond animé (réutilise l'effet des menus)
        dessiner_fond_echo(self.ecran, self.largeur, self.hauteur, self.temps_anim)

        slide = self.slides[self.index]

        # Zone principale : panneau centré
        pw = int(self.largeur * 0.72)
        ph = int(self.hauteur * 0.78)
        px = (self.largeur - pw) // 2
        py = int(self.hauteur * 0.07)

        self._dessiner_panneau(px, py, pw, ph)
        self._dessiner_contenu_slide(slide, px, py, pw, ph)
        self._dessiner_navigation()
        self._dessiner_indicateur()

    def _dessiner_panneau(self, x, y, w, h):
        """Panneau semi-transparent avec bordure néon."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((10, 8, 28, 210))
        self.ecran.blit(surf, (x, y))

        # Bordure cyan
        pulse = 0.7 + 0.3 * math.sin(self.temps_anim / 900)
        alpha_bord = int(180 * pulse)
        bord = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bord, (*COULEUR_CYAN, alpha_bord), bord.get_rect(), 2, border_radius=10)
        self.ecran.blit(bord, (x, y))

    def _dessiner_contenu_slide(self, slide, px, py, pw, ph):
        """Dessine le titre, l'icône et les blocs de texte de la slide."""
        marge_h = int(pw * 0.06)
        marge_v = int(ph * 0.07)
        y_cur   = py + marge_v

        # -- Icône --
        icone_surf = self.police_titre.render(slide.get("icone", ""), True, COULEUR_CYAN)
        self.ecran.blit(icone_surf, (px + marge_h, y_cur))

        # -- Titre --
        titre_surf = self.police_titre.render(slide["titre"], True, COULEUR_CYAN)
        self.ecran.blit(titre_surf, (px + marge_h + icone_surf.get_width() + 18, y_cur))
        y_cur += titre_surf.get_height() + 6

        # -- Sous-titre --
        if slide.get("sous_titre"):
            st = self.police_petit.render(slide["sous_titre"], True, COULEUR_TEXTE_SOMBRE)
            self.ecran.blit(st, (px + marge_h + icone_surf.get_width() + 18, y_cur))
            y_cur += st.get_height() + 4

        # -- Séparateur --
        sep_y = y_cur + 8
        sep_surf = pygame.Surface((pw - 2 * marge_h, 1), pygame.SRCALPHA)
        sep_surf.fill((*COULEUR_CYAN, 80))
        self.ecran.blit(sep_surf, (px + marge_h, sep_y))
        y_cur = sep_y + 18

        # -- Illustration à droite (selon type) --
        ilu_x = px + pw - int(pw * 0.30) - marge_h
        ilu_y = py + int(ph * 0.18)
        ilu_w = int(pw * 0.28)
        ilu_h = int(ph * 0.55)
        self._dessiner_illustration(slide.get("dessin", ""), ilu_x, ilu_y, ilu_w, ilu_h)

        # Zone texte (côté gauche)
        zone_texte_w = int(pw * 0.60) - marge_h

        # -- Blocs de contenu --
        for bloc in slide.get("blocs", []):
            couleur = bloc.get("couleur", COULEUR_TEXTE)

            if "label" in bloc:
                # Ligne label + texte
                label_surf = self.police_bouton.render(bloc["label"], True, COULEUR_CYAN)
                self.ecran.blit(label_surf, (px + marge_h, y_cur))
                txt_surf = self.police_texte.render(bloc["texte"], True, couleur)
                self.ecran.blit(txt_surf, (px + marge_h + label_surf.get_width() + 14, y_cur + 4))
                y_cur += label_surf.get_height() + 10
            else:
                # Bloc de texte multi-lignes
                for ligne in bloc["texte"].split("\n"):
                    if ligne.strip() == "":
                        y_cur += int(self.police_texte.get_height() * 0.6)
                        continue
                    s = self.police_texte.render(ligne, True, couleur)
                    if s.get_width() > zone_texte_w:
                        # Troncature simple
                        while s.get_width() > zone_texte_w and len(ligne) > 10:
                            ligne = ligne[:-1]
                        s = self.police_texte.render(ligne + "…", True, couleur)
                    self.ecran.blit(s, (px + marge_h, y_cur))
                    y_cur += s.get_height() + 6
                y_cur += 8

    def _dessiner_illustration(self, type_dessin, x, y, w, h):
        """Dessine une illustration minimaliste selon le type de slide."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        t = self.temps_anim

        if type_dessin == "bienvenue":
            # Titre animé en écho
            pulse = 0.5 + 0.5 * math.sin(t / 700)
            for r in [80, 55, 30]:
                a = int(pulse * 120 * (1 - r / 90))
                pygame.draw.circle(surf, (*COULEUR_CYAN, a), (cx, cy), r, 2)
            pygame.draw.circle(surf, COULEUR_CYAN, (cx, cy), 10)

        elif type_dessin == "deplacement":
            # Personnage stylisé avec flèches
            pygame.draw.rect(surf, COULEUR_JOUEUR, (cx - 8, cy - 15, 16, 20), border_radius=3)
            pygame.draw.circle(surf, COULEUR_JOUEUR, (cx, cy - 22), 8)
            # Flèches gauche/droite
            pygame.draw.polygon(surf, COULEUR_CYAN, [(cx - 35, cy), (cx - 22, cy - 10), (cx - 22, cy + 10)])
            pygame.draw.polygon(surf, COULEUR_CYAN, [(cx + 35, cy), (cx + 22, cy - 10), (cx + 22, cy + 10)])
            # Sol
            pygame.draw.line(surf, COULEUR_MUR_VISIBLE, (cx - 50, cy + 10), (cx + 50, cy + 10), 3)

        elif type_dessin == "echo":
            # Ondes concentriques en expansion
            phase = (t % 2400) / 2400
            for i in range(4):
                r_base = 20 + i * 22
                r = int(r_base + phase * 25) % (h // 2)
                a = max(0, int(200 * (1 - phase - i * 0.18)))
                if a > 0:
                    pygame.draw.circle(surf, (*COULEUR_CYAN, a), (cx, cy), r, 2)
            pygame.draw.circle(surf, COULEUR_VIOLET, (cx, cy), 8)

        elif type_dessin == "combat":
            # Joueur vs ennemi
            pygame.draw.rect(surf, COULEUR_JOUEUR,  (cx - 40, cy - 15, 16, 22), border_radius=3)
            pygame.draw.circle(surf, COULEUR_JOUEUR, (cx - 32, cy - 24), 8)
            pygame.draw.rect(surf, COULEUR_ENNEMI,   (cx + 18, cy - 15, 16, 22), border_radius=3)
            pygame.draw.circle(surf, COULEUR_ENNEMI, (cx + 26, cy - 24), 8)
            # Trait d'attaque animé
            blink = int(t / 300) % 2
            if blink:
                pygame.draw.line(surf, COULEUR_ATTAQUE, (cx - 22, cy - 5), (cx + 17, cy - 5), 3)

        elif type_dessin == "ame":
            # Silhouette âme + icône argent
            pulse = 0.6 + 0.4 * math.sin(t / 600)
            r = int(20 * pulse)
            pygame.draw.ellipse(surf, (*COULEUR_VIOLET, 180), (cx - r, cy - r - 5, r * 2, r * 2 + 10))
            # Particules flottantes
            for i in range(5):
                angle = t / 1000 + i * math.pi * 2 / 5
                px2 = int(cx + math.cos(angle) * 35)
                py2 = int(cy + math.sin(angle) * 20)
                pygame.draw.circle(surf, (*COULEUR_VIOLET_CLAIR, 160), (px2, py2), 3)

        elif type_dessin == "checkpoint":
            # Tuile checkpoint cyan avec éclat
            pygame.draw.rect(surf, COULEUR_SAUVEGARDE, (cx - 16, cy - 16, 32, 32), border_radius=4)
            pulse = 0.4 + 0.6 * math.sin(t / 800)
            for r in [28, 40, 52]:
                a = int(60 * pulse * (1 - r / 60))
                if a > 0:
                    pygame.draw.circle(surf, (*COULEUR_SAUVEGARDE, a), (cx, cy), r, 2)
            # Symbole save
            texte = pygame.font.Font(None, 28).render("✔", True, COULEUR_NOIR)
            surf.blit(texte, (cx - texte.get_width() // 2, cy - texte.get_height() // 2))

        elif type_dessin == "capacites":
            # Double saut et dash représentés
            pygame.draw.rect(surf, COULEUR_JOUEUR, (cx - 8, cy - 15, 16, 20), border_radius=3)
            pygame.draw.circle(surf, COULEUR_JOUEUR, (cx, cy - 22), 8)
            # Flèche montante double saut
            for offset in [-8, 0]:
                pygame.draw.polygon(surf, COULEUR_CYAN, [
                    (cx, cy - 35 + offset), (cx - 10, cy - 22 + offset), (cx + 10, cy - 22 + offset)
                ])
            # Trainée dash
            for i in range(5):
                a = int(150 * (1 - i / 5))
                pygame.draw.circle(surf, (*COULEUR_VIOLET, a), (cx - 20 - i * 8, cy), 4 - i // 2)

        elif type_dessin == "multi":
            # 3 joueurs
            colors = [COULEUR_JOUEUR, COULEUR_JOUEUR_AUTRE, COULEUR_CYAN]
            positions = [(cx - 40, cy), (cx, cy - 10), (cx + 40, cy)]
            for (px2, py2), c in zip(positions, colors):
                pygame.draw.rect(surf, c, (px2 - 8, py2 - 12, 16, 18), border_radius=3)
                pygame.draw.circle(surf, c, (px2, py2 - 20), 7)
            # Connexion réseau
            pygame.draw.line(surf, (*COULEUR_CYAN, 100), positions[0], positions[1], 1)
            pygame.draw.line(surf, (*COULEUR_CYAN, 100), positions[1], positions[2], 1)

        elif type_dessin == "recap":
            # Clavier simplifié
            touches = ["Q", "D", "Z", "E", "K", "C"]
            for i, t_label in enumerate(touches):
                col = i % 3
                row = i // 3
                kx = cx - 50 + col * 38
                ky = cy - 22 + row * 38
                pygame.draw.rect(surf, COULEUR_BOUTON_SURVOL, (kx, ky, 32, 28), border_radius=4)
                pygame.draw.rect(surf, COULEUR_CYAN, (kx, ky, 32, 28), 1, border_radius=4)
                k_txt = pygame.font.Font(None, 22).render(t_label, True, COULEUR_CYAN)
                surf.blit(k_txt, (kx + 16 - k_txt.get_width() // 2, ky + 14 - k_txt.get_height() // 2))

        elif type_dessin == "fin":
            # Logo/titre pulsé
            pulse = 0.7 + 0.3 * math.sin(t / 700)
            for r in [60, 40, 22]:
                a = int(pulse * 100)
                pygame.draw.circle(surf, (*COULEUR_CYAN, a), (cx, cy), r, 2)
            logo = pygame.font.Font(None, 48).render("ÉCHO", True, COULEUR_CYAN)
            surf.blit(logo, (cx - logo.get_width() // 2, cy - logo.get_height() // 2))

        self.ecran.blit(surf, (x, y))

    def _dessiner_navigation(self):
        """Dessine les boutons précédent/suivant/passer."""
        est_derniere = self.index == self.total - 1

        if est_derniere:
            self.btn_fermer.dessiner(self.ecran)
        else:
            self.btn_suivant.dessiner(self.ecran)
            if self.index > 0:
                self.btn_precedent.dessiner(self.ecran)

        self.btn_passer.dessiner(self.ecran)

    def _dessiner_indicateur(self):
        """Barre de points indiquant la progression."""
        n = self.total
        rayon = 5
        espace = 16
        total_w = n * rayon * 2 + (n - 1) * espace
        x_start = self.cx - total_w // 2
        y_pos = self.hauteur - 16

        for i in range(n):
            x = x_start + i * (rayon * 2 + espace) + rayon
            if i == self.index:
                pygame.draw.circle(self.ecran, COULEUR_CYAN, (x, y_pos), rayon)
            else:
                pygame.draw.circle(self.ecran, COULEUR_BOUTON_SURVOL, (x, y_pos), rayon - 1)
                pygame.draw.circle(self.ecran, COULEUR_TEXTE_SOMBRE, (x, y_pos), rayon - 1, 1)