# client.py

from parametres import *
import envoyer_logs
if MODE_DEV:
    envoyer_logs.activer_capture()   # ← UNE seule ligne, c'est tout

import pygame
import socket
import pickle
import sys
import threading
import serveur
import time
import copy
import os
import math

from parametres import *
from carte import Carte
from joueur import Joueur
from ennemi import Ennemi
from ame_perdue import AmePerdue
from ame_libre import AmeLibre
from cle import Cle
from torche import Torche
import gestion_parametres
import langue
from bouton import Bouton
import gestion_sauvegarde


# ======================================================================
#  UTILITAIRES VISUELS ECHO
# ======================================================================

def dessiner_fond_echo(surface, largeur, hauteur, temps):
    """
    Fond animé style Echo :
      - dégradé vertical bleu-nuit
      - grille de particules subtile
      - lueur centrale pulsante
    """
    # 1. Fond de base dégradé vertical
    if FOND_MENU:
        for y in range(hauteur):
            ratio = y / hauteur
            r = int(8  + ratio * 4)
            g = int(8  + ratio * 2)
            b = int(20 + ratio * 15)
            pygame.draw.line(surface, (r, g, b), (0, y), (largeur, y))
    else:
        surface.fill((0, 0, 0))

    # 2. Grille en perspective (lignes horizontales fines)
    if HALOS_MENU:
        nb_lignes = 12
        grille_surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        for i in range(nb_lignes):
            ratio = (i + 1) / nb_lignes
            y_pos = int(hauteur * 0.55 + ratio * hauteur * 0.6)
            if y_pos >= hauteur:
                break
            alpha = int(12 + ratio * 25)
            epaisseur = 1 if ratio < 0.6 else 2
            pygame.draw.line(grille_surf, (0, 180, 255, alpha),
                            (0, y_pos), (largeur, y_pos), epaisseur)

        # Lignes verticales de la grille
        nb_v = 20
        for i in range(nb_v + 1):
            ratio_x = i / nb_v
            x_vanish = largeur // 2
            y_vanish = int(hauteur * 0.55)
            x_bas = int(ratio_x * largeur)
            alpha = int(8 + abs(ratio_x - 0.5) * 20)
            pygame.draw.line(grille_surf, (0, 150, 220, alpha),
                            (x_vanish, y_vanish), (x_bas, hauteur), 1)
        surface.blit(grille_surf, (0, 0))

    # 3. Lueur centrale pulsante (cyan)
    if HALOS_MENU:
        pulse = 0.75 + 0.25 * math.sin(temps / 1200)
        glow_surf = pygame.Surface((largeur, hauteur), pygame.SRCALPHA)
        cx, cy = largeur // 2, int(hauteur * 0.38)
        for rayon, alpha_base in [(420, 18), (280, 30), (150, 45), (70, 25)]:
            a = int(alpha_base * pulse)
            pygame.draw.circle(glow_surf, (0, 180, 255, a), (cx, cy), rayon)
        surface.blit(glow_surf, (0, 0))


def dessiner_separateur_neon(surface, x1, y, x2, couleur=None, alpha=180):
    """Ligne séparatrice style néon avec dégradé de transparence."""
    if couleur is None:
        couleur = COULEUR_CYAN
    sep_surf = pygame.Surface((x2 - x1, 2), pygame.SRCALPHA)
    r, g, b = couleur
    largeur = x2 - x1
    for px in range(largeur):
        ratio = px / largeur
        dist_centre = abs(ratio - 0.5) * 2   # 0 au centre, 1 aux bords
        a = int(alpha * (1 - dist_centre ** 1.5))
        sep_surf.set_at((px, 0), (r, g, b, a))
        sep_surf.set_at((px, 1), (r, g, b, a // 3))
    surface.blit(sep_surf, (x1, y))


def dessiner_titre_neon(surface, police, texte, cx, cy, couleur_neon=None):
    """Titre avec effet de lueur néon multicouche."""
    if couleur_neon is None:
        couleur_neon = COULEUR_CYAN
    r, g, b = couleur_neon

    # Couches de glow (de la plus grande à la plus petite)
    for decal, alpha in [(6, 15), (4, 25), (2, 40)]:
        for dx in (-decal, 0, decal):
            for dy in (-decal, 0, decal):
                if dx == 0 and dy == 0:
                    continue
                glow = police.render(texte, True, (r, g, b))
                glow.set_alpha(alpha)
                rect = glow.get_rect(center=(cx + dx, cy + dy))
                surface.blit(glow, rect)

    # Texte principal
    surf = police.render(texte, True, couleur_neon)
    rect = surf.get_rect(center=(cx, cy))
    surface.blit(surf, rect)


def dessiner_panneau(surface, rect, couleur_bordure=None, alpha_fond=220):
    """Panneau semi-transparent avec bordure néon et coin biseautés."""
    if couleur_bordure is None:
        couleur_bordure = COULEUR_CYAN_SOMBRE

    # Fond
    fond_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    r_fond = (COULEUR_FOND_PANEL[0], COULEUR_FOND_PANEL[1], COULEUR_FOND_PANEL[2], alpha_fond)
    pygame.draw.rect(fond_surf, r_fond,
                     pygame.Rect(0, 0, rect.width, rect.height),
                     border_radius=12)
    surface.blit(fond_surf, rect.topleft)

    # Bordure extérieure
    pygame.draw.rect(surface, couleur_bordure, rect, width=1, border_radius=12)

    # Reflet du haut (ligne lumineuse)
    reflet = pygame.Surface((rect.width - 20, 1), pygame.SRCALPHA)
    for px in range(rect.width - 20):
        ratio = px / (rect.width - 20)
        dist = abs(ratio - 0.5) * 2
        a = int(50 * (1 - dist ** 2))
        reflet.set_at((px, 0), (200, 230, 255, a))
    surface.blit(reflet, (rect.x + 10, rect.y + 8))


# ======================================================================
#  CAMÉRA
# ======================================================================

def calculer_camera(rect_cible, largeur_ecran, hauteur_ecran, zoom,
                    largeur_monde, hauteur_monde):
    largeur_vue = largeur_ecran / zoom
    hauteur_vue = hauteur_ecran / zoom
    offset_x = rect_cible.centerx - (largeur_vue / 2)
    offset_y = rect_cible.centery - (hauteur_vue / 2)
    offset_x = max(0, offset_x)
    offset_y = max(0, offset_y)
    offset_x = min(offset_x, largeur_monde - largeur_vue)
    offset_y = min(offset_y, hauteur_monde - hauteur_vue)
    return int(offset_x), int(offset_y)


# ======================================================================
#  SPLASH SCREEN
# ======================================================================

def afficher_splash_screen(ecran, duree=3000):
    """Affiche un splash screen avec le logo du jeu (70% de l'écran)."""
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)

        logo_path = os.path.join(base_path, 'favicon.png')
        logo_original = pygame.image.load(logo_path).convert_alpha()
        taille_ref = min(LARGEUR_ECRAN, HAUTEUR_ECRAN)
        cote_cible = int(taille_ref * 0.7)
        logo = pygame.transform.smoothscale(logo_original, (cote_cible, cote_cible))
        fond = pygame.Surface((LARGEUR_ECRAN, HAUTEUR_ECRAN))
        fond.fill((0, 0, 0))
        logo_rect = logo.get_rect(center=(LARGEUR_ECRAN // 2, HAUTEUR_ECRAN // 2))
        debut = pygame.time.get_ticks()
        horloge = pygame.time.Clock()
        while pygame.time.get_ticks() - debut < duree:
            temps_ecoule = pygame.time.get_ticks() - debut
            if temps_ecoule < duree * 0.3:
                alpha = int((temps_ecoule / (duree * 0.3)) * 255)
            elif temps_ecoule > duree * 0.7:
                alpha = int((1 - (temps_ecoule - duree * 0.7) / (duree * 0.3)) * 255)
            else:
                alpha = 255
            ecran.blit(fond, (0, 0))
            logo_temp = logo.copy()
            logo_temp.set_alpha(alpha)
            ecran.blit(logo_temp, logo_rect)
            pygame.display.flip()
            horloge.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    return
                if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                    envoyer_logs.envoyer_maintenant()
                    print("[LOG] Envoi manuel déclenché depuis le bouton HUD")
    except Exception as e:
        print(f"Impossible d'afficher le splash screen: {e}")


# ======================================================================
#  CLASSE CLIENT
# ======================================================================

class Client:
    def __init__(self):
        pygame.init()
        zoom = ZOOM_CAMERA
        self._surface_virtuelle = pygame.Surface((int(LARGEUR_ECRAN / zoom), int(HAUTEUR_ECRAN / zoom)))
        # Icône
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(__file__)
            icon_path = os.path.join(base_path, 'favicon.png')
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)
        except Exception as e:
            print(f"Impossible de charger l'icône: {e}")

        # Musique
        self._init_musique()

        self.parametres = gestion_parametres.charger_parametres()
        langue.set_langue(self.parametres['jouabilite']['langue'])

        self.largeur_ecran = LARGEUR_ECRAN
        self.hauteur_ecran = HAUTEUR_ECRAN
        self.appliquer_parametres_video(premiere_fois=True)
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.horloge = pygame.time.Clock()

        # Temps pour les animations
        self.temps_anim = 0

        afficher_splash_screen(self.ecran, duree=3000)

        # États
        self.etat_jeu = "MENU_PRINCIPAL"
        self.etat_jeu_precedent = "MENU_PRINCIPAL"
        self.etat_jeu_interne = "JEU"
        self.running = True

        self.client_socket = None
        self.mon_id = -1

        self.carte = None
        self.vis_map_locale = None
        self.joueurs_locaux = {}
        self.ennemis_locaux = {}
        self.ames_perdues_locales = {}
        self.ames_libres_locales = {}
        self.cle_locale = None
        self.torche = Torche(x=0, y=672)

        # Polices — tailles relatives à la hauteur d'écran
        h = self.hauteur_ecran
        #self.police_titre  = pygame.font.Font(None, max(48, h // 14))
        self.police_titre = pygame.font.Font(None, max(96, h // 7))
        self.police_bouton = pygame.font.Font(None, max(30, h // 28))
        self.police_texte  = pygame.font.Font(None, max(24, h // 36))
        self.police_petit  = pygame.font.Font(None, max(18, h // 48))

        self.parametres_temp = {}
        self.touche_a_modifier = None
        self.id_slot_a_ecraser = None
        self.scroll_y_params = 0
        self.message_erreur_connexion = None

        # Activer le presse-papiers pygame
        try:
            pygame.scrap.init()
        except Exception:
            pass  # Non critique

        self.creer_widgets_menu_principal()
        self.creer_widgets_menu_rejoindre()
        self.creer_widgets_menu_parametres()
        self.creer_widgets_menu_pause()
        self.creer_widgets_menu_slots()
        self.creer_widgets_menu_confirmation()

        self._mort_depuis = None

    # ------------------------------------------------------------------
    #  PROPRIÉTÉS DE MISE EN PAGE (tout calculé depuis la taille réelle)
    # ------------------------------------------------------------------

    @property
    def cx(self):
        return self.largeur_ecran // 2

    @property
    def cy(self):
        return self.hauteur_ecran // 2

    def _largeur_bouton(self):
        """Largeur standard des boutons principaux (max 420 px, min 260)."""
        return max(260, min(420, self.largeur_ecran // 4))

    def _hauteur_bouton(self):
        return max(40, min(56, self.hauteur_ecran // 20))

    def _espacement_bouton(self):
        return max(10, min(18, self.hauteur_ecran // 60))

    # ------------------------------------------------------------------
    #  CRÉATION DES WIDGETS
    # ------------------------------------------------------------------

    def creer_widgets_menu_principal(self):
        cx = self.cx
        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        esp = self._espacement_bouton() + bh  # pas total

        # Calcul y_start pour que le groupe de boutons soit centré verticalement
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

        # Bouton IP (utilisé dans paramètres, initialisé ici pour éviter l'AttributeError)
        self.btn_copier_ip_locale = Bouton(0, 0, 300, 36, "", self.police_petit)

    def creer_widgets_menu_rejoindre(self):
        cx = self.cx
        lw = self._largeur_bouton()
        bh = self._hauteur_bouton()
        cy = self.cy

        self.input_box_ip   = pygame.Rect(cx - lw // 2, cy - 30, lw, 46)
        self.input_ip_texte = ""
        self.input_ip_actif = False

        self.btn_connecter       = Bouton(cx - lw // 2, cy + 40, lw, bh,
                                          langue.get_texte("rejoindre_connecter"),
                                          self.police_bouton)
        self.btn_retour_rejoindre = Bouton(cx - lw // 2, cy + 40 + bh + 12, lw, bh,
                                           langue.get_texte("rejoindre_retour"),
                                           self.police_bouton, style="ghost")
        self.btn_erreur_ok = Bouton(cx - 60, cy + 90, 120, bh, "OK",
                                    self.police_bouton, style="danger")

        # Bouton "Coller" — à droite de l'input IP
        lw_coller = 90
        self.btn_coller_ip = Bouton(
            cx + lw // 2 + 10, cy - 30, lw_coller, 46,
            "📋 Coller", self.police_bouton, style="ghost"
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
        self.btn_toggle_musique      = _p()
        self.btn_changer_gauche      = _p()
        self.btn_changer_droite      = _p()
        self.btn_changer_saut        = _p()
        self.btn_changer_echo        = _p()
        self.btn_changer_attaque     = _p()
        self.btn_changer_dash        = _p()

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
            self.btn_toggle_musique,
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
        # DÉSACTIVÉ — bouton inutile pour l'instant
        # self.btn_pause_activer_multi = Bouton(cx - lw // 2, y0 + esp * 2, lw, bh,
        #                                       "Activer Multijoueur (Bientôt)",
        #                                       self.police_bouton, style="ghost")

        # Le bouton quitter remonte d'un cran (index esp * 2 au lieu de esp * 3)
        self.btn_pause_quitter      = Bouton(cx - lw // 2, y0 + esp * 2,  lw, bh,
                                             langue.get_texte("pause_quitter_session"),
                                             self.police_bouton, style="ghost")

        self.boutons_menu_pause = [
            self.btn_pause_reprendre, self.btn_pause_parametres,
            self.btn_pause_quitter
            # self.btn_pause_activer_multi retiré
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

    # ------------------------------------------------------------------
    #  BOUCLE PRINCIPALE
    # ------------------------------------------------------------------

    def lancer_application(self):
        while self.running:
            self.temps_anim = pygame.time.get_ticks()
            pos_souris = pygame.mouse.get_pos()

            if self.etat_jeu == "MENU_PRINCIPAL":
                self.gerer_menu_principal(pos_souris)
                self.dessiner_menu_principal()

            elif self.etat_jeu == "MENU_REJOINDRE":
                self.gerer_menu_rejoindre(pos_souris)
                self.dessiner_menu_rejoindre()

            elif self.etat_jeu in ("MENU_NOUVELLE_PARTIE", "MENU_CONTINUER"):
                self.gerer_menu_slots(pos_souris)
                self.dessiner_menu_slots()

            elif self.etat_jeu == "MENU_CONFIRMATION":
                self.gerer_menu_confirmation(pos_souris)
                self.dessiner_menu_confirmation()

            elif self.etat_jeu == "MENU_PARAMETRES":
                if not self.parametres_temp:
                    self.parametres_temp = copy.deepcopy(self.parametres)
                self.gerer_menu_parametres(pos_souris)
                self.dessiner_menu_parametres()

            elif self.etat_jeu == "EN_JEU":
                if self.etat_jeu_interne != "PAUSE":
                    self.etat_jeu_interne = "JEU"
                self.boucle_jeu_reseau()
                if self.etat_jeu == "MENU_PARAMETRES":
                    self.etat_jeu_precedent = "EN_JEU"
                    self.parametres_temp = copy.deepcopy(self.parametres)
                elif self.etat_jeu != "EN_JEU":
                    self.etat_jeu = "MENU_PRINCIPAL"
                    self.nettoyer_connexion()
                    self.actualiser_langues_widgets()

            elif self.etat_jeu == "QUITTER":
                self.running = False

            pygame.display.flip()
            self.horloge.tick(FPS)

        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------
    #  ACTUALISATION DES LANGUES
    # ------------------------------------------------------------------

    def actualiser_langues_widgets(self):
        langue.set_langue(self.parametres['jouabilite']['langue'])
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.btn_nouvelle_partie.texte = langue.get_texte("menu_nouvelle_partie")
        self.btn_continuer.texte       = langue.get_texte("menu_continuer")
        self.btn_rejoindre.texte       = langue.get_texte("menu_rejoindre")
        self.btn_parametres.texte      = langue.get_texte("menu_parametres")
        self.btn_quitter.texte         = langue.get_texte("menu_quitter")
        self.btn_connecter.texte       = langue.get_texte("rejoindre_connecter")
        self.btn_retour_rejoindre.texte = langue.get_texte("rejoindre_retour")
        self.btn_appliquer_params.texte = langue.get_texte("param_appliquer")
        self.btn_retour_params.texte   = langue.get_texte("param_retour")
        self.btn_pause_reprendre.texte = langue.get_texte("pause_reprendre")
        self.btn_pause_parametres.texte = langue.get_texte("pause_parametres")
        self.btn_popup_oui.texte       = langue.get_texte("popup_oui")
        self.btn_popup_non.texte       = langue.get_texte("popup_non")

    # ------------------------------------------------------------------
    #  RÉSEAU & IP
    # ------------------------------------------------------------------

    def obtenir_ip_locale(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "Non disponible"

    def obtenir_ip_hamachi(self):
        try:
            hostname = socket.gethostname()
            all_ips = socket.gethostbyname_ex(hostname)[2]
            for ip in all_ips:
                if ip.startswith("25."):
                    return ip
            return "Non connecté"
        except Exception:
            return "Non connecté"

    def copier_dans_presse_papier(self, texte):
        try:
            import subprocess
            subprocess.run(['clip'], input=texte.encode('utf-16le'), check=True)
            return True
        except Exception:
            return False

    def appliquer_parametres_video(self, premiere_fois=False):
        flags = pygame.SCALED
        if self.parametres['video']['plein_ecran']:
            flags |= pygame.FULLSCREEN
        self.ecran = pygame.display.set_mode(
            (self.largeur_ecran, self.hauteur_ecran), flags)

    # ------------------------------------------------------------------
    #  MENU PRINCIPAL
    # ------------------------------------------------------------------

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

        # Fond animé Echo
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran, t)

        # Zone titre
        cy_titre = max(80, self.hauteur_ecran // 7)
        police_grand_titre = pygame.font.Font(None, max(96, self.hauteur_ecran // 7))
        dessiner_titre_neon(self.ecran, police_grand_titre,
                            langue.get_texte("titre_jeu"),
                            self.cx, cy_titre)

        # Sous-titre
        sub = self.police_petit.render("par la Team Nightberry", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(sub, sub.get_rect(center=(self.cx, cy_titre + police_grand_titre.get_height() // 2 + 20)))

        # Séparateur
        marge = self.largeur_ecran // 6
        dessiner_separateur_neon(self.ecran,
                                 marge, cy_titre + police_grand_titre.get_height() // 2 + 50,
                                 self.largeur_ecran - marge)

        # Boutons
        for btn in self.boutons_menu_principal:
            btn.dessiner(self.ecran)

        # Version (coin bas droite)
        ver = self.police_petit.render("v1.2 — Beta", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(ver, (self.largeur_ecran - ver.get_width() - 20,
                              self.hauteur_ecran - ver.get_height() - 12))
        
        # Lien site (coin bas gauche) avec survol
        lien_texte = "https://florian-croiset.github.io/jeusite/"
        pos_souris = pygame.mouse.get_pos()
        lien_surf = self.police_petit.render(lien_texte, True, COULEUR_CYAN_SOMBRE)
        lien_rect = lien_surf.get_rect(bottomleft=(20, self.hauteur_ecran - 12))
        if lien_rect.collidepoint(pos_souris):
            lien_surf = self.police_petit.render(lien_texte, True, COULEUR_CYAN)
        self.ecran.blit(lien_surf, lien_rect)

    # ------------------------------------------------------------------
    #  MENU REJOINDRE
    # ------------------------------------------------------------------

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

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if self.btn_retour_rejoindre.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"
            if self.btn_connecter.verifier_clic(event):
                hote = self.input_ip_texte if self.input_ip_texte else "localhost"
                if self.connecter(hote):
                    self.etat_jeu = "EN_JEU"
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.input_ip_actif = self.input_box_ip.collidepoint(event.pos)
            if self.btn_coller_ip.verifier_clic(event):
                try:
                    texte_presse_papier = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if texte_presse_papier:
                        # pygame.scrap renvoie bytes avec null-terminateur sur Windows
                        ip_collee = texte_presse_papier.decode('utf-8', errors='ignore').rstrip('\x00').strip()
                        if ip_collee:
                            self.input_ip_texte = ip_collee
                            self.input_ip_actif = True
                except Exception:
                    # Fallback : essai via pyperclip ou subprocess
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['powershell', '-command', 'Get-Clipboard'],
                            capture_output=True, text=True, timeout=2
                        )
                        ip_collee = result.stdout.strip()
                        if ip_collee:
                            self.input_ip_texte = ip_collee
                    except Exception:
                        pass

            if event.type == pygame.KEYDOWN and self.input_ip_actif:
                if event.key == pygame.K_RETURN:
                    hote = self.input_ip_texte if self.input_ip_texte else "localhost"
                    if self.connecter(hote):
                        self.etat_jeu = "EN_JEU"
                elif event.key == pygame.K_BACKSPACE:
                    self.input_ip_texte = self.input_ip_texte[:-1]
                else:
                    self.input_ip_texte += event.unicode

    def dessiner_menu_rejoindre(self):
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran,
                           self.temps_anim)

        # Titre
        dessiner_titre_neon(self.ecran, self.police_titre,
                            langue.get_texte("rejoindre_titre"),
                            self.cx, self.hauteur_ecran // 7)

        # Panneau central
        pan_w = self._largeur_bouton() + 80
        pan_h = 220
        pan_rect = pygame.Rect(self.cx - pan_w // 2,
                               self.cy - pan_h // 2 - 20,
                               pan_w, pan_h)
        dessiner_panneau(self.ecran, pan_rect)

        # Label
        label = self.police_texte.render(
            langue.get_texte("rejoindre_label_ip"), True, COULEUR_TEXTE)
        self.ecran.blit(label, label.get_rect(
            center=(self.cx, pan_rect.y + 36)))

        # Input box
        bord_color = COULEUR_CYAN if self.input_ip_actif else COULEUR_CYAN_SOMBRE
        pygame.draw.rect(self.ecran, COULEUR_INPUT_BOX,
                         self.input_box_ip, border_radius=6)
        pygame.draw.rect(self.ecran, bord_color,
                         self.input_box_ip, width=1, border_radius=6)

        ip_surf = self.police_texte.render(self.input_ip_texte, True, COULEUR_TEXTE)
        self.ecran.blit(ip_surf, (self.input_box_ip.x + 12,
                                  self.input_box_ip.y + 10))

        # Curseur clignotant
        if self.input_ip_actif and int(time.time() * 2) % 2 == 0:
            cx_cur = self.input_box_ip.x + 14 + ip_surf.get_width()
            cy_cur = self.input_box_ip.y + 8
            pygame.draw.rect(self.ecran, COULEUR_CYAN,
                             pygame.Rect(cx_cur, cy_cur, 2,
                                         self.police_texte.get_height() - 6))

        self.btn_coller_ip.dessiner(self.ecran)
        self.btn_connecter.dessiner(self.ecran)
        self.btn_retour_rejoindre.dessiner(self.ecran)

        # Popup erreur
        if self.message_erreur_connexion:
            self._dessiner_popup_erreur()

    def _dessiner_popup_erreur(self):
        """Affiche une popup d'erreur de connexion par-dessus le menu rejoindre."""
        cx, cy = self.cx, self.cy
        w_popup = max(440, min(600, self.largeur_ecran // 3))
        h_popup = max(200, min(260, self.hauteur_ecran // 4))
        rect_popup = pygame.Rect(cx - w_popup // 2, cy - h_popup // 2,
                                w_popup, h_popup)

        # Fond semi-transparent sombre
        overlay = pygame.Surface((self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.ecran.blit(overlay, (0, 0))

        # Panneau
        dessiner_panneau(self.ecran, rect_popup, couleur_bordure=(220, 50, 50))

        # Titre
        titre_surf = self.police_texte.render("Erreur de connexion", True, (220, 50, 50))
        self.ecran.blit(titre_surf, titre_surf.get_rect(
            center=(cx, rect_popup.y + 36)))

        # Séparateur
        dessiner_separateur_neon(self.ecran,
                                rect_popup.x + 20, rect_popup.y + 58,
                                rect_popup.right - 20, couleur=(220, 50, 50))

        # Message (peut contenir \n)
        police_msg = self.police_petit
        lignes = self.message_erreur_connexion.split('\n')
        for i, ligne in enumerate(lignes):
            s = police_msg.render(ligne, True, COULEUR_TEXTE)
            self.ecran.blit(s, s.get_rect(center=(cx, rect_popup.y + 90 + i * 26)))

        # Bouton OK
        self.btn_erreur_ok.rect.center = (cx, rect_popup.bottom - 36)
        self.btn_erreur_ok.dessiner(self.ecran)

    def _dessiner_ecran_mort(self, surface):
        if not hasattr(self, '_mort_depuis') or self._mort_depuis is None:
            self._mort_depuis = pygame.time.get_ticks()

        elapsed = pygame.time.get_ticks() - self._mort_depuis
        alpha = min(200, int(200 * min(elapsed, 800) / 800))  # monte sur 0.8s puis reste stable

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((80, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

        # Texte visible dès 600ms
        if elapsed > 600:
            police_mort = pygame.font.Font(None, 48)
            police_sub  = pygame.font.Font(None, 28)
            lw, lh = surface.get_size()
            txt1 = police_mort.render("VOUS ETES MORT", True, (220, 50, 50))
            txt2 = police_sub.render("Respawn en cours...", True, (160, 100, 100))
            surface.blit(txt1, txt1.get_rect(center=(lw // 2, lh // 2 - 20)))
            surface.blit(txt2, txt2.get_rect(center=(lw // 2, lh // 2 + 20)))

    # ------------------------------------------------------------------
    #  MENU SLOTS
    # ------------------------------------------------------------------

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

            # Description en dessous du bouton
            desc_c = COULEUR_TEXTE_SOMBRE if (mode_continuer and est_vide) else COULEUR_TEXTE
            desc = self.police_petit.render(info["description"], True, desc_c)
            self.ecran.blit(desc, desc.get_rect(
                center=(btn_slot.rect.centerx,
                        btn_slot.rect.bottom + 14)))

        self.btn_retour_slots.dessiner(self.ecran)

    # ------------------------------------------------------------------
    #  MENU CONFIRMATION (popup écraser sauvegarde)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    #  MENU PARAMÈTRES
    # ------------------------------------------------------------------

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
                    self.actualiser_langues_widgets()
                    self.touche_a_modifier = None
                    self.scroll_y_params = 0
                    self.etat_jeu = self.etat_jeu_precedent

                if self.btn_toggle_plein_ecran.verifier_clic(event):
                    self.parametres_temp['video']['plein_ecran'] = \
                        not self.parametres_temp['video']['plein_ecran']

                if self.btn_toggle_musique.verifier_clic(event):
                    nouvelle_val = not self.parametres_temp['video'].get('musique', True)
                    self.parametres_temp['video']['musique'] = nouvelle_val
                    # Appliquer immédiatement
                    if self._musique_ok:
                        if nouvelle_val:
                            if not self._musique_jouee:
                                pygame.mixer.music.play(-1)
                                self._musique_jouee = True
                            else:
                                pygame.mixer.music.unpause()
                        else:
                            pygame.mixer.music.pause()

                if self.btn_changer_langue.verifier_clic(event):
                    langues = ['fr', 'en']
                    actuelle = self.parametres_temp['jouabilite']['langue']
                    try:
                        idx = langues.index(actuelle)
                        nouvelle = langues[(idx + 1) % len(langues)]
                    except ValueError:
                        nouvelle = 'fr'
                    self.parametres_temp['jouabilite']['langue'] = nouvelle

                if self.btn_changer_gauche.verifier_clic(event):   self.touche_a_modifier = "gauche"
                if self.btn_changer_droite.verifier_clic(event):   self.touche_a_modifier = "droite"
                if self.btn_changer_saut.verifier_clic(event):     self.touche_a_modifier = "saut"
                if self.btn_changer_echo.verifier_clic(event):     self.touche_a_modifier = "echo"
                if self.btn_changer_attaque.verifier_clic(event):  self.touche_a_modifier = "attaque"
                if self.btn_changer_dash.verifier_clic(event):     self.touche_a_modifier = "dash"

                if self.btn_copier_ip_locale.verifier_clic(event):
                    ip = self.obtenir_ip_locale()
                    self.copier_dans_presse_papier(ip)
                if self.btn_copier_ip_hamachi.verifier_clic(event):
                    ip = self.obtenir_ip_hamachi()
                    if ip != "Non connecté":
                        self.copier_dans_presse_papier(ip)

        # Survol
        for btn in self.boutons_menu_params_fixes + self.boutons_menu_params_scrollables:
            btn.verifier_survol(pos_souris)

    def dessiner_menu_parametres(self):
        dessiner_fond_echo(self.ecran, self.largeur_ecran, self.hauteur_ecran,
                           self.temps_anim)

        # Titre fixe — police normale (pas le grand titre du menu principal)
        police_titre_params = pygame.font.Font(None, max(48, self.hauteur_ecran // 14))
        dessiner_titre_neon(self.ecran, police_titre_params,
                            langue.get_texte("param_titre"),
                            self.cx, self.hauteur_ecran // 14)

        # Zone de contenu scrollable
        y = int(self.hauteur_ecran * 0.12) + self.scroll_y_params
        params = self.parametres_temp if self.parametres_temp else self.parametres
        col_droite = self.cx + 60
        col_gauche = 100
        esp_ligne = max(44, self.hauteur_ecran // 22)

        def section(titre_texte):
            nonlocal y
            dessiner_separateur_neon(self.ecran, col_gauche, y,
                                     self.largeur_ecran - col_gauche,
                                     alpha=100)
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

        # ---- Jouabilité ----
        section(langue.get_texte("param_section_jouabilite"))
        # Langue
        lbl_lng = self.police_texte.render(langue.get_texte("param_langue"), True, COULEUR_TEXTE)
        self.ecran.blit(lbl_lng, (col_gauche + 20, y + 6))
        self.btn_changer_langue.rect.y = y
        self.btn_changer_langue.texte = params['jouabilite']['langue'].upper()
        self.btn_changer_langue.dessiner(self.ecran)
        y += esp_ligne

        # ---- Vidéo ----
        section(langue.get_texte("param_section_video"))
        ligne_toggle(langue.get_texte("param_plein_ecran"),
                     params['video']['plein_ecran'],
                     self.btn_toggle_plein_ecran,
                     langue.get_texte("param_oui"),
                     langue.get_texte("param_non"))
        ligne_toggle("Musique",
                     params['video'].get('musique', True),
                     self.btn_toggle_musique,
                     langue.get_texte("param_oui"),
                     langue.get_texte("param_non"))

        # ---- Contrôles ----
        section(langue.get_texte("param_section_controles"))
        ligne_controle(langue.get_texte("param_gauche"),   'gauche',  self.btn_changer_gauche)
        ligne_controle(langue.get_texte("param_droite"),   'droite',  self.btn_changer_droite)
        ligne_controle(langue.get_texte("param_saut"),     'saut',    self.btn_changer_saut)
        ligne_controle(langue.get_texte("param_echo"),     'echo',    self.btn_changer_echo)
        ligne_controle(langue.get_texte("param_attaque"),  'attaque', self.btn_changer_attaque)
        ligne_controle(langue.get_texte("param_dash"),     'dash',    self.btn_changer_dash)

        # ---- Réseau ----
        section(langue.get_texte("param_section_reseau"))
        ligne_ip("IP Locale (LAN) :",
                 f"{self.obtenir_ip_locale()}   (copier)",
                 self.btn_copier_ip_locale)
        ligne_ip("IP Hamachi (VPN) :",
                 f"{self.obtenir_ip_hamachi()}   (copier)",
                 self.btn_copier_ip_hamachi)

        aide = self.police_petit.render(
            "Cliquez pour copier dans le presse-papiers", True, COULEUR_TEXTE_SOMBRE)
        self.ecran.blit(aide, (col_gauche + 20, y))

        # Boutons fixes
        self.btn_appliquer_params.dessiner(self.ecran)
        self.btn_retour_params.dessiner(self.ecran)

    # ------------------------------------------------------------------
    #  MENU PAUSE
    # ------------------------------------------------------------------

    def dessiner_menu_pause(self):
        self.ecran.blit(self.surface_fond_pause, (0, 0))

        dessiner_titre_neon(self.ecran, self.police_titre,
                            langue.get_texte("pause_titre"),
                            self.cx,
                            self.cy - int(self.hauteur_ecran * 0.22))

        est_hote = (self.mon_id == 0)
        #if est_hote:
        #    est_multi = len(self.joueurs_locaux) > 1
        #    self.btn_pause_quitter.texte = langue.get_texte(
        #        "pause_terminer_session" if est_multi else "pause_quitter_session")
        #else:
        #    self.btn_pause_quitter.texte = langue.get_texte("pause_quitter_session")      

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
                self._reprendre_musique()
            if self.btn_pause_reprendre.verifier_clic(event):
                self.etat_jeu_interne = "JEU"
                self._reprendre_musique()
            if self.btn_pause_parametres.verifier_clic(event):
                self.etat_jeu_precedent = "EN_JEU"
                self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu = "MENU_PARAMETRES"
            if self.btn_pause_quitter.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"

    # ------------------------------------------------------------------
    #  MUSIQUE
    # ------------------------------------------------------------------

    def _init_musique(self):
        """Initialise le mixer et charge musique.mp3."""
        try:
            import os, sys
            if getattr(sys, 'frozen', False):
                base = sys._MEIPASS
            else:
                base = os.path.dirname(__file__)
            chemin = os.path.join(base, 'musique.mp3')
            pygame.mixer.init()
            pygame.mixer.music.load(chemin)
            pygame.mixer.music.set_volume(0.5)
            self._musique_ok = True
        except Exception as e:
            print(f'[MUSIQUE] Impossible de charger musique.mp3 : {e}')
            self._musique_ok = False
        self._musique_jouee = False

    def _demarrer_musique(self):
        """Lance la musique si activée dans les paramètres."""
        musique_activee = self.parametres.get('video', {}).get('musique', True)
        if self._musique_ok and not self._musique_jouee and musique_activee:
            pygame.mixer.music.play(-1)  # -1 = boucle infinie
            self._musique_jouee = True

    def _pause_musique(self):
        if self._musique_ok and self._musique_jouee:
            pygame.mixer.music.pause()

    def _reprendre_musique(self):
        if self._musique_ok and self._musique_jouee:
            pygame.mixer.music.unpause()

    def _dessiner_icone_cle(self, x, y):
        """Dessine l'icône de clé dans le HUD avec texte."""
        import os, sys
        # Essayer de charger le sprite cle
        if not hasattr(self, '_sprite_cle_hud'):
            try:
                if getattr(sys, 'frozen', False):
                    base = sys._MEIPASS
                else:
                    base = os.path.dirname(__file__)
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
            # Fallback : carré doré
            pygame.draw.rect(self.ecran, (255, 215, 0), pygame.Rect(x, y, 14, 14), border_radius=3)
            lbl = self.police_texte.render("  Clé", True, (255, 215, 0))
            self.ecran.blit(lbl, (x + 16, y))

    # ------------------------------------------------------------------
    #  HUD EN JEU
    # ------------------------------------------------------------------

    def dessiner_hud(self):
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur:
            return

        pv     = mon_joueur.pv
        pv_max = mon_joueur.pv_max

        # Barres de vie style Echo (cyan)
        largeur_coeur = max(24, self.largeur_ecran // 60)
        hauteur_coeur = max(20, self.hauteur_ecran // 45)
        padding = 6
        x0 = 24
        y0 = 24

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

        # Argent / âmes
        argent_txt = self.police_texte.render(
            f"Âmes : {mon_joueur.argent}", True, COULEUR_VIOLET_CLAIR)
        self.ecran.blit(argent_txt, (x0, y0 + hauteur_coeur + 10))

        # Inventaire : clé
        if hasattr(mon_joueur, 'have_key') and mon_joueur.have_key:
            y_inv = y0 + hauteur_coeur + 36
            self._dessiner_icone_cle(x0, y_inv)

        # -- Compteur debug (MODE_DEV) --
        # -- Compteur debug (MODE_DEV) --
        if MODE_DEV:
            self._dessiner_debug_hud()
            #btn = envoyer_logs.get_bouton()
            #btn.rect.topleft = (10, 40)   # à côté du compteur FPS
            #btn.dessiner(surface)

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

        police = self.police_petit
        ligne_h = police.get_height() + 4
        padding = 8
        largeur_panel = 160
        hauteur_panel = len(lignes) * ligne_h + padding * 2

        x0 = self.largeur_ecran - largeur_panel - 12
        y0 = 12

        panel = pygame.Surface((largeur_panel, hauteur_panel), pygame.SRCALPHA)
        panel.fill((8, 8, 20, 180))
        pygame.draw.rect(panel, COULEUR_CYAN_SOMBRE,
                         pygame.Rect(0, 0, largeur_panel, hauteur_panel),
                         width=1, border_radius=6)
        self.ecran.blit(panel, (x0, y0))

        #dev_txt = self.police_petit.render("DEV", True, COULEUR_CYAN)
        #self.ecran.blit(dev_txt, (x0 + padding, y0 + 2))

        for i, (texte, couleur) in enumerate(lignes):
            surf = police.render(texte, True, couleur)
            self.ecran.blit(surf, (x0 + padding, y0 + padding + i * ligne_h))

    def _dessiner_ecran_mort(self, surface):
        """Overlay de mort semi-transparent avec message."""
        if self._mort_depuis is None:
            self._mort_depuis = pygame.time.get_ticks()

        elapsed = pygame.time.get_ticks() - self._mort_depuis
        alpha = min(200, int(200 * min(elapsed, 800) / 800))

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((80, 0, 0, alpha))
        surface.blit(overlay, (0, 0))

        if elapsed > 600:
            police_mort = pygame.font.Font(None, 48)
            police_sub  = pygame.font.Font(None, 28)
            lw, lh = surface.get_size()
            txt1 = police_mort.render("VOUS ETES MORT", True, (220, 50, 50))
            txt2 = police_sub.render("Respawn en cours...", True, (160, 100, 100))
            surface.blit(txt1, txt1.get_rect(center=(lw // 2, lh // 2 - 20)))
            surface.blit(txt2, txt2.get_rect(center=(lw // 2, lh // 2 + 20)))

    # ------------------------------------------------------------------
    #  BOUCLE JEU RÉSEAU
    # ------------------------------------------------------------------

    def gerer_evenements_jeu(self):
        commandes = {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False, 'dash': False},
                     'echo': False, 'toggle_torche': False,}
        params_ctrl = self.parametres.get('controles', {})

        def key(nom):
            k = params_ctrl.get(nom, '')
            try:
                return pygame.key.key_code(k)
            except Exception:
                return None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                print("[LOG] Clic bouton detecte : envoi en cours...")
                envoyer_logs.envoyer_maintenant()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.etat_jeu_interne = "PAUSE"
                    self._pause_musique()
                if event.key == key('attaque'):
                    commandes['clavier']['attaque'] = True
                if event.key == key('echo'):
                    commandes['echo'] = True
                if event.key == key('dash'):
                    commandes['clavier']['dash'] = True
                if event.key == pygame.K_l:
                    if self.mon_id not in self.joueurs_locaux:
                        continue
                    joueur = self.joueurs_locaux[self.mon_id]
                    vient_dallumer = self.torche.toggle()
                    commandes['toggle_torche'] = True  # envoyé au serveur (ON et OFF)
                    if vient_dallumer:
                        dx = joueur.rect.centerx - self.torche.x
                        dy = joueur.rect.centery - self.torche.y
                        if (dx**2 + dy**2)**0.5 <= DISTANCE_TORCHE_ECHO:
                            commandes['echo'] = True

        touches = pygame.key.get_pressed()
        if key('gauche')  and touches[key('gauche')]:
            commandes['clavier']['gauche'] = True
        if key('droite')  and touches[key('droite')]:
            commandes['clavier']['droite'] = True
        if key('saut')    and touches[key('saut')]:
            commandes['clavier']['saut'] = True

        return commandes

    def dessiner_jeu(self):
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur or not self.carte or not self.vis_map_locale:
            self.ecran.fill(COULEUR_FOND)
            return

        zoom = ZOOM_CAMERA
        lv = int(self.largeur_ecran / zoom)
        hv = int(self.hauteur_ecran / zoom)
        surface_virtuelle = self._surface_virtuelle
        surface_virtuelle.fill(COULEUR_FOND)
        lm = self.carte.largeur_map * TAILLE_TUILE
        hm = self.carte.hauteur_map * TAILLE_TUILE
        camera_offset = calculer_camera(mon_joueur.rect,
                                        self.largeur_ecran, self.hauteur_ecran,
                                        zoom, lm, hm)

        self.carte.dessiner_carte(surface_virtuelle, self.vis_map_locale, camera_offset)

        '''for joueur in self.joueurs_locaux.values():
            try:
                joueur.dessiner(surface_virtuelle, camera_offset)
            except TypeError:
                joueur.dessiner(surface_virtuelle)'''
        
        for joueur in self.joueurs_locaux.values():
            joueur.dessiner(surface_virtuelle, camera_offset)

        temps_ms = pygame.time.get_ticks()

        for ennemi in self.ennemis_locaux.values():
            if mon_joueur:
                dx = ennemi.rect.centerx - mon_joueur.rect.centerx
                dy = ennemi.rect.centery - mon_joueur.rect.centery
                dist = (dx**2 + dy**2) ** 0.5
            else:
                dist = 9999
                temps_depuis_flash = 9999
                flash_actif = False
                proche = False

            temps_depuis_flash = temps_ms - getattr(ennemi, 'flash_echo_temps', 0)
            flash_actif = temps_depuis_flash < DUREE_FLASH_ECHO_ENNEMI
            proche = dist <= DISTANCE_DETECTION_ENNEMI

            if proche:
                ennemi.dessiner(surface_virtuelle, camera_offset)
            elif flash_actif:
                ratio = 1.0 - (temps_depuis_flash / DUREE_FLASH_ECHO_ENNEMI)
                off_x, off_y = camera_offset
                cx = ennemi.rect.centerx - off_x
                cy = ennemi.rect.centery - off_y
                halo = pygame.Surface((60, 60), pygame.SRCALPHA)
                pygame.draw.circle(halo, (0, 212, 255, int(80 * ratio)), (30, 30), 30)
                surface_virtuelle.blit(halo, (cx - 30, cy - 30))
                tmp = pygame.Surface((ennemi.rect.w, ennemi.rect.h), pygame.SRCALPHA)
                tmp.fill((0, 212, 255, int(255 * ratio)))
                surface_virtuelle.blit(tmp, (ennemi.rect.x - off_x, ennemi.rect.y - off_y))

        # Reset timer de mort quand vivant
        if mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        for ame in self.ames_perdues_locales.values():
            ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # Âmes libres (cristaux turquoise)
        for ame in self.ames_libres_locales.values():
            ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # Clé
        if self.cle_locale and not self.cle_locale.est_ramassee:
            self.cle_locale.dessiner(surface_virtuelle, camera_offset, temps_ms)

        self.torche.mettre_a_jour(temps_ms)
        self.torche.dessiner(surface_virtuelle, camera_offset, temps_ms)


        # -- Calque obscurité avec halo dégradé --
        if mon_joueur:
            obscurite = pygame.Surface(surface_virtuelle.get_size(), pygame.SRCALPHA)
            obscurite.fill((0, 0, 10, 220))

            cx = mon_joueur.rect.centerx - camera_offset[0]
            cy = mon_joueur.rect.centery - camera_offset[1]
            rayon = RAYON_HALO_JOUEUR
            nb_couches = 32
            for i in range(nb_couches, 0, -1):
                r_couche = int(rayon * i / nb_couches)
                alpha = int(220 * (1 - (i / nb_couches) ** 0.5))
                pygame.draw.circle(obscurite, (0, 0, 10, alpha), (cx, cy), r_couche)

            if self.torche.allumee:
                tx = self.torche.x + TAILLE_TUILE // 2 - camera_offset[0]
                ty = self.torche.y + TAILLE_TUILE - camera_offset[1]
                rayon_t = RAYON_LUMIERE_TORCHE
                for i in range(nb_couches, 0, -1):
                    r_couche = int(rayon_t * i / nb_couches)
                    alpha = int(220 * (1 - (i / nb_couches) ** 0.6))
                    pygame.draw.circle(obscurite, (0, 0, 10, alpha), (tx, ty), r_couche)

            surface_virtuelle.blit(obscurite, (0, 0))

        if mon_joueur and mon_joueur.pv <= 0:
            self._dessiner_ecran_mort(surface_virtuelle)
        elif mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None  # reset seulement si vivant ET on ne dessine pas la mort

        surface_zoomee = pygame.transform.scale(
            surface_virtuelle, (self.largeur_ecran, self.hauteur_ecran))
        self.ecran.blit(surface_zoomee, (0, 0))

        if MODE_DEV:
            btn = envoyer_logs.get_bouton()
            btn.rect.topleft = (self.largeur_ecran - 175, 140)
            btn.verifier_survol(pygame.mouse.get_pos())
            btn.dessiner(self.ecran)

        self.dessiner_hud()

    def _recvall(self, sock, n):
        """Lit exactement n octets (TCP peut fragmenter les paquets)."""
        data = b""
        while len(data) < n:
            paquet = sock.recv(n - len(data))
            if not paquet:
                raise EOFError("Connexion fermée par le serveur")
            data += paquet
        return data

    def _recv_complet(self, sock):
        """Reçoit un paquet complet : 4 octets taille + payload pickle."""
        header = self._recvall(sock, 4)
        taille = int.from_bytes(header, 'big')
        if taille > 10_000_000:  # sécurité : max 10 MB
            raise ValueError(f"Paquet suspect trop grand : {taille} octets")
        return pickle.loads(self._recvall(sock, taille))

    def _send_complet(self, sock, obj):
        """Envoie un objet pickle précédé de 4 octets de taille."""
        data = pickle.dumps(obj)
        sock.sendall(len(data).to_bytes(4, 'big') + data)


    def boucle_jeu_reseau(self):
        if not self.client_socket:
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        self._demarrer_musique()

        while self.etat_jeu == "EN_JEU" and self.running:
            pos_souris = pygame.mouse.get_pos()
            commandes_a_envoyer = {
                'clavier': {'gauche': False, 'droite': False,
                            'saut': False, 'attaque': False, 'dash': False},
                'echo': False
            }

            if self.etat_jeu_interne == "JEU":
                commandes_a_envoyer = self.gerer_evenements_jeu()
            elif self.etat_jeu_interne == "PAUSE":
                self.gerer_evenements_pause(pos_souris)

            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            try:
                self._send_complet(self.client_socket, commandes_a_envoyer)
                donnees_recues = self._recv_complet(self.client_socket)

                # Delta vis_map : le serveur n'envoie une vis_map que si elle a changé
                if donnees_recues.get('vis_map') is not None:
                    self.vis_map_locale = donnees_recues['vis_map']

                ids_serveur = {j['id'] for j in donnees_recues['joueurs']}
                for id_local in list(self.joueurs_locaux.keys()):
                    if id_local not in ids_serveur:
                        del self.joueurs_locaux[id_local]
                for dj in donnees_recues['joueurs']:
                    if dj['id'] not in self.joueurs_locaux:
                        self.joueurs_locaux[dj['id']] = Joueur(dj['x'], dj['y'], dj['id'])
                    self.joueurs_locaux[dj['id']].set_etat(dj)

                ids_e = {e['id'] for e in donnees_recues['ennemis']}
                for id_local in list(self.ennemis_locaux.keys()):
                    if id_local not in ids_e:
                        del self.ennemis_locaux[id_local]
                for de in donnees_recues['ennemis']:
                    if de['id'] not in self.ennemis_locaux:
                        self.ennemis_locaux[de['id']] = Ennemi(de['x'], de['y'], de['id'])
                    self.ennemis_locaux[de['id']].set_etat(de)

                ids_a = {a['id'] for a in donnees_recues.get('ames_perdues', [])}
                for id_local in list(self.ames_perdues_locales.keys()):
                    if id_local not in ids_a:
                        del self.ames_perdues_locales[id_local]
                for da in donnees_recues.get('ames_perdues', []):
                    if da['id'] not in self.ames_perdues_locales:
                        self.ames_perdues_locales[da['id']] = AmePerdue(
                            da['x'], da['y'], da['id_joueur'])
                    self.ames_perdues_locales[da['id']].set_etat(da)

                # Âmes libres
                ids_al = {a['id'] for a in donnees_recues.get('ames_libres', [])}
                for id_local in list(self.ames_libres_locales.keys()):
                    if id_local not in ids_al:
                        del self.ames_libres_locales[id_local]
                for dal in donnees_recues.get('ames_libres', []):
                    if dal['id'] not in self.ames_libres_locales:
                        self.ames_libres_locales[dal['id']] = AmeLibre(dal['x'], dal['y'], dal.get('valeur'))
                    self.ames_libres_locales[dal['id']].set_etat(dal)

                # Clé
                data_cle = donnees_recues.get('cle')
                if data_cle:
                    if self.cle_locale is None:
                        self.cle_locale = Cle(data_cle['x'], data_cle['y'])
                    self.cle_locale.set_etat(data_cle)

                torche_serveur = donnees_recues.get('torche_allumee', False)
                if torche_serveur != self.torche.allumee:
                    self.torche.allumee = torche_serveur
                    if torche_serveur:
                        self.torche.particules = []

                self.dessiner_jeu()
                if self.etat_jeu_interne == "PAUSE":
                    self.dessiner_menu_pause()

            except EOFError as e:
                print(f"[CLIENT] Serveur deconnecte: {e}")
                self.message_erreur_connexion = "Le serveur s'est deconnecte."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break
            except socket.timeout:
                print("[CLIENT] Timeout réseau — serveur ne répond plus")
                self.message_erreur_connexion = "Connexion perdue (timeout)."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break
            except (socket.error, OSError) as e:
                print(f"[CLIENT] Erreur socket: {e}")
                self.message_erreur_connexion = "Connexion perdue."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break
            except (pickle.UnpicklingError, ValueError) as e:
                print(f"[CLIENT] Paquet corrompu ignoré: {e}")
                # On continue — un seul paquet corrompu ne doit pas crasher

            pygame.display.flip()
            self.horloge.tick(FPS)

    # ------------------------------------------------------------------
    #  LANCEMENT ET CONNEXION
    # ------------------------------------------------------------------

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement = "nouvelle" if est_nouvelle_partie else "charger"
        print(f"[CLIENT] Demarrage serveur local (slot {id_slot}, {type_lancement})")
        thread_serveur = threading.Thread(
            target=serveur.main,
            args=(id_slot, type_lancement),
            daemon=True
        )
        thread_serveur.start()
        # Attente active : retry jusqu'à 3s au lieu d'un sleep fixe
        connecte = False
        for _ in range(6):
            time.sleep(0.5)
            connecte = self.connecter("localhost")
            if connecte:
                break
        if connecte:
            self.etat_jeu = "EN_JEU"
        else:
            print("[CLIENT] Échec connexion serveur")
            self.etat_jeu = "MENU_PRINCIPAL"

    def connecter(self, hote):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)   # 5 secondes max pour se connecter
            print(f"[CLIENT] Connexion a {hote}:{PORT_SERVEUR}...")
            self.client_socket.connect((hote, PORT_SERVEUR))
            self.client_socket.settimeout(10.0)  # timeout 10s : détecte serveur mort
            reponse = self._recv_complet(self.client_socket)

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs connectés)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = reponse
            self.message_erreur_connexion = None

            import os
            dossier_script = os.path.dirname(os.path.abspath(__file__))
            chemin_map = os.path.join(dossier_script, "map.json")
            self.carte = Carte(chemin_map)
            self.vis_map_locale = self.carte.creer_carte_visibilite_vierge()
            self.joueurs_locaux      = {}
            self.ennemis_locaux      = {}
            self.ames_perdues_locales = {}
            self.ames_libres_locales  = {}
            self.cle_locale           = None
            return True

        except socket.error as e:
            print(f"[CLIENT] Echec connexion: {e}")
            self.message_erreur_connexion = (
                f"Impossible de se connecter\nau serveur : {hote}")
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        self.client_socket = None
        self.mon_id = -1
        self.joueurs_locaux       = {}
        self.ennemis_locaux       = {}
        self.ames_perdues_locales = {}
        self.ames_libres_locales  = {}
        self.cle_locale           = None
        self.carte = None
        self.vis_map_locale = None
        self.etat_jeu_interne = "JEU"


# ======================================================================
#  POINT D'ENTRÉE
# ======================================================================

if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()