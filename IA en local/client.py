# client.py
# Le VISUEL du jeu. À lancer par TOUS les joueurs.
# CORRECTION : Alignement des boutons, popup de confirmation, changement de langue, scroll.

import pygame
import socket
import pickle
import sys
#import subprocess
import threading
import serveur
import time
import copy
import os 

from parametres import *
from carte import Carte
from joueur import Joueur 
from ennemi import Ennemi 
from ame_perdue import AmePerdue
import gestion_parametres
import langue 
from bouton import Bouton
import gestion_sauvegarde

class Client:
    def __init__(self):
        pygame.init()
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


        self.parametres = gestion_parametres.charger_parametres()
        
        langue.set_langue(self.parametres['jouabilite']['langue'])
        
        self.largeur_ecran = LARGEUR_ECRAN
        self.hauteur_ecran = HAUTEUR_ECRAN
        self.appliquer_parametres_video(premiere_fois=True)
        
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.horloge = pygame.time.Clock()
        
        # Etats: MENU_PRINCIPAL, MENU_REJOINDRE, MENU_NOUVELLE_PARTIE, MENU_CONTINUER, MENU_PARAMETRES, MENU_CONFIRMATION, EN_JEU, QUITTER
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

        self.police_titre = pygame.font.Font(None, 72)
        self.police_bouton = pygame.font.Font(None, 40)
        self.police_texte = pygame.font.Font(None, 32)
        
        self.parametres_temp = {}
        self.touche_a_modifier = None
        
        # Variables pour la popup de confirmation
        self.id_slot_a_ecraser = None
        
        # Variables pour le scroll des paramètres
        self.scroll_y_params = 0
        self.message_erreur_connexion = None
        
        self.creer_widgets_menu_principal()
        self.creer_widgets_menu_rejoindre()
        self.creer_widgets_menu_parametres()
        self.creer_widgets_menu_pause()
        self.creer_widgets_menu_slots()
        self.creer_widgets_menu_confirmation() # Nouveau



    def obtenir_ip_locale(self):
        """Retourne l'IP locale de la machine sur le réseau."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_locale = s.getsockname()[0]
            s.close()
            return ip_locale
        except Exception:
            return "Non disponible"

    def copier_dans_presse_papier(self, texte):
        """Copie le texte dans le presse-papiers (Windows uniquement pour l'instant)"""
        try:
            import subprocess
            subprocess.run(['clip'], input=texte.encode('utf-16le'), check=True)
            return True
        except:
            return False

    def appliquer_parametres_video(self, premiere_fois=False):
        flags = pygame.SCALED
        if self.parametres['video']['plein_ecran']:
            flags |= pygame.FULLSCREEN
        self.ecran = pygame.display.set_mode((self.largeur_ecran, self.hauteur_ecran), flags)

    def creer_widgets_menu_principal(self):
        cx = self.largeur_ecran // 2
        col_droite_bouton = cx + 50
        largeur_btn_param = 300
        largeur_btn = 400 
        y_start = 250
        self.btn_nouvelle_partie = Bouton(cx - largeur_btn//2, y_start, largeur_btn, 50, langue.get_texte("menu_nouvelle_partie"), self.police_bouton)
        y_start += 70
        self.btn_continuer = Bouton(cx - largeur_btn//2, y_start, largeur_btn, 50, langue.get_texte("menu_continuer"), self.police_bouton)
        y_start += 70
        self.btn_rejoindre = Bouton(cx - largeur_btn//2, y_start, largeur_btn, 50, langue.get_texte("menu_rejoindre"), self.police_bouton)
        y_start += 70
        self.btn_parametres = Bouton(cx - largeur_btn//2, y_start, largeur_btn, 50, langue.get_texte("menu_parametres"), self.police_bouton)
        y_start += 70
        self.btn_quitter = Bouton(cx - largeur_btn//2, y_start, largeur_btn, 50, langue.get_texte("menu_quitter"), self.police_bouton)
        self.boutons_menu_principal = [self.btn_nouvelle_partie, self.btn_continuer, self.btn_rejoindre, self.btn_parametres, self.btn_quitter]

        self.btn_copier_ip_locale = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte) #IP

    def creer_widgets_menu_rejoindre(self):
        cx = self.largeur_ecran // 2
        self.input_box_ip = pygame.Rect(cx - 200, 300, 400, 50)
        self.input_ip_texte = ""
        self.input_ip_actif = False
        self.btn_connecter = Bouton(cx - 200, 370, 400, 50, langue.get_texte("rejoindre_connecter"), self.police_bouton)
        self.btn_retour_rejoindre = Bouton(cx - 200, 440, 400, 50, langue.get_texte("rejoindre_retour"), self.police_bouton)
        self.btn_erreur_ok = Bouton(cx - 50, 0, 100, 50, "OK", self.police_bouton)

    def creer_widgets_menu_parametres(self):
        self.widgets_parametres = {}
        cx = self.largeur_ecran // 2
        col_droite_bouton = cx + 50
        largeur_btn_param = 300
        
        # Bouton Langue
        self.btn_changer_langue = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)

        # Bouton Vidéo
        self.btn_toggle_plein_ecran = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)
        
        # Boutons Contrôles
        self.btn_changer_gauche = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)
        self.btn_changer_droite = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)
        self.btn_changer_saut = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)
        self.btn_changer_echo = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)
        self.btn_changer_attaque = Bouton(col_droite_bouton, 0, largeur_btn_param, 40, "", self.police_texte)

        # Boutons Fixes (ne scrollent pas)
        self.btn_appliquer_params = Bouton(cx - 320, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_appliquer"), self.police_bouton)
        self.btn_retour_params = Bouton(cx + 20, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_retour"), self.police_bouton)

        self.boutons_menu_params_scrollables = [
            self.btn_changer_langue,
            self.btn_toggle_plein_ecran,
            self.btn_changer_gauche, self.btn_changer_droite,
            self.btn_changer_saut, self.btn_changer_echo, self.btn_changer_attaque,
            self.btn_copier_ip_locale
        ]
        
        self.boutons_menu_params_fixes = [self.btn_appliquer_params, self.btn_retour_params]

    def creer_widgets_menu_confirmation(self):
        """Crée les boutons pour la popup de confirmation."""
        cx = self.largeur_ecran // 2
        cy = self.hauteur_ecran // 2
        
        self.rect_popup = pygame.Rect(cx - 250, cy - 150, 500, 300)
        self.btn_popup_oui = Bouton(cx - 150, cy + 50, 100, 50, langue.get_texte("popup_oui"), self.police_bouton)
        self.btn_popup_non = Bouton(cx + 50, cy + 50, 100, 50, langue.get_texte("popup_non"), self.police_bouton)
        
        self.boutons_confirmation = [self.btn_popup_oui, self.btn_popup_non]

    def creer_widgets_menu_pause(self):
        cx = self.largeur_ecran // 2
        largeur_btn = 400
        
        self.btn_pause_reprendre = Bouton(cx - largeur_btn//2, 250, largeur_btn, 50, langue.get_texte("pause_reprendre"), self.police_bouton)
        self.btn_pause_parametres = Bouton(cx - largeur_btn//2, 320, largeur_btn, 50, langue.get_texte("pause_parametres"), self.police_bouton)
        self.btn_pause_activer_multi = Bouton(cx - largeur_btn//2, 390, largeur_btn, 50, "Activer Multijoueur (Bientôt)", self.police_bouton)
        self.btn_pause_activer_multi.couleur_fond = (40, 40, 40)
        self.btn_pause_quitter = Bouton(cx - largeur_btn//2, 460, largeur_btn, 50, langue.get_texte("pause_quitter_session"), self.police_bouton) 
        
        self.boutons_menu_pause = [self.btn_pause_reprendre, self.btn_pause_parametres, self.btn_pause_activer_multi, self.btn_pause_quitter]
        
        self.surface_fond_pause = pygame.Surface((self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
        self.surface_fond_pause.fill(COULEUR_FOND_PAUSE)

    def creer_widgets_menu_slots(self):
        self.infos_slots = []
        self.boutons_slots = []
        cx = self.largeur_ecran // 2
        largeur_btn_slot = self.largeur_ecran * 0.7 
        y_start = 250
        for i in range(NB_SLOTS_SAUVEGARDE):
            btn = Bouton(cx - largeur_btn_slot//2, y_start + (i * 100), largeur_btn_slot, 80, f"Slot {i+1}", self.police_bouton)
            self.boutons_slots.append(btn)
        self.btn_retour_slots = Bouton(cx - 200, y_start + (NB_SLOTS_SAUVEGARDE * 100) + 20, 400, 50, langue.get_texte("rejoindre_retour"), self.police_bouton)

    def lancer_application(self):
        while self.running:
            pos_souris = pygame.mouse.get_pos()
            
            if self.etat_jeu == "MENU_PRINCIPAL":
                self.gerer_menu_principal(pos_souris)
                self.dessiner_menu_principal()
            elif self.etat_jeu == "MENU_REJOINDRE":
                self.gerer_menu_rejoindre(pos_souris)
                self.dessiner_menu_rejoindre()
            elif self.etat_jeu == "MENU_NOUVELLE_PARTIE" or self.etat_jeu == "MENU_CONTINUER":
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
                elif self.etat_jeu == "EN_JEU":
                    pass
                else:
                    self.etat_jeu = "MENU_PRINCIPAL"
                    self.nettoyer_connexion()
                    self.actualiser_langues_widgets()
            elif self.etat_jeu == "QUITTER":
                self.running = False
            
            pygame.display.flip()
            self.horloge.tick(FPS)
            
        pygame.quit()
        sys.exit()

    def actualiser_langues_widgets(self):
        langue.set_langue(self.parametres['jouabilite']['langue'])
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.btn_nouvelle_partie.texte = langue.get_texte("menu_nouvelle_partie")
        self.btn_continuer.texte = langue.get_texte("menu_continuer")
        self.btn_rejoindre.texte = langue.get_texte("menu_rejoindre")
        self.btn_parametres.texte = langue.get_texte("menu_parametres")
        self.btn_quitter.texte = langue.get_texte("menu_quitter")
        self.btn_connecter.texte = langue.get_texte("rejoindre_connecter")
        self.btn_retour_rejoindre.texte = langue.get_texte("rejoindre_retour")
        self.btn_appliquer_params.texte = langue.get_texte("param_appliquer")
        self.btn_retour_params.texte = langue.get_texte("param_retour")
        self.btn_pause_reprendre.texte = langue.get_texte("pause_reprendre")
        self.btn_pause_parametres.texte = langue.get_texte("pause_parametres")
        self.btn_popup_oui.texte = langue.get_texte("popup_oui")
        self.btn_popup_non.texte = langue.get_texte("popup_non")

    def gerer_menu_principal(self, pos_souris):
        for bouton in self.boutons_menu_principal:
            bouton.verifier_survol(pos_souris)
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

    def dessiner_menu_principal(self):
        self.ecran.fill(COULEUR_FOND)
        titre_surface = self.police_titre.render(langue.get_texte("titre_jeu"), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 120))
        self.ecran.blit(titre_surface, titre_rect)
        for bouton in self.boutons_menu_principal:
            bouton.dessiner(self.ecran)

    def gerer_menu_rejoindre(self, pos_souris):
        # Si popup d'erreur affichée, gérer uniquement le bouton OK
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
        self.ecran.fill(COULEUR_FOND)
        titre_surface = self.police_titre.render(langue.get_texte("rejoindre_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre_surface, titre_surface.get_rect(center=(self.largeur_ecran // 2, 150)))
        label_surface = self.police_texte.render(langue.get_texte("rejoindre_label_ip"), True, COULEUR_TEXTE)
        self.ecran.blit(label_surface, label_surface.get_rect(center=(self.largeur_ecran // 2, 250)))
        pygame.draw.rect(self.ecran, COULEUR_INPUT_BOX, self.input_box_ip, border_radius=5)
        texte_ip_surface = self.police_texte.render(self.input_ip_texte, True, COULEUR_TEXTE)
        self.ecran.blit(texte_ip_surface, (self.input_box_ip.x + 10, self.input_box_ip.y + 10))
        if self.input_ip_actif and int(time.time() * 2) % 2 == 0:
            curseur_rect = pygame.Rect(self.input_box_ip.x + 12 + texte_ip_surface.get_width(), self.input_box_ip.y + 10, 3, self.police_texte.get_height() - 10)
            pygame.draw.rect(self.ecran, COULEUR_TEXTE, curseur_rect)
        self.btn_connecter.dessiner(self.ecran)
        self.btn_retour_rejoindre.dessiner(self.ecran)
        
        # ⬇️ POPUP D'ERREUR
        if self.message_erreur_connexion:
            # Fond semi-transparent
            surface_overlay = pygame.Surface((self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
            surface_overlay.fill((0, 0, 0, 180))
            self.ecran.blit(surface_overlay, (0, 0))
            
            # Cadre popup
            cx = self.largeur_ecran // 2
            cy = self.hauteur_ecran // 2
            rect_popup = pygame.Rect(cx - 300, cy - 150, 600, 300)
            pygame.draw.rect(self.ecran, COULEUR_BOUTON, rect_popup, border_radius=10)
            pygame.draw.rect(self.ecran, (255, 80, 80), rect_popup, width=3, border_radius=10)
            
            # Titre
            titre_erreur = self.police_bouton.render("Erreur de connexion", True, (255, 80, 80))
            self.ecran.blit(titre_erreur, titre_erreur.get_rect(center=(cx, cy - 80)))
            
            # Message (peut avoir plusieurs lignes)
            lignes = self.message_erreur_connexion.split('\n')
            y_offset = cy - 20
            for ligne in lignes:
                txt = self.police_texte.render(ligne, True, COULEUR_TEXTE)
                self.ecran.blit(txt, txt.get_rect(center=(cx, y_offset)))
                y_offset += 40
            
            # Bouton OK
            self.btn_erreur_ok.rect.y = cy + 80
            self.btn_erreur_ok.dessiner(self.ecran)

    def gerer_menu_slots(self, pos_souris):
        tous_boutons = self.boutons_slots + [self.btn_retour_slots]
        for bouton in tous_boutons:
            bouton.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            if self.btn_retour_slots.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL"
            for id_slot, bouton_slot in enumerate(self.boutons_slots):
                if bouton_slot.verifier_clic(event):
                    if self.etat_jeu == "MENU_NOUVELLE_PARTIE":
                        # Vérifier si le slot est vide ou non
                        if not self.infos_slots[id_slot]["est_vide"]:
                            self.id_slot_a_ecraser = id_slot
                            self.etat_jeu = "MENU_CONFIRMATION"
                        else:
                            self.lancer_partie_locale(id_slot, est_nouvelle_partie=True)
                    elif self.etat_jeu == "MENU_CONTINUER":
                        if not self.infos_slots[id_slot]["est_vide"]:
                            self.lancer_partie_locale(id_slot, est_nouvelle_partie=False)

    def dessiner_menu_slots(self):
        self.ecran.fill(COULEUR_FOND)
        titre_cle = "slots_titre_nouvelle" if self.etat_jeu == "MENU_NOUVELLE_PARTIE" else "slots_titre_continuer"
        titre_surface = self.police_titre.render(langue.get_texte(titre_cle), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 120))
        self.ecran.blit(titre_surface, titre_rect)
        for id_slot, bouton_slot in enumerate(self.boutons_slots):
            info = self.infos_slots[id_slot]
            if self.etat_jeu == "MENU_CONTINUER" and info["est_vide"]:
                bouton_slot.couleur_fond = (30, 30, 30) 
                bouton_slot.couleur_texte = (100, 100, 100)
            else:
                bouton_slot.couleur_fond = COULEUR_BOUTON
                bouton_slot.couleur_texte = COULEUR_TEXTE
            bouton_slot.texte = info["nom"]
            bouton_slot.dessiner(self.ecran)
            desc_surface = self.police_texte.render(info["description"], True, COULEUR_TEXTE)
            desc_rect = desc_surface.get_rect(center=(bouton_slot.rect.centerx, bouton_slot.rect.centery + 20))
            self.ecran.blit(desc_surface, desc_rect)
        self.btn_retour_slots.dessiner(self.ecran)

    def gerer_menu_confirmation(self, pos_souris):
        for bouton in self.boutons_confirmation:
            bouton.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            
            if self.btn_popup_oui.verifier_clic(event):
                # On lance la nouvelle partie en écrasant
                self.lancer_partie_locale(self.id_slot_a_ecraser, est_nouvelle_partie=True)
                # Note: lancer_partie_locale change l'état vers EN_JEU
            
            if self.btn_popup_non.verifier_clic(event):
                # On annule et on revient aux slots
                self.id_slot_a_ecraser = None
                self.etat_jeu = "MENU_NOUVELLE_PARTIE"

    def dessiner_menu_confirmation(self):
        # On dessine d'abord le menu des slots en arrière-plan
        self.dessiner_menu_slots()
        
        # Fond sombre pour la popup
        self.ecran.blit(self.surface_fond_pause, (0, 0))
        
        # Cadre Popup
        pygame.draw.rect(self.ecran, COULEUR_BOUTON, self.rect_popup, border_radius=10)
        pygame.draw.rect(self.ecran, COULEUR_TITRE, self.rect_popup, width=2, border_radius=10)
        
        # Texte
        titre = self.police_bouton.render(langue.get_texte("popup_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre, titre.get_rect(center=(self.rect_popup.centerx, self.rect_popup.y + 40)))
        
        msg = self.police_texte.render(langue.get_texte("popup_message"), True, COULEUR_TEXTE)
        self.ecran.blit(msg, msg.get_rect(center=(self.rect_popup.centerx, self.rect_popup.y + 100)))
        
        # Boutons
        self.btn_popup_oui.dessiner(self.ecran)
        self.btn_popup_non.dessiner(self.ecran)

    def gerer_menu_parametres(self, pos_souris):
        # Gestion du scroll avec la molette
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            
            if event.type == pygame.MOUSEWHEEL:
                self.scroll_y_params += event.y * 20
                # Limites simples pour le scroll
                if self.scroll_y_params > 0: self.scroll_y_params = 0
                if self.scroll_y_params < -500: self.scroll_y_params = -500 # A ajuster selon longueur

            # Gestion des clics boutons
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Vérification clics boutons scrollables
                # Il faut passer l'event, mais Bouton.verifier_clic utilise event.pos
                # Les boutons scrollables bougent, donc on doit vérifier avec leur position visuelle
                pass # Traité plus bas via verifier_clic standard si on met à jour les rects

            # Touches Clavier (Redéfinition)
            if self.touche_a_modifier:
                if event.type == pygame.KEYDOWN:
                    if event.key not in [pygame.K_ESCAPE, pygame.K_RETURN]:
                        nom_touche = pygame.key.name(event.key)
                        self.parametres_temp['controles'][self.touche_a_modifier] = nom_touche
                        self.touche_a_modifier = None 
            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.parametres_temp = {} 
                        self.etat_jeu = self.etat_jeu_precedent
                
                # Boutons Fixes
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

                # Boutons Scrollables (On doit vérifier manuellement car leur rect ne bouge pas, mais l'affichage si)
                # Pour simplifier, on met à jour leur rect dans dessiner_menu_parametres, 
                # et ici on espère que la boucle d'events capture le bon moment.
                # Une meilleure approche : verifier_clic doit savoir le décalage.
                # Ici, on va tricher : on délègue le clic aux boutons qui ont été mis à jour graphiquement.
                
                if self.btn_toggle_plein_ecran.verifier_clic(event):
                    self.parametres_temp['video']['plein_ecran'] = not self.parametres_temp['video']['plein_ecran']
                
                if self.btn_changer_langue.verifier_clic(event):
                    langues = ['fr', 'en']
                    actuelle = self.parametres_temp['jouabilite']['langue']
                    try:
                        idx = langues.index(actuelle)
                        nouvelle = langues[(idx + 1) % len(langues)]
                    except ValueError:
                        nouvelle = 'fr'
                    self.parametres_temp['jouabilite']['langue'] = nouvelle

                if self.btn_changer_gauche.verifier_clic(event): self.touche_a_modifier = "gauche"
                if self.btn_changer_droite.verifier_clic(event): self.touche_a_modifier = "droite"
                if self.btn_changer_saut.verifier_clic(event): self.touche_a_modifier = "saut"
                if self.btn_changer_echo.verifier_clic(event): self.touche_a_modifier = "echo"
                if self.btn_changer_attaque.verifier_clic(event): self.touche_a_modifier = "attaque" 

                # Gestion des boutons IP
                if self.btn_copier_ip_locale.verifier_clic(event):
                    ip = self.obtenir_ip_locale()
                    if self.copier_dans_presse_papier(ip):
                        print(f"[CLIENT] IP locale copiée : {ip}")

        # Mise à jour survol pour boutons fixes
        for btn in self.boutons_menu_params_fixes:
            btn.verifier_survol(pos_souris)
        # Mise à jour survol pour boutons scrollables (leurs rects sont mis à jour dans dessiner)
        for btn in self.boutons_menu_params_scrollables:
            btn.verifier_survol(pos_souris)

    def dessiner_menu_parametres(self):
        self.ecran.fill(COULEUR_FOND)
        
        # Titre (Fixe)
        titre_surface = self.police_titre.render(langue.get_texte("param_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre_surface, titre_surface.get_rect(center=(self.largeur_ecran // 2, 50)))
        
        # Zone de contenu scrollable (tout ce qui suit est décalé par self.scroll_y_params)
        y_base = 120 + self.scroll_y_params
        
        params = self.parametres_temp if self.parametres_temp else self.parametres
        
        # --- Section Jouabilité ---
        titre_section = self.police_bouton.render(langue.get_texte("param_section_jouabilite"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_base))
        y_base += 60
        
        # Langue
        lbl = self.police_texte.render(langue.get_texte("param_langue"), True, COULEUR_TEXTE)
        self.ecran.blit(lbl, (120, y_base + 5))
        # Bouton aligné
        self.btn_changer_langue.rect.y = y_base
        self.btn_changer_langue.texte = params['jouabilite']['langue'].upper()
        self.btn_changer_langue.dessiner(self.ecran)
        y_base += 60

        # --- Section Vidéo ---
        titre_section = self.police_bouton.render(langue.get_texte("param_section_video"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_base))
        y_base += 60
        
        # Option Plein écran
        label_plein_ecran = self.police_texte.render(langue.get_texte("param_plein_ecran"), True, COULEUR_TEXTE)
        self.ecran.blit(label_plein_ecran, (120, y_base + 5))
        
        # Alignement Bouton Plein Écran
        self.btn_toggle_plein_ecran.rect.y = y_base # Mise à jour position Y pour clic et dessin
        texte_btn_plein_ecran = langue.get_texte("param_oui") if params['video']['plein_ecran'] else langue.get_texte("param_non")
        self.btn_toggle_plein_ecran.texte = texte_btn_plein_ecran
        self.btn_toggle_plein_ecran.dessiner(self.ecran)
        y_base += 60

        # --- Section Contrôles ---
        titre_section = self.police_bouton.render(langue.get_texte("param_section_controles"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_base))
        y_base += 60
        
        # Helper pour dessiner les contrôles alignés
        def dessiner_controle_btn(label, cle_json, btn, y):
            lbl = self.police_texte.render(label, True, COULEUR_TEXTE)
            self.ecran.blit(lbl, (120, y + 5))
            
            # Mise à jour position Y du bouton pour qu'il soit en face du texte
            btn.rect.y = y
            
            txt = params['controles'][cle_json].upper()
            if self.touche_a_modifier == cle_json:
                txt = langue.get_texte("param_attente_touche")
            btn.texte = txt
            btn.dessiner(self.ecran)
        
        dessiner_controle_btn(langue.get_texte("param_gauche"), 'gauche', self.btn_changer_gauche, y_base)
        y_base += 50
        dessiner_controle_btn(langue.get_texte("param_droite"), 'droite', self.btn_changer_droite, y_base)
        y_base += 50
        dessiner_controle_btn(langue.get_texte("param_saut"), 'saut', self.btn_changer_saut, y_base)
        y_base += 50
        dessiner_controle_btn(langue.get_texte("param_echo"), 'echo', self.btn_changer_echo, y_base)
        y_base += 50
        dessiner_controle_btn(langue.get_texte("param_attaque"), 'attaque', self.btn_changer_attaque, y_base) 
        
        # Boutons Appliquer / Retour (Fixes en bas)
        self.btn_appliquer_params.dessiner(self.ecran)
        self.btn_retour_params.dessiner(self.ecran)

        # Section Réseau
        y_base += 70  # (Espacement)
        titre_section = self.police_bouton.render(langue.get_texte("param_section_reseau"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_base))
        y_base += 60
        
        # IP Locale
        lbl_ip_locale = self.police_texte.render("IP Locale (LAN) :", True, COULEUR_TEXTE)
        self.ecran.blit(lbl_ip_locale, (120, y_base + 5))
        
        self.btn_copier_ip_locale.rect.y = y_base
        ip_locale = self.obtenir_ip_locale()
        self.btn_copier_ip_locale.texte = f"{ip_locale}    (copier)"
        self.btn_copier_ip_locale.dessiner(self.ecran)
        y_base += 50

    # --- GESTION DU RÉSEAU ET DU JEU ---

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement = "nouvelle" if est_nouvelle_partie else "charger"

        print(f"[CLIENT] Démarrage serveur local (slot {id_slot}, {type_lancement})")

        thread_serveur = threading.Thread(
            target=serveur.main,
            args=(id_slot, type_lancement),
            daemon=True
        )
        thread_serveur.start()

        time.sleep(1.5)

        if self.connecter("localhost"):
            self.etat_jeu = "EN_JEU"
        else:
            print("[CLIENT] Échec connexion serveur")
            self.etat_jeu = "MENU_PRINCIPAL"


    def lancer_serveur_local(self):
        """DEPRECATED - Remplacé par lancer_partie_locale"""
        # Cette fonction n'est plus appelée directement.
        print("Erreur: lancer_serveur_local() ne doit plus être utilisé.")
        pass

    def connecter(self, hote):
        """Tente de se connecter au serveur."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[CLIENT] Connexion à {hote}:{PORT_SERVEUR}...")
            self.client_socket.connect((hote, PORT_SERVEUR))
            
            # Recevoir la réponse
            reponse = pickle.loads(self.client_socket.recv(2048))
            
            # Vérifier si c'est une erreur
            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    print("[CLIENT] Serveur plein (3/3 joueurs)")
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs connectes)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False
            
            # C'est l'ID du joueur
            self.mon_id = reponse
            print(f"[CLIENT] Connecté avec succès. Mon ID est {self.mon_id}")
            
            # Réinitialiser message d'erreur
            self.message_erreur_connexion = None
            
            # Initialiser jeu
            self.carte = Carte()
            self.vis_map_locale = self.carte.creer_carte_visibilite_vierge()
            self.joueurs_locaux = {}
            self.ennemis_locaux = {}
            self.ames_perdues_locales = {}
            
            return True
        except socket.error as e:
            print(f"[CLIENT] Échec connexion: {e}")
            self.message_erreur_connexion = f"Impossible de se connecter\nau serveur : {hote}"
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        """Nettoie la connexion et réinitialise les variables de jeu."""
        if self.client_socket:
            self.client_socket.close()
        self.client_socket = None
        self.mon_id = -1
        self.joueurs_locaux = {}
        self.ennemis_locaux = {} # Nettoyer aussi les ennemis
        self.ames_perdues_locales = {} # Nettoyer aussi les âmes
        self.carte = None
        self.vis_map_locale = None
        
        # Si on était l'hôte, on tente d'arrêter le serveur
        if hasattr(self, 'processus_serveur') and self.processus_serveur:
            print("[CLIENT] Tentative d'arrêt du serveur local...")
            self.processus_serveur.terminate()
            self.processus_serveur.poll() # Attendre que le processus se termine
            self.processus_serveur = None
            
        print("[CLIENT] Connexion nettoyée.")

    def gerer_evenements_jeu(self):
        """
        Gère les entrées (clavier/souris) pendant que le jeu tourne.
        Renvoie les commandes à envoyer au serveur.
        """
        # Initialiser les commandes et l'indicateur d'écho pour éviter les références avant affectation
        commandes_clavier = {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}
        declencher_echo = False
        
        # Récupérer les codes de touches depuis les paramètres
        try:
            touche_gauche = pygame.key.key_code(self.parametres['controles']['gauche'])
            touche_droite = pygame.key.key_code(self.parametres['controles']['droite'])
            touche_saut = pygame.key.key_code(self.parametres['controles']['saut'])
            touche_echo = pygame.key.key_code(self.parametres['controles']['echo'])
            touche_attaque = pygame.key.key_code(self.parametres['controles']['attaque'])
        except Exception as e:
            print(f"Erreur de mapping des touches: {e}. Utilisation des touches par défaut.")
            # Fallback (au cas où les noms dans le JSON sont mauvais)
            touche_gauche, touche_droite, touche_saut, touche_echo, touche_attaque = pygame.K_q, pygame.K_d, pygame.K_SPACE, pygame.K_e, pygame.K_k


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False # Arrête toute l'application
                self.etat_jeu = "QUITTER" # Force la sortie de la boucle jeu
            
            if event.type == pygame.KEYDOWN:
                # Gérer l'écho (appui unique)
                if event.key == touche_echo:
                    declencher_echo = True
                if event.key == touche_attaque:
                    commandes_clavier['attaque'] = True # On marque l'action pour ce tick
                # Menu Pause
                if event.key == pygame.K_ESCAPE:
                    print("[CLIENT] Passage en mode Pause")
                    self.etat_jeu_interne = "PAUSE"
                    # On retourne des commandes vides pour ce tick
                    return {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}, 'echo': False}
        
        # Gérer les mouvements (touches maintenues)
        touches = pygame.key.get_pressed()
        if touches[touche_gauche]:
            commandes_clavier['gauche'] = True
        if touches[touche_droite]:
            commandes_clavier['droite'] = True
        if touches[touche_saut]:
            commandes_clavier['saut'] = True
            
        return {'clavier': commandes_clavier, 'echo': declencher_echo}

    def gerer_evenements_pause(self, pos_souris):
        """Gère les entrées (clavier/souris) pendant que le jeu est en pause."""
        
        for bouton in self.boutons_menu_pause:
            bouton.verifier_survol(pos_souris)
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.etat_jeu = "QUITTER"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.etat_jeu_interne = "JEU" # Reprendre
            
            # Clic sur "Reprendre"
            if self.btn_pause_reprendre.verifier_clic(event):
                self.etat_jeu_interne = "JEU"
            
            # Clic sur "Paramètres"
            if self.btn_pause_parametres.verifier_clic(event):
                # On change l'état principal, ce qui fera quitter la boucle_jeu_reseau
                self.etat_jeu = "MENU_PARAMETRES"
            
            # Clic sur "Activer Multi"
            if self.btn_pause_activer_multi.verifier_clic(event):
                print("Activation du multijoueur... (Non implémenté)")
                # TODO: Rendre le serveur visible sur le réseau (au lieu de 127.0.0.1)
                # C'est une modification majeure sur 'serveur.py'
            
            # Clic sur "Quitter"
            if self.btn_pause_quitter.verifier_clic(event):
                # On change l'état principal, ce qui fera quitter la boucle
                # et déclenchera le nettoyage de la connexion
                self.etat_jeu = "MENU_PRINCIPAL" 


    def dessiner_jeu(self):
        """Dessine l'état actuel du jeu."""
        if not self.carte or not self.vis_map_locale:
            return # Ne rien dessiner si le jeu n'est pas prêt

        # 1. Dessiner la carte (uniquement les parties visibles)
        self.carte.dessiner_carte(self.ecran, self.vis_map_locale)
        
        # 2. Dessiner tous les joueurs
        for id_joueur, joueur in self.joueurs_locaux.items():
            joueur.dessiner(self.ecran)
            
            # Optionnel : dessiner son propre joueur d'une couleur différente
            if id_joueur == self.mon_id:
                joueur.couleur = COULEUR_JOUEUR
            else:
                joueur.couleur = COULEUR_JOUEUR_AUTRE
                
        # 3. Dessiner tous les ennemis
        for ennemi in self.ennemis_locaux.values():
            ennemi.dessiner(self.ecran)
            
        # 4. Dessiner toutes les âmes perdues
        for ame in self.ames_perdues_locales.values():
            ame.dessiner(self.ecran)
            
        # 5. Dessiner l'interface (HUD) - Ex: Barre de vie
        self.dessiner_hud()

    def dessiner_hud(self):
        """Dessine les informations du joueur (PV, etc.)"""
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        
        if mon_joueur:
            # Barre de vie
            pv = mon_joueur.pv
            pv_max = mon_joueur.pv_max
            
            x_barre = 20
            y_barre = 20
            largeur_coeur = 30
            padding = 5
            
            for i in range(pv_max):
                rect_fond = pygame.Rect(x_barre + i * (largeur_coeur + padding), y_barre, largeur_coeur, 30)
                pygame.draw.rect(self.ecran, COULEUR_PV_PERDU, rect_fond, border_radius=4)
                
            for i in range(pv):
                rect_plein = pygame.Rect(x_barre + i * (largeur_coeur + padding), y_barre, largeur_coeur, 30)
                pygame.draw.rect(self.ecran, COULEUR_PV, rect_plein, border_radius=4)
            
            # Argent (Âmes)
            argent_txt = self.police_texte.render(f"Ames: {mon_joueur.argent}", True, COULEUR_TEXTE)
            self.ecran.blit(argent_txt, (20, 60))

    def dessiner_menu_pause(self):
        """Dessine le menu pause par-dessus l'écran de jeu."""
        
        # 1. Dessine le fond semi-transparent
        self.ecran.blit(self.surface_fond_pause, (0, 0))
        
        # 2. Dessine le titre
        titre_surface = self.police_titre.render(langue.get_texte("pause_titre"), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 150))
        self.ecran.blit(titre_surface, titre_rect)
        
        # 3. Met à jour le texte du bouton Quitter (Hôte vs Client)
        # On vérifie si on est l'hôte (ID 0)
        est_hote = self.mon_id == 0
        
        if est_hote:
            # L'hôte voit "Terminer" si multi, "Quitter" si solo
            est_multijoueur = len(self.joueurs_locaux) > 1
            if est_multijoueur:
                self.btn_pause_quitter.texte = langue.get_texte("pause_terminer_session")
            else:
                self.btn_pause_quitter.texte = langue.get_texte("pause_quitter_session")
        else:
            # Les clients voient toujours "Quitter"
            self.btn_pause_quitter.texte = langue.get_texte("pause_quitter_session")
            
        # 4. Gérer le bouton "Activer Multi"
        if est_hote:
            self.btn_pause_activer_multi.couleur_fond = COULEUR_BOUTON # Actif
            self.btn_pause_activer_multi.couleur_texte = COULEUR_TEXTE
        else:
            self.btn_pause_activer_multi.couleur_fond = (30, 30, 30) # Grisé
            self.btn_pause_activer_multi.couleur_texte = (100, 100, 100)

        # 5. Dessine les boutons
        for bouton in self.boutons_menu_pause:
            bouton.dessiner(self.ecran)


    def boucle_jeu_reseau(self):
        """
        Boucle principale du jeu (envoi commandes, réception état, dessin).
        """
        
        # La connexion doit déjà être établie
        if not self.client_socket:
            print("[CLIENT] Erreur: Tentative de boucle de jeu sans connexion.")
            self.etat_jeu = "MENU_PRINCIPAL"
            return

        # Boucle tant qu'on est en jeu et que l'appli tourne
        while self.etat_jeu == "EN_JEU" and self.running:
            
            pos_souris = pygame.mouse.get_pos()
            
            # 1. Gérer les entrées locales (soit jeu, soit pause)
            commandes_a_envoyer = {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}, 'echo': False}
            
            if self.etat_jeu_interne == "JEU":
                commandes_a_envoyer = self.gerer_evenements_jeu()
            elif self.etat_jeu_interne == "PAUSE":
                self.gerer_evenements_pause(pos_souris)
                # On envoie des commandes vides pendant la pause
            
            # Si on quitte (via ESC ou croix ou bouton), self.etat_jeu change
            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            try:
                # 2. Envoyer les commandes au serveur
                self.client_socket.send(pickle.dumps(commandes_a_envoyer))
                
                # 3. Recevoir l'état du jeu complet du serveur
                donnees_recues = pickle.loads(self.client_socket.recv(4096))
                
                # 4. Mettre à jour l'état local
                self.vis_map_locale = donnees_recues['vis_map']
                etat_joueurs_serveur = donnees_recues['joueurs']
                etat_ennemis_serveur = donnees_recues['ennemis']
                etat_ames_serveur = donnees_recues.get('ames_perdues', []) # .get pour compatibilité
                
                # --- Mettre à jour les joueurs ---
                ids_serveur = {j['id'] for j in etat_joueurs_serveur}
                for id_local in list(self.joueurs_locaux.keys()):
                    if id_local not in ids_serveur:
                        del self.joueurs_locaux[id_local]
                
                for data_joueur in etat_joueurs_serveur:
                    id_j = data_joueur['id']
                    if id_j not in self.joueurs_locaux:
                        self.joueurs_locaux[id_j] = Joueur(data_joueur['x'], data_joueur['y'], id_j)
                    
                    self.joueurs_locaux[id_j].set_etat(data_joueur)
                
                # --- Mettre à jour les ennemis ---
                ids_ennemis_serveur = {e['id'] for e in etat_ennemis_serveur}
                for id_local in list(self.ennemis_locaux.keys()):
                    if id_local not in ids_ennemis_serveur:
                        del self.ennemis_locaux[id_local] # Ennemi mort/supprimé
                
                for data_ennemi in etat_ennemis_serveur:
                    id_e = data_ennemi['id']
                    if id_e not in self.ennemis_locaux:
                        # Crée un "fantôme" local
                        self.ennemis_locaux[id_e] = Ennemi(data_ennemi['x'], data_ennemi['y'], id_e)
                    
                    # Met à jour le fantôme
                    self.ennemis_locaux[id_e].set_etat(data_ennemi)
                
                # --- Mettre à jour les âmes perdues ---
                ids_ames_serveur = {a['id'] for a in etat_ames_serveur}
                for id_local in list(self.ames_perdues_locales.keys()):
                    if id_local not in ids_ames_serveur:
                        del self.ames_perdues_locales[id_local] 
                
                for data_ame in etat_ames_serveur:
                    id_a = data_ame['id']
                    if id_a not in self.ames_perdues_locales:
                        self.ames_perdues_locales[id_a] = AmePerdue(data_ame['x'], data_ame['y'], data_ame['id_joueur'])
                    
                    self.ames_perdues_locales[id_a].set_etat(data_ame)
                
                # 5. Dessiner la scène
                self.dessiner_jeu()
                
                # 6. Dessiner le menu pause PAR-DESSUS si on est en pause
                if self.etat_jeu_interne == "PAUSE":
                    self.dessiner_menu_pause()
                
            except socket.error as e:
                print(f"[CLIENT] Erreur réseau: {e}")
                self.etat_jeu = "MENU_PRINCIPAL" # Revenir au menu
            except EOFError:
                print("[CLIENT] Connexion perdue avec le serveur.")
                self.etat_jeu = "MENU_PRINCIPAL" # Revenir au menu
            except pickle.UnpicklingError:
                print("[CLIENT] Erreur de désérialisation. Données corrompues.")
                pass

            # Le flip est maintenant géré ici, car le dessin est complexe
            pygame.display.flip()
            self.horloge.tick(FPS)

# --- Point d'entrée ---
if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()