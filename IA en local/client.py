# client.py
# Mise à jour : Gestion de la touche Attaque, Affichage Argent.

import pygame
import socket
import pickle
import sys
import subprocess
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
        self.parametres = gestion_parametres.charger_parametres()
        
        langue.set_langue(self.parametres['jouabilite']['langue'])
        
        self.largeur_ecran = LARGEUR_ECRAN
        self.hauteur_ecran = HAUTEUR_ECRAN
        self.appliquer_parametres_video(premiere_fois=True)
        
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        self.horloge = pygame.time.Clock()
        
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
        
        self.creer_widgets_menu_principal()
        self.creer_widgets_menu_rejoindre()
        self.creer_widgets_menu_parametres()
        self.creer_widgets_menu_pause()
        self.creer_widgets_menu_slots()

    def appliquer_parametres_video(self, premiere_fois=False):
        flags = pygame.SCALED
        if self.parametres['video']['plein_ecran']:
            flags |= pygame.FULLSCREEN
        self.ecran = pygame.display.set_mode((self.largeur_ecran, self.hauteur_ecran), flags)

    def creer_widgets_menu_principal(self):
        cx = self.largeur_ecran // 2
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

    def creer_widgets_menu_rejoindre(self):
        cx = self.largeur_ecran // 2
        self.input_box_ip = pygame.Rect(cx - 200, 300, 400, 50)
        self.input_ip_texte = ""
        self.input_ip_actif = False
        self.btn_connecter = Bouton(cx - 200, 370, 400, 50, langue.get_texte("rejoindre_connecter"), self.police_bouton)
        self.btn_retour_rejoindre = Bouton(cx - 200, 440, 400, 50, langue.get_texte("rejoindre_retour"), self.police_bouton)

    def creer_widgets_menu_parametres(self):
        cx = self.largeur_ecran // 2
        col_droite_bouton = cx + 50
        largeur_btn_param = 300
        
        y_video = 250
        self.btn_toggle_plein_ecran = Bouton(col_droite_bouton, y_video, largeur_btn_param, 40, "", self.police_texte)
        
        y_controles = 350
        self.btn_changer_gauche = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_droite = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_saut = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_echo = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_attaque = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte) # AJOUT

        self.btn_appliquer_params = Bouton(cx - 320, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_appliquer"), self.police_bouton)
        self.btn_retour_params = Bouton(cx + 20, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_retour"), self.police_bouton)

        self.boutons_menu_params = [
            self.btn_toggle_plein_ecran,
            self.btn_changer_gauche, self.btn_changer_droite,
            self.btn_changer_saut, self.btn_changer_echo, self.btn_changer_attaque,
            self.btn_appliquer_params, self.btn_retour_params
        ]

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
                else:
                    print(f"[CLIENT] Échec de la connexion à {hote}")
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

    def gerer_menu_parametres(self, pos_souris):
        for bouton in self.boutons_menu_params:
            bouton.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
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
                if self.btn_retour_params.verifier_clic(event):
                    self.parametres_temp = {} 
                    self.touche_a_modifier = None
                    self.etat_jeu = self.etat_jeu_precedent 
                if self.btn_appliquer_params.verifier_clic(event):
                    self.parametres = copy.deepcopy(self.parametres_temp)
                    gestion_parametres.sauvegarder_parametres(self.parametres)
                    self.appliquer_parametres_video()
                    self.actualiser_langues_widgets() 
                    self.touche_a_modifier = None
                    self.etat_jeu = self.etat_jeu_precedent 
                if self.btn_toggle_plein_ecran.verifier_clic(event):
                    self.parametres_temp['video']['plein_ecran'] = not self.parametres_temp['video']['plein_ecran']
                if self.btn_changer_gauche.verifier_clic(event): self.touche_a_modifier = "gauche"
                if self.btn_changer_droite.verifier_clic(event): self.touche_a_modifier = "droite"
                if self.btn_changer_saut.verifier_clic(event): self.touche_a_modifier = "saut"
                if self.btn_changer_echo.verifier_clic(event): self.touche_a_modifier = "echo"
                if self.btn_changer_attaque.verifier_clic(event): self.touche_a_modifier = "attaque" # AJOUT

    def dessiner_menu_parametres(self):
        self.ecran.fill(COULEUR_FOND)
        titre_surface = self.police_titre.render(langue.get_texte("param_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre_surface, titre_surface.get_rect(center=(self.largeur_ecran // 2, 80)))
        
        y_offset = 200
        titre_section = self.police_bouton.render(langue.get_texte("param_section_video"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_offset))
        y_offset += 60
        label_plein_ecran = self.police_texte.render(langue.get_texte("param_plein_ecran"), True, COULEUR_TEXTE)
        self.ecran.blit(label_plein_ecran, (120, y_offset + 5))
        params = self.parametres_temp if self.parametres_temp else self.parametres
        texte_btn_plein_ecran = langue.get_texte("param_oui") if params['video']['plein_ecran'] else langue.get_texte("param_non")
        self.btn_toggle_plein_ecran.texte = texte_btn_plein_ecran
        self.btn_toggle_plein_ecran.dessiner(self.ecran)

        y_offset = 350
        titre_section = self.police_bouton.render(langue.get_texte("param_section_controles"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_offset))
        y_offset += 60
        
        # Helper pour dessiner les contrôles
        def dessiner_controle_btn(label, cle_json, btn, y):
            lbl = self.police_texte.render(label, True, COULEUR_TEXTE)
            self.ecran.blit(lbl, (120, y + 5))
            txt = params['controles'][cle_json].upper()
            if self.touche_a_modifier == cle_json:
                txt = langue.get_texte("param_attente_touche")
            btn.texte = txt
            btn.dessiner(self.ecran)
        
        dessiner_controle_btn(langue.get_texte("param_gauche"), 'gauche', self.btn_changer_gauche, y_offset)
        y_offset += 50
        dessiner_controle_btn(langue.get_texte("param_droite"), 'droite', self.btn_changer_droite, y_offset)
        y_offset += 50
        dessiner_controle_btn(langue.get_texte("param_saut"), 'saut', self.btn_changer_saut, y_offset)
        y_offset += 50
        dessiner_controle_btn(langue.get_texte("param_echo"), 'echo', self.btn_changer_echo, y_offset)
        y_offset += 50
        dessiner_controle_btn("Attaque", 'attaque', self.btn_changer_attaque, y_offset) # TODO: Texte multilingue
        
        self.btn_appliquer_params.dessiner(self.ecran)
        self.btn_retour_params.dessiner(self.ecran)

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement = "nouvelle" if est_nouvelle_partie else "charger"
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            serveur_path = os.path.join(script_dir, 'serveur.py')
            commande_lancement = [sys.executable, serveur_path, str(id_slot), type_lancement]
            self.processus_serveur = subprocess.Popen(commande_lancement)
            time.sleep(2) 
        except FileNotFoundError as e:
            print(f"[CLIENT] ERREUR CRITIQUE: {e}")
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        except Exception as e:
            print(f"[CLIENT] Erreur inconnue: {e}")
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        
        if self.connecter("localhost"):
            self.etat_jeu = "EN_JEU"
        else:
            self.etat_jeu = "MENU_PRINCIPAL" 

    def connecter(self, hote):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((hote, PORT_SERVEUR))
            self.mon_id = pickle.loads(self.client_socket.recv(2048))
            self.carte = Carte()
            self.vis_map_locale = self.carte.creer_carte_visibilite_vierge()
            self.joueurs_locaux = {}
            self.ennemis_locaux = {}
            self.ames_perdues_locales = {}
            return True
        except socket.error as e:
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        if self.client_socket:
            self.client_socket.close()
        self.client_socket = None
        self.mon_id = -1
        self.joueurs_locaux = {}
        self.ennemis_locaux = {}
        self.ames_perdues_locales = {}
        self.carte = None
        self.vis_map_locale = None
        if hasattr(self, 'processus_serveur') and self.processus_serveur:
            self.processus_serveur.terminate()
            self.processus_serveur.poll() 
            self.processus_serveur = None

    def gerer_evenements_jeu(self):
        commandes_clavier = {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}
        declencher_echo = False
        
        try:
            touche_gauche = pygame.key.key_code(self.parametres['controles']['gauche'])
            touche_droite = pygame.key.key_code(self.parametres['controles']['droite'])
            touche_saut = pygame.key.key_code(self.parametres['controles']['saut'])
            touche_echo = pygame.key.key_code(self.parametres['controles']['echo'])
            touche_attaque = pygame.key.key_code(self.parametres['controles']['attaque'])
        except Exception as e:
            touche_gauche, touche_droite, touche_saut, touche_echo, touche_attaque = pygame.K_q, pygame.K_d, pygame.K_SPACE, pygame.K_e, pygame.K_k

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False 
                self.etat_jeu = "QUITTER" 
            if event.type == pygame.KEYDOWN:
                if event.key == touche_echo:
                    declencher_echo = True
                if event.key == touche_attaque:
                    commandes_clavier['attaque'] = True # On marque l'action pour ce tick
                if event.key == pygame.K_ESCAPE:
                    self.etat_jeu_interne = "PAUSE"
                    return {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}, 'echo': False}
        
        touches = pygame.key.get_pressed()
        if touches[touche_gauche]:
            commandes_clavier['gauche'] = True
        if touches[touche_droite]:
            commandes_clavier['droite'] = True
        if touches[touche_saut]:
            commandes_clavier['saut'] = True
        # Note: Pour l'attaque, on peut aussi permettre de maintenir la touche, mais un appui unique est souvent mieux.
        # Ici j'ai mis l'appui unique dans KEYDOWN, mais si on veut mitrailler en maintenant, on ajouterait ici.
            
        return {'clavier': commandes_clavier, 'echo': declencher_echo}

    def gerer_evenements_pause(self, pos_souris):
        for bouton in self.boutons_menu_pause:
            bouton.verifier_survol(pos_souris)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.etat_jeu = "QUITTER"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.etat_jeu_interne = "JEU" 
            if self.btn_pause_reprendre.verifier_clic(event):
                self.etat_jeu_interne = "JEU"
            if self.btn_pause_parametres.verifier_clic(event):
                self.etat_jeu = "MENU_PARAMETRES"
            if self.btn_pause_quitter.verifier_clic(event):
                self.etat_jeu = "MENU_PRINCIPAL" 

    def dessiner_jeu(self):
        if not self.carte or not self.vis_map_locale:
            return 
        self.carte.dessiner_carte(self.ecran, self.vis_map_locale)
        for id_joueur, joueur in self.joueurs_locaux.items():
            joueur.dessiner(self.ecran)
        for ennemi in self.ennemis_locaux.values():
            ennemi.dessiner(self.ecran)
        for ame in self.ames_perdues_locales.values():
            ame.dessiner(self.ecran)
        self.dessiner_hud()

    def dessiner_hud(self):
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if mon_joueur:
            # PV
            pv, pv_max = mon_joueur.pv, mon_joueur.pv_max
            x_barre, y_barre = 20, 20
            largeur_coeur, padding = 30, 5
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
        self.ecran.blit(self.surface_fond_pause, (0, 0))
        titre_surface = self.police_titre.render(langue.get_texte("pause_titre"), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 150))
        self.ecran.blit(titre_surface, titre_rect)
        
        est_hote = self.mon_id == 0
        if est_hote:
            est_multijoueur = len(self.joueurs_locaux) > 1
            if est_multijoueur:
                self.btn_pause_quitter.texte = langue.get_texte("pause_terminer_session")
            else:
                self.btn_pause_quitter.texte = langue.get_texte("pause_quitter_session")
        else:
            self.btn_pause_quitter.texte = langue.get_texte("pause_quitter_session")
            
        if est_hote:
            self.btn_pause_activer_multi.couleur_fond = COULEUR_BOUTON 
            self.btn_pause_activer_multi.couleur_texte = COULEUR_TEXTE
        else:
            self.btn_pause_activer_multi.couleur_fond = (30, 30, 30) 
            self.btn_pause_activer_multi.couleur_texte = (100, 100, 100)

        for bouton in self.boutons_menu_pause:
            bouton.dessiner(self.ecran)

    def boucle_jeu_reseau(self):
        if not self.client_socket:
            self.etat_jeu = "MENU_PRINCIPAL"
            return

        while self.etat_jeu == "EN_JEU" and self.running:
            pos_souris = pygame.mouse.get_pos()
            commandes_a_envoyer = {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False}, 'echo': False}
            
            if self.etat_jeu_interne == "JEU":
                commandes_a_envoyer = self.gerer_evenements_jeu()
            elif self.etat_jeu_interne == "PAUSE":
                self.gerer_evenements_pause(pos_souris)
            
            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            try:
                self.client_socket.send(pickle.dumps(commandes_a_envoyer))
                donnees_recues = pickle.loads(self.client_socket.recv(4096))
                
                self.vis_map_locale = donnees_recues['vis_map']
                etat_joueurs_serveur = donnees_recues['joueurs']
                etat_ennemis_serveur = donnees_recues['ennemis']
                etat_ames_serveur = donnees_recues.get('ames_perdues', []) 
                
                ids_serveur = {j['id'] for j in etat_joueurs_serveur}
                for id_local in list(self.joueurs_locaux.keys()):
                    if id_local not in ids_serveur:
                        del self.joueurs_locaux[id_local]
                for data_joueur in etat_joueurs_serveur:
                    id_j = data_joueur['id']
                    if id_j not in self.joueurs_locaux:
                        self.joueurs_locaux[id_j] = Joueur(data_joueur['x'], data_joueur['y'], id_j)
                    self.joueurs_locaux[id_j].set_etat(data_joueur)
                
                ids_ennemis_serveur = {e['id'] for e in etat_ennemis_serveur}
                for id_local in list(self.ennemis_locaux.keys()):
                    if id_local not in ids_ennemis_serveur:
                        del self.ennemis_locaux[id_local] 
                for data_ennemi in etat_ennemis_serveur:
                    id_e = data_ennemi['id']
                    if id_e not in self.ennemis_locaux:
                        self.ennemis_locaux[id_e] = Ennemi(data_ennemi['x'], data_ennemi['y'], id_e)
                    self.ennemis_locaux[id_e].set_etat(data_ennemi)
                
                ids_ames_serveur = {a['id'] for a in etat_ames_serveur}
                for id_local in list(self.ames_perdues_locales.keys()):
                    if id_local not in ids_ames_serveur:
                        del self.ames_perdues_locales[id_local] 
                for data_ame in etat_ames_serveur:
                    id_a = data_ame['id']
                    if id_a not in self.ames_perdues_locales:
                        self.ames_perdues_locales[id_a] = AmePerdue(data_ame['x'], data_ame['y'], data_ame['id_joueur'])
                    self.ames_perdues_locales[id_a].set_etat(data_ame)
                
                self.dessiner_jeu()
                if self.etat_jeu_interne == "PAUSE":
                    self.dessiner_menu_pause()
                
            except socket.error as e:
                self.etat_jeu = "MENU_PRINCIPAL" 
            except EOFError:
                self.etat_jeu = "MENU_PRINCIPAL" 
            except pickle.UnpicklingError:
                pass

            pygame.display.flip()
            self.horloge.tick(FPS)

if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()