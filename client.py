# client.py
# Classe Client — point d'entrée du jeu côté client.
# Hérite de 3 mixins pour séparer les responsabilités :
#   - MenusMixin     (ui/menus.py)    : tous les menus
#   - HudMixin       (ui/hud.py)      : HUD en jeu (vie, boss, mort, debug)
#   - BoucleJeuMixin (boucle_jeu.py)  : boucle réseau, rendu monde, connexion

from parametres import *
from utils import envoyer_logs
if MODE_DEV:
    envoyer_logs.activer_capture()

import pygame
import sys
import os

from parametres import *
from core.torche import Torche
from sauvegarde import gestion_parametres
from utils import langue, music
from ui.camera import creer_masque_halo
from ui.splash_screen import afficher_splash_screen

# Mixins
from ui.menus import MenusMixin
from ui.hud import HudMixin
from boucle_jeu import BoucleJeuMixin


class Client(MenusMixin, HudMixin, BoucleJeuMixin):
    """Classe principale du client de jeu Écho."""

    def __init__(self):
        pygame.init()

        # Paramètres et langue (chargés tôt pour connaître l'écran cible)
        self.parametres = gestion_parametres.charger_parametres()
        langue.set_langue(self.parametres['jouabilite']['langue'])
        music.init(self.parametres)

        # Résolution native de l'écran cible (selon display_index)
        try:
            self._desktop_sizes = pygame.display.get_desktop_sizes()
        except Exception:
            _info = pygame.display.Info()
            self._desktop_sizes = [(_info.current_w, _info.current_h)]
        idx = self.parametres['video'].get('display_index', 0)
        if idx < 0 or idx >= len(self._desktop_sizes):
            idx = 0
            self.parametres['video']['display_index'] = 0
        self.resolution_native = self._desktop_sizes[idx]

        # Précalcul des masques de halo
        self._masque_halo_joueur = creer_masque_halo(RAYON_HALO_JOUEUR, HALO_DEGRADE_ETENDUE)
        self._masque_halo_torche = creer_masque_halo(RAYON_LUMIERE_TORCHE, HALO_DEGRADE_ETENDUE)
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

        # Écran — la résolution et le zoom effectif sont calculés par appliquer_parametres_video
        self.largeur_ecran = LARGEUR_ECRAN
        self.hauteur_ecran = HAUTEUR_ECRAN
        self.zoom_effectif = ZOOM_CAMERA
        self.appliquer_parametres_video(premiere_fois=True)
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.horloge = pygame.time.Clock()

        # Temps animations
        self.temps_anim = 0

        # Splash screen
        afficher_splash_screen(self.ecran, duree=3000)

        # Machine à états
        self.etat_jeu = "MENU_PRINCIPAL"
        self.etat_jeu_precedent = "MENU_PRINCIPAL"
        self.etat_jeu_interne = "JEU"
        self.running = True

        # Réseau
        self.client_socket = None
        self.mon_id = -1
        self.code_room = None
        self._serveur_instance = None

        # Données de jeu
        self.carte = None
        self.vis_map_locale = None
        self.joueurs_locaux = {}
        self.ennemis_locaux = {}
        self.ames_perdues_locales = {}
        self.ames_libres_locales = {}
        self.cle_locale = None
        self.torche = Torche(x=551, y=1025)
        self.boss_local = None
        self._porte_etait_en_ouverture = False
        self._boss_etat_precedent = None

        # Polices
        h = self.hauteur_ecran
        self.police_titre = pygame.font.Font(None, max(96, h // 7))
        self.police_bouton = pygame.font.Font(None, max(30, h // 28))
        self.police_texte  = pygame.font.Font(None, max(24, h // 36))
        self.police_petit  = pygame.font.Font(None, max(18, h // 48))

        # État temporaire menus
        self.parametres_temp = {}
        self.touche_a_modifier = None
        self.id_slot_a_ecraser = None
        self.scroll_y_params = 0
        self.message_erreur_connexion = None

        # Presse-papiers
        try:
            pygame.scrap.init()
        except Exception:
            pass

        # Créer tous les widgets des menus
        self.creer_widgets_menu_principal()
        self.creer_widgets_menu_rejoindre()
        self.creer_widgets_menu_parametres()
        self.creer_widgets_menu_luminosite()
        self.creer_widgets_menu_pause()
        self.creer_widgets_menu_slots()
        self.creer_widgets_menu_confirmation()

        self._mort_depuis = None
        self._codes_touches = {}
        self._recalculer_codes_touches()

    # ------------------------------------------------------------------
    #  CONTRÔLES
    # ------------------------------------------------------------------

    def _recalculer_codes_touches(self):
        ctrl = self.parametres.get('controles', {})
        self._codes_touches = {}
        self._codes_souris  = {}
        for nom, val in ctrl.items():
            if isinstance(val, str) and val.startswith("mouse_"):
                try:
                    self._codes_souris[nom] = int(val.split("_")[1])
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    self._codes_touches[nom] = pygame.key.key_code(val)
                except Exception:
                    self._codes_touches[nom] = None

    # ------------------------------------------------------------------
    #  PROPRIÉTÉS DE MISE EN PAGE
    # ------------------------------------------------------------------

    @property
    def cx(self):
        return self.largeur_ecran // 2

    @property
    def cy(self):
        return self.hauteur_ecran // 2

    def _largeur_bouton(self):
        return max(260, min(420, self.largeur_ecran // 4))

    def _hauteur_bouton(self):
        return max(40, min(56, self.hauteur_ecran // 20))

    def _espacement_bouton(self):
        return max(10, min(18, self.hauteur_ecran // 60))

    # ------------------------------------------------------------------
    #  UTILITAIRES
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
        if hasattr(self, 'btn_appliquer_luminosite'):
            self.btn_appliquer_luminosite.texte = langue.get_texte("param_appliquer")
            self.btn_retour_luminosite.texte    = langue.get_texte("param_retour")
        self.btn_pause_reprendre.texte = langue.get_texte("pause_reprendre")
        self.btn_pause_parametres.texte = langue.get_texte("pause_parametres")
        self.btn_popup_oui.texte       = langue.get_texte("popup_oui")
        self.btn_popup_non.texte       = langue.get_texte("popup_non")

    def copier_dans_presse_papier(self, texte):
        try:
            import subprocess
            subprocess.run(['clip'], input=texte.encode('utf-16le'), check=True)
            return True
        except Exception:
            return False

    def appliquer_parametres_video(self, premiere_fois=False):
        idx = self.parametres['video'].get('display_index', 0)
        if idx < 0 or idx >= len(getattr(self, '_desktop_sizes', [(0, 0)])):
            idx = 0
            self.parametres['video']['display_index'] = 0
        self.resolution_native = self._desktop_sizes[idx]

        if self.parametres['video']['plein_ecran']:
            new_w, new_h = self.resolution_native
            flags = pygame.SCALED | pygame.FULLSCREEN
        else:
            res = self.parametres['video'].get('resolution', [LARGEUR_ECRAN, HAUTEUR_ECRAN])
            new_w, new_h = res[0], res[1]
            flags = pygame.SCALED

        self.zoom_effectif = ZOOM_CAMERA * (new_w / LARGEUR_ECRAN)

        needs_mode_change = premiere_fois
        if not premiere_fois:
            surf = pygame.display.get_surface()
            if surf:
                cur_flags = surf.get_flags()
                cur_size  = surf.get_size()
                cur_display = getattr(self, '_display_index_actif', 0)
                needs_mode_change = (
                    (cur_size != (new_w, new_h)) or
                    (bool(cur_flags & pygame.FULLSCREEN) != bool(flags & pygame.FULLSCREEN)) or
                    (cur_display != idx)
                )

        if needs_mode_change:
            try:
                self.ecran = pygame.display.set_mode((new_w, new_h), flags, display=idx)
            except TypeError:
                self.ecran = pygame.display.set_mode((new_w, new_h), flags)
            self._display_index_actif = idx

        self.largeur_ecran = new_w
        self.hauteur_ecran = new_h

        if not premiere_fois and needs_mode_change:
            h = self.hauteur_ecran
            self.police_titre  = pygame.font.Font(None, max(96, h // 7))
            self.police_bouton = pygame.font.Font(None, max(30, h // 28))
            self.police_texte  = pygame.font.Font(None, max(24, h // 36))
            self.police_petit  = pygame.font.Font(None, max(18, h // 48))
            self.creer_widgets_menu_principal()
            self.creer_widgets_menu_rejoindre()
            self.creer_widgets_menu_parametres()
            self.creer_widgets_menu_luminosite()
            self.creer_widgets_menu_pause()
            self.creer_widgets_menu_slots()
            self.creer_widgets_menu_confirmation()


# ======================================================================
#  POINT D'ENTRÉE
# ======================================================================

if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()
