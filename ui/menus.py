# ui/menus.py
# Mixin pour la gestion de tous les menus du jeu.
# Hérité par la classe Client — toutes les méthodes accèdent à self.

import pygame
import copy
import time

from parametres import *
from utils import langue, music
from ui.bouton import Bouton
from ui.effets_visuels import dessiner_fond_echo, dessiner_titre_neon, dessiner_separateur_neon, dessiner_panneau
from sauvegarde import gestion_parametres, gestion_sauvegarde
from reseau.protocole import obtenir_ip_locale, obtenir_ip_hamachi


class MenusMixin:
    """Méthodes de création, gestion et dessin de tous les menus."""

    # ==================================================================
    #  CRÉATION DES WIDGETS
    # ==================================================================

    def creer_widgets_menu_principal(self):
        cx = self.cx
        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        esp = self._espacement_bouton() + bh

        nb_boutons = 5
        hauteur_groupe = nb_boutons * esp - self._espacement_bouton()
        y_start = self.cy - hauteur_groupe // 2 + self.hauteur_ecran // 10

        def _btn(i, texte, style="normal"):
            y = y_start + i * esp
            return Bouton(cx - lw // 2, y, lw, bh, texte, self.police_bouton, style=style)

        self.btn_nouvelle_partie = _btn(0, langue.get_texte("menu_nouvelle_partie"))
        self.btn_continuer       = _btn(1, langue.get_texte("menu_continuer"))
        self.btn_rejoindre       = _btn(2, langue.get_texte("menu_rejoindre"))
        self.btn_parametres      = _btn(3, langue.get_texte("menu_parametres"))
        self.btn_quitter         = _btn(4, langue.get_texte("menu_quitter"), style="ghost")

        self.boutons_menu_principal = [
            self.btn_nouvelle_partie, self.btn_continuer,
            self.btn_rejoindre, self.btn_parametres, self.btn_quitter
        ]
        self.btn_copier_ip_locale = Bouton(0, 0, 300, 36, "", self.police_petit)

    def creer_widgets_menu_rejoindre(self):
        cx = self.cx
        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        cy = self.cy

        # Mode de connexion : "ip" ou "code"
        self.mode_rejoindre = "ip" if not RELAY_HOST else "code"

        # --- Champ IP ---
        self.input_box_ip   = pygame.Rect(cx - lw // 2, cy - 30, lw, 46)
        self.input_ip_texte = ""
        self.input_ip_actif = False

        # --- Champ Code Room ---
        self.input_box_code   = pygame.Rect(cx - lw // 2, cy - 30, lw, 46)
        self.input_code_texte = ""
        self.input_code_actif = False

        # --- Bouton toggle mode ---
        self.btn_mode_connexion = Bouton(
            cx - lw // 2, cy - 30 - bh - 16, lw, bh,
            langue.get_texte("rejoindre_mode_code" if self.mode_rejoindre == "code" else "rejoindre_mode_ip"),
            self.police_bouton, style="ghost"
        )

        self.btn_connecter       = Bouton(cx - lw // 2, cy + 40, lw, bh,
                                        langue.get_texte("rejoindre_connecter"),
                                        self.police_bouton)
        self.btn_retour_rejoindre = Bouton(cx - lw // 2, cy + 40 + bh + 12, lw, bh,
                                        langue.get_texte("rejoindre_retour"),
                                        self.police_bouton, style="ghost")
        self.btn_erreur_ok = Bouton(cx - 60, cy + 90, 120, bh, "OK",
                                    self.police_bouton, style="danger")
        lw_coller = 90
        self.btn_coller_ip = Bouton(
            cx + lw // 2 + 10, cy - 30, lw_coller, 46,
            "Coller", self.police_bouton, style="ghost"
        )

    def creer_widgets_menu_parametres(self):
        cx = self.cx
        col_droite = cx + 60
        lw_param = max(200, min(300, self.largeur_ecran // 6))
        bh_param = max(34, self.hauteur_ecran // 28)

        def _p(texte=""):
            return Bouton(col_droite, 0, lw_param, bh_param, texte, self.police_petit)

        self.btn_copier_ip_locale    = _p()
        self.btn_copier_ip_hamachi   = _p()
        self.btn_changer_langue      = _p()
        self.btn_toggle_plein_ecran  = _p()
        self.btn_changer_resolution  = _p()
        self.btn_toggle_musique      = _p()
        self.btn_toggle_sfx          = _p()
        self.btn_changer_gauche      = _p()
        self.btn_changer_droite      = _p()
        self.btn_changer_saut        = _p()
        self.btn_changer_echo        = _p()
        self.btn_changer_attaque     = _p()
        self.btn_changer_dash        = _p()
        self.btn_changer_echo_dir    = _p()

        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        y_bas = self.hauteur_ecran - max(70, self.hauteur_ecran // 14)

        self.btn_appliquer_params = Bouton(cx - lw - 10, y_bas, lw, bh,
                                        langue.get_texte("param_appliquer"),
                                        self.police_bouton, style="confirm")
        self.btn_retour_params    = Bouton(cx + 10, y_bas, lw, bh,
                                        langue.get_texte("param_retour"),
                                        self.police_bouton, style="ghost")

        self.boutons_menu_params_scrollables = [
            self.btn_changer_langue,
            self.btn_toggle_plein_ecran,
            self.btn_changer_resolution,
            self.btn_toggle_musique,
            self.btn_toggle_sfx,
            self.btn_changer_gauche, self.btn_changer_droite,
            self.btn_changer_saut, self.btn_changer_echo,
            self.btn_changer_attaque, self.btn_changer_dash,
            self.btn_copier_ip_locale, self.btn_copier_ip_hamachi,
        ]
        self.boutons_menu_params_fixes = [
            self.btn_appliquer_params, self.btn_retour_params
        ]

    def creer_widgets_menu_confirmation(self):
        cx = self.cx
        cy = self.cy
        w_popup = max(400, min(520, self.largeur_ecran // 4))
        h_popup = max(220, min(280, self.hauteur_ecran // 4))
        self.rect_popup = pygame.Rect(cx - w_popup // 2, cy - h_popup // 2,
                                    w_popup, h_popup)
        bh = self._hauteur_bouton()
        lw_btn = w_popup // 3
        self.btn_popup_oui = Bouton(cx - lw_btn - 10, cy + h_popup // 2 - bh - 16,
                                    lw_btn, bh,
                                    langue.get_texte("popup_oui"),
                                    self.police_bouton, style="confirm")
        self.btn_popup_non = Bouton(cx + 10, cy + h_popup // 2 - bh - 16,
                                    lw_btn, bh,
                                    langue.get_texte("popup_non"),
                                    self.police_bouton, style="danger")
        self.boutons_confirmation = [self.btn_popup_oui, self.btn_popup_non]

    def creer_widgets_menu_pause(self):
        cx = self.cx
        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        esp = bh + self._espacement_bouton()
        y0 = self.cy - esp

        self.btn_pause_reprendre    = Bouton(cx - lw // 2, y0,            lw, bh,
                                            langue.get_texte("pause_reprendre"),
                                            self.police_bouton)
        self.btn_pause_parametres   = Bouton(cx - lw // 2, y0 + esp,      lw, bh,
                                            langue.get_texte("pause_parametres"),
                                            self.police_bouton)
        self.btn_pause_quitter      = Bouton(cx - lw // 2, y0 + esp * 2,  lw, bh,
                                            langue.get_texte("pause_quitter_session"),
                                            self.police_bouton, style="ghost")

        self.boutons_menu_pause = [
            self.btn_pause_reprendre, self.btn_pause_parametres,
            self.btn_pause_quitter
        ]

        self.surface_fond_pause = pygame.Surface(
            (self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
        self.surface_fond_pause.fill(COULEUR_FOND_PAUSE)

    def creer_widgets_menu_slots(self):
        self.infos_slots  = []
        self.boutons_slots = []
        cx  = self.cx
        lw  = max(400, int(self.largeur_ecran * 0.55))
        bh  = max(64, self.hauteur_ecran // 14)
        esp = bh + max(14, self.hauteur_ecran // 60)

        nb = NB_SLOTS_SAUVEGARDE
        hauteur_groupe = nb * esp - (esp - bh)
        y_start = self.cy - hauteur_groupe // 2

        for i in range(nb):
            btn = Bouton(cx - lw // 2, y_start + i * esp, lw, bh,
                        f"Slot {i+1}", self.police_bouton)
            self.boutons_slots.append(btn)

        y_retour = y_start + nb * esp + 16
        self.btn_retour_slots = Bouton(cx - self._largeur_bouton() // 2, y_retour,
                                    self._largeur_bouton(), self._hauteur_bouton(),
                                    langue.get_texte("rejoindre_retour"),
                                    self.police_bouton, style="ghost")

    # ==================================================================
    #  GESTION + DESSIN — MENU PRINCIPAL
    # ==================================================================

    def gerer_menu_principal(self, pos_souris):
        for btn in self.boutons_menu_principal:
            btn.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if self.btn_nouvelle_partie.verifier_clic(event):
                self.etat_jeu = "MENU_NOUVELLE_PARTIE"
                self.infos_slots = gestion_sauvegarde.get_infos_slots()
            if self.btn_continuer.verifier_clic(event):
                self.etat_jeu = "MENU_CONTINUER"
                self.infos_slots = gestion_sauvegarde.get_infos_slots()
            if self.btn_rejoindre.verifier_clic(event):
                self.etat_jeu = "MENU_REJOINDRE"
            if self.btn_parametres.verifier_clic(event):
                self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu_precedent = "MENU_PRINCIPAL"
                self.etat_jeu = "MENU_PARAMETRES"
            if self.btn_quitter.verifier_clic(event):
                self.etat_jeu = "QUITTER"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                lien_rect = self.police_petit.render("florian-croiset.github.io/jeusite/", True, COULEUR_CYAN_SOMBRE).get_rect(bottomleft=(20, self.hauteur_ecran - 12))
                if lien_rect.collidepoint(event.pos):
                    import webbrowser
                    webbrowser.open("https://florian-croiset.github.io/jeusite/")

    def dessiner_menu_principal(self):
        t = self.temps_anim
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran, t)

        cy_titre = max(80, self.hauteur_ecran // 7)
        police_grand_titre = pygame.font.Font(None, max(96, self.hauteur_ecran // 7))
        dessiner_titre_neon(self.ecran, police_grand_titre,
                            langue.get_texte("titre_jeu"),
                            self.cx, cy_titre)

        sub = self.police_petit.render("par la Team Nightberry", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(sub, sub.get_rect(center=(self.cx, cy_titre + police_grand_titre.get_height() // 2 + 20)))

        marge = self.largeur_ecran // 6
        dessiner_separateur_neon(self.ecran,
                                marge, cy_titre + police_grand_titre.get_height() // 2 + 50,
                                self.largeur_ecran - marge)

        for btn in self.boutons_menu_principal:
            btn.dessiner(self.ecran)

        ver = self.police_petit.render("v1.2 — Beta", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(ver, (self.largeur_ecran - ver.get_width() - 20,
                            self.hauteur_ecran - ver.get_height() - 12))

        lien_texte = "https://florian-croiset.github.io/jeusite/"
        pos_souris = pygame.mouse.get_pos()
        lien_surf = self.police_petit.render(lien_texte, True, COULEUR_CYAN_SOMBRE)
        lien_rect = lien_surf.get_rect(bottomleft=(20, self.hauteur_ecran - 12))
        if lien_rect.collidepoint(pos_souris):
            lien_surf = self.police_petit.render(lien_texte, True, COULEUR_CYAN)
        self.ecran.blit(lien_surf, lien_rect)

    # ==================================================================
    #  GESTION + DESSIN — MENU REJOINDRE
    # ==================================================================

    def _tenter_connexion_rejoindre(self):
        """Lance la connexion selon le mode actuel (IP ou Code Room)."""
        if self.mode_rejoindre == "code":
            code = self.input_code_texte.strip().upper()
            if len(code) < 4:
                self.message_erreur_connexion = langue.get_texte("rejoindre_code_invalide")
                return
            if self.connecter_relay(code):
                self.etat_jeu = "EN_JEU"
        else:
            hote = self.input_ip_texte if self.input_ip_texte else "localhost"
            if self.connecter(hote):
                self.etat_jeu = "EN_JEU"

    def _coller_presse_papier(self):
        """Récupère le texte du presse-papier (multi-plateforme)."""
        try:
            texte = pygame.scrap.get(pygame.SCRAP_TEXT)
            if texte:
                return texte.decode('utf-8', errors='ignore').rstrip('\x00').strip()
        except Exception:
            pass
        try:
            import subprocess
            result = subprocess.run(
                ['powershell', '-command', 'Get-Clipboard'],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def gerer_menu_rejoindre(self, pos_souris):
        if self.message_erreur_connexion:
            self.btn_erreur_ok.verifier_survol(pos_souris)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.etat_jeu = "QUITTER"
                if self.btn_erreur_ok.verifier_clic(event):
                    self.message_erreur_connexion = None
            return

        self.btn_connecter.verifier_survol(pos_souris)
        self.btn_retour_rejoindre.verifier_survol(pos_souris)
        self.btn_coller_ip.verifier_survol(pos_souris)
        if RELAY_HOST:
            self.btn_mode_connexion.verifier_survol(pos_souris)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"

            if self.btn_retour_rejoindre.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"

            # Toggle mode IP / Code Room
            if RELAY_HOST and self.btn_mode_connexion.verifier_clic(event):
                if self.mode_rejoindre == "ip":
                    self.mode_rejoindre = "code"
                    self.btn_mode_connexion.texte = langue.get_texte("rejoindre_mode_code")
                else:
                    self.mode_rejoindre = "ip"
                    self.btn_mode_connexion.texte = langue.get_texte("rejoindre_mode_ip")

            if self.btn_connecter.verifier_clic(event):
                self._tenter_connexion_rejoindre()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.mode_rejoindre == "ip":
                    self.input_ip_actif = self.input_box_ip.collidepoint(event.pos)
                    self.input_code_actif = False
                else:
                    self.input_code_actif = self.input_box_code.collidepoint(event.pos)
                    self.input_ip_actif = False

            if self.btn_coller_ip.verifier_clic(event):
                texte_colle = self._coller_presse_papier()
                if texte_colle:
                    if self.mode_rejoindre == "ip":
                        self.input_ip_texte = texte_colle
                        self.input_ip_actif = True
                    else:
                        self.input_code_texte = texte_colle.upper()[:6]
                        self.input_code_actif = True

            # Saisie clavier
            if event.type == pygame.KEYDOWN:
                if self.mode_rejoindre == "ip" and self.input_ip_actif:
                    if event.key == pygame.K_RETURN:
                        self._tenter_connexion_rejoindre()
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_ip_texte = self.input_ip_texte[:-1]
                    else:
                        self.input_ip_texte += event.unicode
                elif self.mode_rejoindre == "code" and self.input_code_actif:
                    if event.key == pygame.K_RETURN:
                        self._tenter_connexion_rejoindre()
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_code_texte = self.input_code_texte[:-1]
                    elif len(self.input_code_texte) < 6 and event.unicode.isalpha():
                        self.input_code_texte += event.unicode.upper()

    def dessiner_menu_rejoindre(self):
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran,
                        self.temps_anim)
        dessiner_titre_neon(self.ecran, self.police_titre,
                            langue.get_texte("rejoindre_titre"),
                            self.cx, self.hauteur_ecran // 7)

        pan_w = self._largeur_bouton() + 80
        pan_h = 280 if RELAY_HOST else 220
        pan_rect = pygame.Rect(self.cx - pan_w // 2,
                            self.cy - pan_h // 2 - 20,
                            pan_w, pan_h)
        dessiner_panneau(self.ecran, pan_rect)

        y_contenu = pan_rect.y + 36

        # Bouton toggle mode (si relay configuré)
        if RELAY_HOST:
            self.btn_mode_connexion.rect.center = (self.cx, y_contenu)
            self.btn_mode_connexion.dessiner(self.ecran)
            y_contenu += 46

        # Label
        if self.mode_rejoindre == "code":
            label_texte = langue.get_texte("rejoindre_label_code")
        else:
            label_texte = langue.get_texte("rejoindre_label_ip")
        label = self.police_texte.render(label_texte, True, COULEUR_TEXTE)
        self.ecran.blit(label, label.get_rect(center=(self.cx, y_contenu)))

        y_contenu += 28

        # Champ de saisie
        if self.mode_rejoindre == "code":
            # Champ code room
            input_box = self.input_box_code
            input_box.y = y_contenu
            is_actif = self.input_code_actif
            texte = self.input_code_texte
        else:
            # Champ IP
            input_box = self.input_box_ip
            input_box.y = y_contenu
            is_actif = self.input_ip_actif
            texte = self.input_ip_texte

        bord_color = COULEUR_CYAN if is_actif else COULEUR_CYAN_SOMBRE
        pygame.draw.rect(self.ecran, COULEUR_INPUT_BOX,
                        input_box, border_radius=6)
        pygame.draw.rect(self.ecran, bord_color,
                        input_box, width=1, border_radius=6)

        # Affichage texte avec espacement pour les codes
        if self.mode_rejoindre == "code":
            texte_affiche = "  ".join(texte) if texte else ""
            txt_surf = self.police_texte.render(texte_affiche, True, COULEUR_TEXTE)
        else:
            txt_surf = self.police_texte.render(texte, True, COULEUR_TEXTE)

        self.ecran.blit(txt_surf, (input_box.x + 12, input_box.y + 10))

        if is_actif and int(time.time() * 2) % 2 == 0:
            cx_cur = input_box.x + 14 + txt_surf.get_width()
            cy_cur = input_box.y + 8
            pygame.draw.rect(self.ecran, COULEUR_CYAN,
                            pygame.Rect(cx_cur, cy_cur, 2,
                                        self.police_texte.get_height() - 6))

        # Bouton coller
        self.btn_coller_ip.rect.y = input_box.y
        self.btn_coller_ip.dessiner(self.ecran)

        # Boutons action
        y_btns = input_box.y + 60
        self.btn_connecter.rect.y = y_btns
        self.btn_retour_rejoindre.rect.y = y_btns + self._hauteur_bouton() + 12
        self.btn_connecter.dessiner(self.ecran)
        self.btn_retour_rejoindre.dessiner(self.ecran)

        if self.message_erreur_connexion:
            self._dessiner_popup_erreur()

    def _dessiner_popup_erreur(self):
        cx, cy = self.cx, self.cy
        w_popup = max(440, min(600, self.largeur_ecran // 3))
        h_popup = max(200, min(260, self.hauteur_ecran // 4))
        rect_popup = pygame.Rect(cx - w_popup // 2, cy - h_popup // 2,
                                w_popup, h_popup)

        overlay = pygame.Surface((self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.ecran.blit(overlay, (0, 0))

        dessiner_panneau(self.ecran, rect_popup, couleur_bordure=(220, 50, 50))
        titre_surf = self.police_texte.render("Erreur de connexion", True, (220, 50, 50))
        self.ecran.blit(titre_surf, titre_surf.get_rect(center=(cx, rect_popup.y + 36)))
        dessiner_separateur_neon(self.ecran,
                                rect_popup.x + 20, rect_popup.y + 58,
                                rect_popup.right - 20, couleur=(220, 50, 50))

        police_msg = self.police_petit
        lignes = self.message_erreur_connexion.split('\n')
        for i, ligne in enumerate(lignes):
            s = police_msg.render(ligne, True, COULEUR_TEXTE)
            self.ecran.blit(s, s.get_rect(center=(cx, rect_popup.y + 90 + i * 26)))

        self.btn_erreur_ok.rect.center = (cx, rect_popup.bottom - 36)
        self.btn_erreur_ok.dessiner(self.ecran)

    # ==================================================================
    #  GESTION + DESSIN — MENU SLOTS
    # ==================================================================

    def gerer_menu_slots(self, pos_souris):
        tous = self.boutons_slots + [self.btn_retour_slots]
        for btn in tous:
            btn.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if self.btn_retour_slots.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"
            for id_slot, btn_slot in enumerate(self.boutons_slots):
                if btn_slot.verifier_clic(event):
                    if self.etat_jeu == "MENU_NOUVELLE_PARTIE":
                        if not self.infos_slots[id_slot]["est_vide"]:
                            self.id_slot_a_ecraser = id_slot
                            self.etat_jeu = "MENU_CONFIRMATION"
                        else:
                            self.lancer_partie_locale(id_slot, est_nouvelle_partie=True)
                    elif self.etat_jeu == "MENU_CONTINUER":
                        if not self.infos_slots[id_slot]["est_vide"]:
                            self.lancer_partie_locale(id_slot, est_nouvelle_partie=False)

    def dessiner_menu_slots(self):
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran,
                        self.temps_anim)
        titre_cle = ("slots_titre_nouvelle"
                    if self.etat_jeu == "MENU_NOUVELLE_PARTIE"
                    else "slots_titre_continuer")
        dessiner_titre_neon(self.ecran, self.police_titre,
                            langue.get_texte(titre_cle),
                            self.cx, self.hauteur_ecran // 7)

        for id_slot, btn_slot in enumerate(self.boutons_slots):
            info = self.infos_slots[id_slot] if id_slot < len(self.infos_slots) else None
            if not info:
                continue
            est_vide = info["est_vide"]
            mode_continuer = (self.etat_jeu == "MENU_CONTINUER")
            if mode_continuer and est_vide:
                btn_slot.style = "ghost"
            else:
                btn_slot.style = "normal"
                btn_slot._definir_style(btn_slot.style)
            btn_slot.texte = info["nom"]
            btn_slot.dessiner(self.ecran)
            if info["description"]:
                desc_c = COULEUR_TEXTE_SOMBRE if (mode_continuer and est_vide) else COULEUR_TEXTE
                desc = self.police_petit.render(info["description"], True, desc_c)
                self.ecran.blit(desc, desc.get_rect(
                    center=(btn_slot.rect.centerx,
                            btn_slot.rect.centery + 14)))
        self.btn_retour_slots.dessiner(self.ecran)

    # ==================================================================
    #  GESTION + DESSIN — MENU CONFIRMATION
    # ==================================================================

    def gerer_menu_confirmation(self, pos_souris):
        for btn in self.boutons_confirmation:
            btn.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if self.btn_popup_oui.verifier_clic(event):
                self.lancer_partie_locale(self.id_slot_a_ecraser,
                                        est_nouvelle_partie=True)
            if self.btn_popup_non.verifier_clic(event):
                self.id_slot_a_ecraser = None
                self.etat_jeu = "MENU_NOUVELLE_PARTIE"

    def dessiner_menu_confirmation(self):
        self.dessiner_menu_slots()
        overlay = pygame.Surface((self.largeur_ecran, self.hauteur_ecran),
                                pygame.SRCALPHA)
        overlay.fill((0, 0, 10, 180))
        self.ecran.blit(overlay, (0, 0))
        dessiner_panneau(self.ecran, self.rect_popup,
                        couleur_bordure=COULEUR_VIOLET, alpha_fond=245)
        titre = self.police_bouton.render(
            langue.get_texte("popup_titre"), True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(titre, titre.get_rect(
            center=(self.rect_popup.centerx, self.rect_popup.y + 50)))
        dessiner_separateur_neon(self.ecran,
                                self.rect_popup.x + 20, self.rect_popup.y + 76,
                                self.rect_popup.right - 20,
                                couleur=COULEUR_VIOLET_SOMBRE, alpha=140)
        msg = self.police_texte.render(
            langue.get_texte("popup_message"), True, COULEUR_TEXTE)
        self.ecran.blit(msg, msg.get_rect(
            center=(self.rect_popup.centerx, self.rect_popup.centery - 10)))
        self.btn_popup_oui.dessiner(self.ecran)
        self.btn_popup_non.dessiner(self.ecran)

    # ==================================================================
    #  GESTION + DESSIN — MENU PARAMÈTRES
    # ==================================================================

    def gerer_menu_parametres(self, pos_souris):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if event.type == pygame.MOUSEWHEEL:
                self.scroll_y_params += event.y * 20
                self.scroll_y_params = max(-500, min(0, self.scroll_y_params))
            if self.touche_a_modifier:
                if event.type == pygame.KEYDOWN:
                    if event.key not in [pygame.K_ESCAPE, pygame.K_RETURN]:
                        nom_touche = pygame.key.name(event.key)
                        self.parametres_temp['controles'][self.touche_a_modifier] = nom_touche
                        self.touche_a_modifier = None
            else:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.parametres_temp = {}
                    self.etat_jeu = self.etat_jeu_precedent
                if self.btn_retour_params.verifier_clic(event):
                    self.parametres_temp = {}
                    self.touche_a_modifier = None
                    self.scroll_y_params = 0
                    self.etat_jeu = self.etat_jeu_precedent
                if self.btn_appliquer_params.verifier_clic(event):
                    self.parametres = copy.deepcopy(self.parametres_temp)
                    gestion_parametres.sauvegarder_parametres(self.parametres)
                    self.appliquer_parametres_video()
                    self._recalculer_codes_touches()
                    music.toggle(self.parametres['video'].get('musique', True))
                    music.activer_sfx(self.parametres['sons'].get('activer_sfx', True))
                    self.actualiser_langues_widgets()
                    self.touche_a_modifier = None
                    self.scroll_y_params = 0
                    self.etat_jeu = self.etat_jeu_precedent
                if self.btn_toggle_plein_ecran.verifier_clic(event):
                    self.parametres_temp['video']['plein_ecran'] = \
                        not self.parametres_temp['video']['plein_ecran']
                if self.btn_changer_resolution.verifier_clic(event):
                    if not self.parametres_temp['video']['plein_ecran']:
                        resolutions = get_resolutions_compatibles(self.resolution_native)
                        current = tuple(self.parametres_temp['video'].get(
                            'resolution', [LARGEUR_ECRAN, HAUTEUR_ECRAN]))
                        try:
                            idx = resolutions.index(current)
                            nouvelle = resolutions[(idx + 1) % len(resolutions)]
                        except ValueError:
                            nouvelle = resolutions[0]
                        self.parametres_temp['video']['resolution'] = list(nouvelle)
                if self.btn_toggle_musique.verifier_clic(event):
                    self.parametres_temp['video']['musique'] = not self.parametres_temp['video'].get('musique', True)
                if self.btn_toggle_sfx.verifier_clic(event):
                    self.parametres_temp['sons']['activer_sfx'] = not self.parametres_temp['sons'].get('activer_sfx', True)
                if self.btn_changer_langue.verifier_clic(event):
                    langues = ['fr', 'en']
                    actuelle = self.parametres_temp['jouabilite']['langue']
                    try:
                        idx = langues.index(actuelle)
                        nouvelle = langues[(idx + 1) % len(langues)]
                    except ValueError:
                        nouvelle = 'fr'
                    self.parametres_temp['jouabilite']['langue'] = nouvelle
                if self.btn_changer_gauche.verifier_clic(event):
                    self.touche_a_modifier = "gauche"
                if self.btn_changer_droite.verifier_clic(event):
                    self.touche_a_modifier = "droite"
                if self.btn_changer_saut.verifier_clic(event):
                    self.touche_a_modifier = "saut"
                if self.btn_changer_echo.verifier_clic(event):
                    self.touche_a_modifier = "echo"
                if self.btn_changer_attaque.verifier_clic(event):
                    self.touche_a_modifier = "attaque"
                if self.btn_changer_dash.verifier_clic(event):
                    self.touche_a_modifier = 'dash'
                if self.btn_changer_echo_dir.verifier_clic(event):
                    self.touche_a_modifier = 'echo_dir'
                if self.btn_copier_ip_locale.verifier_clic(event):
                    ip = obtenir_ip_locale()
                    self.copier_dans_presse_papier(ip)
                if self.btn_copier_ip_hamachi.verifier_clic(event):
                    ip = obtenir_ip_hamachi()
                    if ip != "Non connecté":
                        self.copier_dans_presse_papier(ip)
        for btn in self.boutons_menu_params_fixes + self.boutons_menu_params_scrollables:
            btn.verifier_survol(pos_souris)

    def dessiner_menu_parametres(self):
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran,
                        self.temps_anim)
        police_titre_params = pygame.font.Font(None, max(48, self.hauteur_ecran // 14))
        dessiner_titre_neon(self.ecran, police_titre_params,
                            langue.get_texte("param_titre"),
                            self.cx, self.hauteur_ecran // 14)

        y = int(self.hauteur_ecran * 0.12) + self.scroll_y_params
        params = self.parametres_temp if self.parametres_temp else self.parametres
        col_droite = self.cx + 60
        col_gauche = 100
        esp_ligne = max(44, self.hauteur_ecran // 22)

        def section(titre_texte):
            nonlocal y
            dessiner_separateur_neon(self.ecran, col_gauche, y,
                                    self.largeur_ecran - col_gauche, alpha=100)
            y += 6
            s = self.police_bouton.render(titre_texte, True, COULEUR_VIOLET_CLAIR)
            self.ecran.blit(s, (col_gauche, y))
            y += esp_ligne

        def ligne_controle(label, cle_json, btn):
            nonlocal y
            lbl = self.police_texte.render(label, True, COULEUR_TEXTE)
            self.ecran.blit(lbl, (col_gauche + 20, y + 6))
            btn.rect.y = y
            txt = params['controles'][cle_json].upper()
            if self.touche_a_modifier == cle_json:
                txt = langue.get_texte("param_attente_touche")
                btn.style = "confirm"
            else:
                btn.style = "normal"
                btn._definir_style(btn.style)
            btn.texte = txt
            btn.dessiner(self.ecran)
            y += esp_ligne

        def ligne_toggle(label, valeur_bool, btn, txt_vrai, txt_faux):
            nonlocal y
            lbl = self.police_texte.render(label, True, COULEUR_TEXTE)
            self.ecran.blit(lbl, (col_gauche + 20, y + 6))
            btn.rect.y = y
            btn.texte = txt_vrai if valeur_bool else txt_faux
            btn.style = "confirm" if valeur_bool else "normal"
            btn._definir_style(btn.style)
            btn.dessiner(self.ecran)
            y += esp_ligne

        def ligne_ip(label, texte_btn, btn):
            nonlocal y
            lbl = self.police_texte.render(label, True, COULEUR_TEXTE)
            self.ecran.blit(lbl, (col_gauche + 20, y + 6))
            btn.rect.y = y
            btn.texte = texte_btn
            btn.dessiner(self.ecran)
            y += esp_ligne

        section(langue.get_texte("param_section_jouabilite"))
        lbl_lng = self.police_texte.render(langue.get_texte("param_langue"), True, COULEUR_TEXTE)
        self.ecran.blit(lbl_lng, (col_gauche + 20, y + 6))
        self.btn_changer_langue.rect.y = y
        self.btn_changer_langue.texte = params['jouabilite']['langue'].upper()
        self.btn_changer_langue.dessiner(self.ecran)
        y += esp_ligne

        section(langue.get_texte("param_section_video"))
        ligne_toggle(langue.get_texte("param_plein_ecran"),
                    params['video']['plein_ecran'],
                    self.btn_toggle_plein_ecran,
                    langue.get_texte("param_oui"),
                    langue.get_texte("param_non"))

        # --- Résolution (grisé si plein écran) ---
        est_plein_ecran = params['video']['plein_ecran']
        if est_plein_ecran:
            res_txt = f"{self.resolution_native[0]}x{self.resolution_native[1]}"
            self.btn_changer_resolution.style = "disabled"
            self.btn_changer_resolution._definir_style("disabled")
        else:
            res = params['video'].get('resolution', [LARGEUR_ECRAN, HAUTEUR_ECRAN])
            res_txt = f"{res[0]}x{res[1]}"
            self.btn_changer_resolution.style = "normal"
            self.btn_changer_resolution._definir_style("normal")
        lbl_res_color = COULEUR_TEXTE_SOMBRE if est_plein_ecran else COULEUR_TEXTE
        lbl_res = self.police_texte.render(
            langue.get_texte("param_resolution"), True, lbl_res_color)
        self.ecran.blit(lbl_res, (col_gauche + 20, y + 6))
        self.btn_changer_resolution.rect.y = y
        self.btn_changer_resolution.texte = res_txt
        self.btn_changer_resolution.dessiner(self.ecran)
        y += esp_ligne

        ligne_toggle("Musique",
                    params['video'].get('musique', True),
                    self.btn_toggle_musique,
                    langue.get_texte("param_oui"),
                    langue.get_texte("param_non"))
        ligne_toggle("Sons (SFX)",
            params['sons'].get('activer_sfx', True),
            self.btn_toggle_sfx,
            langue.get_texte("param_oui"),
            langue.get_texte("param_non"))

        section(langue.get_texte("param_section_controles"))
        ligne_controle(langue.get_texte("param_gauche"),   'gauche',  self.btn_changer_gauche)
        ligne_controle(langue.get_texte("param_droite"),   'droite',  self.btn_changer_droite)
        ligne_controle(langue.get_texte("param_saut"),     'saut',    self.btn_changer_saut)
        ligne_controle(langue.get_texte("param_echo"),     'echo',    self.btn_changer_echo)
        ligne_controle(langue.get_texte("param_attaque"),  'attaque', self.btn_changer_attaque)
        ligne_controle(langue.get_texte("param_dash"), 'dash', self.btn_changer_dash)
        ligne_controle(langue.get_texte("param_echo_dir"), 'echo_dir', self.btn_changer_echo_dir)

        section(langue.get_texte("param_section_reseau"))
        ligne_ip("IP Locale (LAN) :",
                f"{obtenir_ip_locale()}   (copier)",
                self.btn_copier_ip_locale)
        ligne_ip("IP Hamachi (VPN) :",
                f"{obtenir_ip_hamachi()}   (copier)",
                self.btn_copier_ip_hamachi)

        aide = self.police_petit.render(
            "Cliquez pour copier dans le presse-papiers", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(aide, (col_gauche + 20, y))

        self.btn_appliquer_params.dessiner(self.ecran)
        self.btn_retour_params.dessiner(self.ecran)

    # ==================================================================
    #  GESTION + DESSIN — MENU PAUSE
    # ==================================================================

    def dessiner_menu_pause(self):
        self.ecran.blit(self.surface_fond_pause, (0, 0))
        dessiner_titre_neon(self.ecran, self.police_titre,
                            langue.get_texte("pause_titre"),
                            self.cx,
                            self.cy - int(self.hauteur_ecran * 0.22))
        est_hote = (self.mon_id == 0)
        for btn in self.boutons_menu_pause:
            btn.dessiner(self.ecran)

    def gerer_evenements_pause(self, pos_souris):
        for btn in self.boutons_menu_pause:
            btn.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.etat_jeu_interne = "JEU"
                music.reprendre()
            if self.btn_pause_reprendre.verifier_clic(event):
                self.etat_jeu_interne = "JEU"
                music.reprendre()
            if self.btn_pause_parametres.verifier_clic(event):
                self.etat_jeu_precedent = "EN_JEU"
                self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu_interne = "PARAMETRES_JEU"
            if self.btn_pause_quitter.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"
