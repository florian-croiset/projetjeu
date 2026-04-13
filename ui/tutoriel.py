# ui/tutoriel.py
# Tutoriel refactorisé : 2 slides uniquement.
#   Slide 1 — Mécaniques de gameplay (contrôles, système, capacités)
#   Slide 2 — Lore et contexte narratif

import pygame
import math
from parametres import *
from ui.effets_visuels import dessiner_fond_echo
from ui.bouton import Bouton


class Tutoriel:
    """
    Tutoriel en 2 slides purement informatives.
    Usage :
        tuto = Tutoriel(ecran, largeur, hauteur, params_controles,
                        police_titre, police_texte, police_bouton, police_petit)
        tuto.lancer()
    """

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

        self.index    = 0
        self.total    = 2
        self.horloge  = pygame.time.Clock()
        self.temps_anim = 0

        bh = max(40, hauteur // 22)
        bw = max(160, largeur // 9)

        self.btn_suivant   = Bouton(self.cx + 20, hauteur - bh - 30,
                                    bw, bh, "Suivant  →", police_bouton)
        self.btn_precedent = Bouton(self.cx - bw - 20, hauteur - bh - 30,
                                    bw, bh, "←  Retour", police_bouton, style="ghost")
        self.btn_fermer    = Bouton(self.cx - bw // 2, hauteur - bh - 30,
                                    bw, bh, "Commencer !", police_bouton)
        self.btn_passer    = Bouton(largeur - 220, 30,
                                    190, bh - 8, "Passer", police_petit or police_bouton,
                                    style="ghost")

    # ------------------------------------------------------------------
    #  BOUCLE
    # ------------------------------------------------------------------

    def lancer(self):
        running = True
        while running:
            self.temps_anim = pygame.time.get_ticks()
            pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys; sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
                        if self.index < self.total - 1:
                            self.index += 1
                        else:
                            running = False
                    elif event.key == pygame.K_LEFT and self.index > 0:
                        self.index -= 1
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
                            self.index += 1
                    if self.index > 0 and self.btn_precedent.rect.collidepoint(event.pos):
                        self.index -= 1

            for btn in [self.btn_suivant, self.btn_precedent,
                        self.btn_fermer, self.btn_passer]:
                btn.verifier_survol(pos)

            self._dessiner()
            pygame.display.flip()
            self.horloge.tick(FPS)

    # ------------------------------------------------------------------
    #  RENDU
    # ------------------------------------------------------------------

    def _dessiner(self):
        dessiner_fond_echo(self.ecran, self.largeur, self.hauteur, self.temps_anim)

        pw = int(self.largeur * 0.88)
        ph = int(self.hauteur * 0.80)
        px = (self.largeur - pw) // 2
        py = int(self.hauteur * 0.06)

        self._panneau(px, py, pw, ph)

        if self.index == 0:
            self._slide_gameplay(px, py, pw, ph)
        else:
            self._slide_lore(px, py, pw, ph)

        self._navigation()
        self._indicateur()

    def _panneau(self, x, y, w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((10, 8, 28, 215))
        self.ecran.blit(surf, (x, y))
        pulse = 0.7 + 0.3 * math.sin(self.temps_anim / 900)
        bord  = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bord, (*COULEUR_CYAN, int(180 * pulse)),
                         bord.get_rect(), 2, border_radius=10)
        self.ecran.blit(bord, (x, y))

    # ---- Slide 0 : Mécaniques ----------------------------------------

    def _slide_gameplay(self, px, py, pw, ph):
        ctrl   = self.params_controles
        mh     = int(pw * 0.045)
        mv     = int(ph * 0.055)
        col_w  = (pw - mh * 3) // 2
        col1_x = px + mh
        col2_x = px + mh * 2 + col_w
        y0     = py + mv

        # Titre de la slide
        titre = self.police_titre.render("Mécaniques de jeu", True, COULEUR_CYAN)
        self.ecran.blit(titre, (col1_x, y0))
        y0 += titre.get_height() + 4

        sous = self.police_petit.render(
            "Tout ce dont tu as besoin pour survivre dans l'obscurité",
            True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(sous, (col1_x, y0))
        y0 += sous.get_height() + 10

        # Séparateur
        sep = pygame.Surface((pw - mh * 2, 1), pygame.SRCALPHA)
        sep.fill((*COULEUR_CYAN, 70))
        self.ecran.blit(sep, (col1_x, y0))
        y0 += 14

        # Colonnes
        self._colonne_controles(col1_x, y0, col_w, ctrl)
        self._colonne_systemes(col2_x, y0, col_w)

    def _touche(self, cle: str) -> str:
        return self.params_controles.get(cle, '?').upper()

    def _titre_section(self, x, y, texte):
        s = self.police_bouton.render(texte, True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(s, (x, y))
        return y + s.get_height() + 6

    def _ligne(self, x, y, label, desc, couleur_label=None):
        if couleur_label is None:
            couleur_label = COULEUR_CYAN
        p = self.police_petit
        lbl = p.render(label, True, couleur_label)
        self.ecran.blit(lbl, (x, y))
        dsc = p.render(desc, True, COULEUR_TEXTE)
        self.ecran.blit(dsc, (x + lbl.get_width() + 10, y))
        return y + max(lbl.get_height(), dsc.get_height()) + 5

    def _para(self, x, y, texte, couleur=None, max_w=None):
        if couleur is None:
            couleur = COULEUR_TEXTE
        p = self.police_petit
        lignes = texte.split('\n')
        for l in lignes:
            if l.strip() == '':
                y += int(p.get_height() * 0.5)
                continue
            s = p.render(l, True, couleur)
            self.ecran.blit(s, (x, y))
            y += s.get_height() + 4
        return y + 4

    def _colonne_controles(self, x, y, w, ctrl):
        y = self._titre_section(x, y, "⌨  Contrôles")

        y = self._ligne(x, y, f"[ {self._touche('gauche')} / {self._touche('droite')} ]",
                        "Déplacement horizontal")
        y = self._ligne(x, y, f"[ {self._touche('saut')} ]",
                        "Saut  (×2 si Double Saut débloqué)")
        y = self._ligne(x, y, f"[ {self._touche('dash')} ]",
                        "Dash  (si débloqué)")
        y = self._ligne(x, y, f"[ {self._touche('echo')} ]",
                        "Écho — révèle l'environnement")
        y = self._ligne(x, y, f"[ {self._touche('attaque')} ]",
                        "Attaque de mêlée")
        y = self._ligne(x, y, "[ ÉCHAP ]", "Pause")
        y += 12

        y = self._titre_section(x, y, "⚔  Combat & Survie")
        y = self._para(x, y,
            "Tu as 5 PV. Chaque contact ennemi en retire 1.\n"
            "1 seconde d'invincibilité après un coup reçu.\n\n"
            "Les ennemis ont entre 1 et 3 PV :\n"
            "  · 1 PV — patrouilleurs rapides\n"
            "  · 2 PV — gardes standard\n"
            "  · 3 PV — gardiens lourds")

    def _colonne_systemes(self, x, y, w):
        y = self._titre_section(x, y, "🔊  Écholocalisation")
        y = self._para(x, y,
            "Le monde est dans le noir absolu.\n"
            "Active l'écho pour révéler les murs et\n"
            "obstacles proches. Un indicateur circulaire\n"
            "montre la durée restante du cooldown.\n\n"
            "Cooldown : 2.5 s  |  Portée : 150 px")
        y += 8

        y = self._titre_section(x, y, "💜  Âmes Perdues")
        y = self._para(x, y,
            "À ta mort → une âme perdue apparaît\n"
            "avec tout ton argent. Tu réapparais\n"
            "au dernier checkpoint.\n"
            "Attaque l'âme pour la récupérer.\n"
            "Mourir avant = perte définitive.")
        y += 8

        y = self._titre_section(x, y, "✨  Capacités & Progression")
        y = self._para(x, y,
            "Des orbes flottants débloquent\n"
            "définitivement Dash ou Double Saut.\n\n"
            "La porte dorée ne s'ouvre qu'avec la\n"
            "clé — ramasse-la d'abord !\n\n"
            "Checkpoints → sauvegarde automatique.")

    # ---- Slide 1 : Lore ----------------------------------------------

    def _slide_lore(self, px, py, pw, ph):
        mh = int(pw * 0.06)
        mv = int(ph * 0.055)
        x  = px + mh
        y  = py + mv
        tw = pw - mh * 2

        # Titre
        titre = self.police_titre.render("L'Univers d'Écho", True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(titre, (x, y))
        y += titre.get_height() + 4

        sous = self.police_petit.render(
            "L'histoire et le monde derrière l'obscurité",
            True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(sous, (x, y))
        y += sous.get_height() + 10

        sep = pygame.Surface((tw, 1), pygame.SRCALPHA)
        sep.fill((*COULEUR_VIOLET, 70))
        self.ecran.blit(sep, (x, y))
        y += 14

        # Deux colonnes pour le lore
        col_w  = (tw - mh) // 2
        col2_x = x + col_w + mh

        self._lore_colonne_gauche(x, y, col_w)
        self._lore_colonne_droite(col2_x, y, col_w)

    def _lore_colonne_gauche(self, x, y, w):
        y = self._titre_section(x, y, "🌑  Le Grand Silence")
        y = self._para(x, y,
            "Il y a cent ans, une catastrophe\n"
            "connue sous le nom du « Grand Silence »\n"
            "a plongé le monde dans une obscurité\n"
            "totale et permanente.\n\n"
            "Les lumières se sont éteintes. Les étoiles\n"
            "ont disparu. Les villes, autrefois\n"
            "brillantes, sont devenues des labyrinthes\n"
            "de ténèbres peuplés de créatures\n"
            "corrompues par l'absence de lumière.",
            couleur=COULEUR_TEXTE)
        y += 10

        y = self._titre_section(x, y, "🗝  La Porte Interdite")
        y = self._para(x, y,
            "Au cœur des ruines se trouve une\n"
            "porte ancienne, scellée depuis des\n"
            "siècles. Les anciens l'appelaient\n"
            "« La Porte de l'Aurore ».\n\n"
            "Derrière elle, dit-on, se trouve\n"
            "la source de la Première Lumière —\n"
            "seule capable d'inverser le Silence.",
            couleur=(200, 180, 255))

    def _lore_colonne_droite(self, x, y, w):
        y = self._titre_section(x, y, "👤  Tu es l'Éclaireur")
        y = self._para(x, y,
            "Tu es l'un des rares à maîtriser\n"
            "l'Art de l'Écho — une technique\n"
            "ancienne qui permet de percevoir\n"
            "le monde par le son.\n\n"
            "Là où les autres voient le néant,\n"
            "toi tu entends les contours,\n"
            "les passages, les dangers.",
            couleur=COULEUR_TEXTE)
        y += 10

        y = self._titre_section(x, y, "⚡  Les Âmes Errantes")
        y = self._para(x, y,
            "Les créatures qui peuplent l'obscurité\n"
            "ne sont pas de simples monstres.\n"
            "Ce sont des âmes perdues, corrompues\n"
            "par le Silence, piégées entre\n"
            "deux mondes.\n\n"
            "En les vaincant, tu libères une partie\n"
            "de leur énergie — les Âmes —\n"
            "qui te permettront de progresser.",
            couleur=(200, 180, 255))
        y += 10

        y = self._titre_section(x, y, "🎯  Ta Mission")
        y = self._para(x, y,
            "Traverse les ruines. Bats les gardiens.\n"
            "Trouve la clé. Ouvre la Porte.\n"
            "Ramène la lumière.",
            couleur=COULEUR_CYAN)

    # ------------------------------------------------------------------
    #  UI NAVIGATION
    # ------------------------------------------------------------------

    def _navigation(self):
        est_derniere = (self.index == self.total - 1)
        if est_derniere:
            self.btn_fermer.dessiner(self.ecran)
        else:
            self.btn_suivant.dessiner(self.ecran)
        if self.index > 0:
            self.btn_precedent.dessiner(self.ecran)
        self.btn_passer.dessiner(self.ecran)

    def _indicateur(self):
        rayon = 5
        espace = 16
        total_w = self.total * rayon * 2 + (self.total - 1) * espace
        x_start = self.cx - total_w // 2
        y_pos = self.hauteur - 16
        for i in range(self.total):
            x = x_start + i * (rayon * 2 + espace) + rayon
            if i == self.index:
                pygame.draw.circle(self.ecran, COULEUR_CYAN, (x, y_pos), rayon)
            else:
                pygame.draw.circle(self.ecran, COULEUR_BOUTON_SURVOL, (x, y_pos), rayon - 1)
                pygame.draw.circle(self.ecran, COULEUR_TEXTE_SOMBRE, (x, y_pos), rayon - 1, 1)