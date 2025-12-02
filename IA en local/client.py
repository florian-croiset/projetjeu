# client.py
# Le VISUEL du jeu. À lancer par TOUS les joueurs (hôte compris).
# Gère le menu principal, les paramètres, et la connexion au serveur.

import pygame
import socket
import pickle
import sys
import subprocess # Pour lancer le serveur en sous-processus
import time
import copy # Pour copier les dictionnaires de paramètres
import os # <-- AJOUTÉ POUR TROUVER LE CHEMIN ABSOLU

from parametres import *
from carte import Carte
from joueur import Joueur # Utilisé seulement pour créer des "fantômes"
from ennemi import Ennemi # Import pour créer les "fantômes" ennemis
from ame_perdue import AmePerdue # Import de la nouvelle classe
import gestion_parametres
import langue # Notre nouveau module de langue
from bouton import Bouton
import gestion_sauvegarde # Notre nouveau module de sauvegarde

class Client:
    def __init__(self):
        # 1. Initialisation de Pygame et des paramètres
        pygame.init()
        self.parametres = gestion_parametres.charger_parametres()
        
        # Appliquer la langue
        langue.set_langue(self.parametres['jouabilite']['langue'])
        
        # Appliquer les paramètres vidéo
        self.largeur_ecran = LARGEUR_ECRAN
        self.hauteur_ecran = HAUTEUR_ECRAN
        self.appliquer_parametres_video(premiere_fois=True) # Crée self.ecran
        
        pygame.display.set_caption(langue.get_texte("titre_jeu"))
        
        self.horloge = pygame.time.Clock()
        
        # 2. Gestion des états du jeu
        # (MENU_PRINCIPAL, MENU_PARAMETRES, MENU_REJOINDRE, EN_JEU, QUITTER,
        #  MENU_NOUVELLE_PARTIE, MENU_CONTINUER)
        self.etat_jeu = "MENU_PRINCIPAL" 
        self.etat_jeu_precedent = "MENU_PRINCIPAL" # Pour savoir où retourner depuis les paramètres
        self.etat_jeu_interne = "JEU" # Sous-état pour EN_JEU: "JEU" ou "PAUSE"
        self.running = True

        # 3. Éléments Réseau (seront initialisés plus tard)
        self.client_socket = None
        self.mon_id = -1
        
        # 4. Éléments de Jeu (seront initialisés au lancement)
        self.carte = None
        self.vis_map_locale = None
        self.joueurs_locaux = {}
        self.ennemis_locaux = {} # Dico {id: objet Ennemi}
        self.ames_perdues_locales = {} # Dico {id: objet AmePerdue}

        # 5. Éléments des Menus
        self.police_titre = pygame.font.Font(None, 72)
        self.police_bouton = pygame.font.Font(None, 40)
        self.police_texte = pygame.font.Font(None, 32)
        
        # Variables pour le menu paramètres
        self.parametres_temp = {} # Copie pour les modifs non appliquées
        self.touche_a_modifier = None # Stocke la clé du contrôle en attente
        
        self.creer_widgets_menu_principal()
        self.creer_widgets_menu_rejoindre()
        self.creer_widgets_menu_parametres()
        self.creer_widgets_menu_pause()
        self.creer_widgets_menu_slots() # Pour "Nouvelle" et "Continuer"

    def appliquer_parametres_video(self, premiere_fois=False):
        """Applique les paramètres vidéo (plein écran)"""
        flags = pygame.SCALED
        if self.parametres['video']['plein_ecran']:
            flags |= pygame.FULLSCREEN
        
        # Si ce n'est pas la première fois, on recrée l'écran
        # Si c'est la première fois, on le crée simplement
        self.ecran = pygame.display.set_mode((self.largeur_ecran, self.hauteur_ecran), flags)
        print(f"Paramètres vidéo appliqués: Plein écran={self.parametres['video']['plein_ecran']}")

    def creer_widgets_menu_principal(self):
        """Crée les boutons du menu principal."""
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
        """Crée les widgets pour le menu "Rejoindre"."""
        cx = self.largeur_ecran // 2
        self.input_box_ip = pygame.Rect(cx - 200, 300, 400, 50)
        self.input_ip_texte = ""
        self.input_ip_actif = False
        self.btn_connecter = Bouton(cx - 200, 370, 400, 50, langue.get_texte("rejoindre_connecter"), self.police_bouton)
        self.btn_retour_rejoindre = Bouton(cx - 200, 440, 400, 50, langue.get_texte("rejoindre_retour"), self.police_bouton)

    def creer_widgets_menu_parametres(self):
        """Crée les widgets pour le menu des paramètres."""
        self.widgets_parametres = {}
        cx = self.largeur_ecran // 2
        col_gauche_label = 100
        col_droite_bouton = cx + 50
        largeur_btn_param = 300
        
        # --- Vidéo ---
        y_video = 250
        self.btn_toggle_plein_ecran = Bouton(col_droite_bouton, y_video, largeur_btn_param, 40, "", self.police_texte)
        
        # --- Contrôles ---
        y_controles = 400
        self.btn_changer_gauche = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_droite = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_saut = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)
        y_controles += 50
        self.btn_changer_echo = Bouton(col_droite_bouton, y_controles, largeur_btn_param, 40, "", self.police_texte)

        # --- Boutons de navigation ---
        self.btn_appliquer_params = Bouton(cx - 320, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_appliquer"), self.police_bouton)
        self.btn_retour_params = Bouton(cx + 20, self.hauteur_ecran - 100, 300, 50, langue.get_texte("param_retour"), self.police_bouton)

        # Regrouper tous les boutons cliquables
        self.boutons_menu_params = [
            self.btn_toggle_plein_ecran,
            self.btn_changer_gauche, self.btn_changer_droite,
            self.btn_changer_saut, self.btn_changer_echo,
            self.btn_appliquer_params, self.btn_retour_params
        ]

    def creer_widgets_menu_pause(self):
        """Crée les boutons du menu pause."""
        cx = self.largeur_ecran // 2
        largeur_btn = 400
        
        self.btn_pause_reprendre = Bouton(cx - largeur_btn//2, 250, largeur_btn, 50, langue.get_texte("pause_reprendre"), self.police_bouton)
        self.btn_pause_parametres = Bouton(cx - largeur_btn//2, 320, largeur_btn, 50, langue.get_texte("pause_parametres"), self.police_bouton)
        
        # Nouveau bouton pour "Activer Multi" (sera fonctionnel plus tard)
        self.btn_pause_activer_multi = Bouton(cx - largeur_btn//2, 390, largeur_btn, 50, "Activer Multijoueur (Bientôt)", self.police_bouton)
        self.btn_pause_activer_multi.couleur_fond = (40, 40, 40) # Grisé
        
        self.btn_pause_quitter = Bouton(cx - largeur_btn//2, 460, largeur_btn, 50, langue.get_texte("pause_quitter_session"), self.police_bouton) 
        
        self.boutons_menu_pause = [self.btn_pause_reprendre, self.btn_pause_parametres, self.btn_pause_activer_multi, self.btn_pause_quitter]
        
        # Surface pour l'effet d'assombrissement
        self.surface_fond_pause = pygame.Surface((self.largeur_ecran, self.hauteur_ecran), pygame.SRCALPHA)
        self.surface_fond_pause.fill(COULEUR_FOND_PAUSE)

    def creer_widgets_menu_slots(self):
        """Crée les widgets réutilisables pour les menus Nouvelle/Continuer."""
        self.infos_slots = []
        self.boutons_slots = []
        
        cx = self.largeur_ecran // 2
        largeur_btn_slot = self.largeur_ecran * 0.7 # 70% de la largeur
        y_start = 250
        
        for i in range(NB_SLOTS_SAUVEGARDE):
            # Le texte sera mis à jour dynamiquement
            btn = Bouton(cx - largeur_btn_slot//2, y_start + (i * 100), largeur_btn_slot, 80, f"Slot {i+1}", self.police_bouton)
            self.boutons_slots.append(btn)
            
        self.btn_retour_slots = Bouton(cx - 200, y_start + (NB_SLOTS_SAUVEGARDE * 100) + 20, 400, 50, langue.get_texte("rejoindre_retour"), self.police_bouton)

    # --- GESTION DES MENUS ---

    def lancer_application(self):
        """Boucle principale de l'application qui gère les états."""
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
                # Si on entre dans le menu, on crée une copie des paramètres
                if not self.parametres_temp:
                    self.parametres_temp = copy.deepcopy(self.parametres)
                
                self.gerer_menu_parametres(pos_souris)
                self.dessiner_menu_parametres()
                
            elif self.etat_jeu == "LANCEMENT_SERVEUR":
                # Cet état n'est plus utilisé, voir lancer_partie_locale
                print("ERREUR: Etat LANCEMENT_SERVEUR ne devrait pas être atteint.")
                self.etat_jeu = "MENU_PRINCIPAL"

            elif self.etat_jeu == "EN_JEU":
                # Si on n'est pas en "pause", on commence en mode "jeu"
                if self.etat_jeu_interne != "PAUSE":
                    self.etat_jeu_interne = "JEU" 
                
                self.boucle_jeu_reseau() # Lance la boucle de jeu
                
                # La boucle_jeu_reseau s'est terminée. Vérifions pourquoi.
                
                if self.etat_jeu == "MENU_PARAMETRES":
                    # L'utilisateur a cliqué sur Paramètres depuis le menu pause.
                    # On ne nettoie pas la connexion, on se souvient d'où on vient.
                    self.etat_jeu_precedent = "EN_JEU"
                    self.parametres_temp = copy.deepcopy(self.parametres)
                    # La boucle va naturellement passer à l'état MENU_PARAMETRES

                elif self.etat_jeu == "EN_JEU":
                    # Cas où on est dans les paramètres-pause et on clique "Appliquer" ou "Retour"
                    # On ne fait rien, la boucle va relancer boucle_jeu_reseau
                    pass

                else:
                    # L'utilisateur a quitté (déco, ou bouton "Quitter")
                    # On nettoie tout et on retourne au menu principal
                    self.etat_jeu = "MENU_PRINCIPAL"
                    self.nettoyer_connexion()
                    # On réinitialise les widgets au cas où la langue a changé
                    self.actualiser_langues_widgets()

            elif self.etat_jeu == "QUITTER":
                self.running = False
            
            pygame.display.flip()
            self.horloge.tick(FPS)
            
        pygame.quit()
        sys.exit()

    def actualiser_langues_widgets(self):
        """Met à jour le texte de tous les widgets après un changement de langue."""
        langue.set_langue(self.parametres['jouabilite']['langue'])
        pygame.display.set_caption(langue.get_texte("titre_jeu"))

        # Menu Principal
        self.btn_nouvelle_partie.texte = langue.get_texte("menu_nouvelle_partie")
        self.btn_continuer.texte = langue.get_texte("menu_continuer")
        self.btn_rejoindre.texte = langue.get_texte("menu_rejoindre")
        self.btn_parametres.texte = langue.get_texte("menu_parametres")
        self.btn_quitter.texte = langue.get_texte("menu_quitter")
        
        # Menu Rejoindre
        self.btn_connecter.texte = langue.get_texte("rejoindre_connecter")
        self.btn_retour_rejoindre.texte = langue.get_texte("rejoindre_retour")
        
        # Menu Paramètres
        self.btn_appliquer_params.texte = langue.get_texte("param_appliquer")
        self.btn_retour_params.texte = langue.get_texte("param_retour")
        
        # Menu Pause
        self.btn_pause_reprendre.texte = langue.get_texte("pause_reprendre")
        self.btn_pause_parametres.texte = langue.get_texte("pause_parametres")
        # self.btn_pause_activer_multi.texte = ... (plus tard)
        # Le texte du bouton quitter est géré dynamiquement dans boucle_jeu_reseau

    def gerer_menu_principal(self, pos_souris):
        """Gère les événements du menu principal."""
        for bouton in self.boutons_menu_principal:
            bouton.verifier_survol(pos_souris)
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"
            
            if self.btn_nouvelle_partie.verifier_clic(event):
                self.etat_jeu = "MENU_NOUVELLE_PARTIE"
                self.infos_slots = gestion_sauvegarde.get_infos_slots() # Charger les infos
            if self.btn_continuer.verifier_clic(event):
                self.etat_jeu = "MENU_CONTINUER"
                self.infos_slots = gestion_sauvegarde.get_infos_slots() # Charger les infos
            if self.btn_rejoindre.verifier_clic(event):
                self.etat_jeu = "MENU_REJOINDRE"
            if self.btn_parametres.verifier_clic(event):
                # On crée la copie des paramètres en entrant dans le menu
                self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu_precedent = "MENU_PRINCIPAL" # On vient du menu principal
                self.etat_jeu = "MENU_PARAMETRES"
            if self.btn_quitter.verifier_clic(event):
                self.etat_jeu = "QUITTER"

    def dessiner_menu_principal(self):
        """Dessine le menu principal."""
        self.ecran.fill(COULEUR_FOND)
        titre_surface = self.police_titre.render(langue.get_texte("titre_jeu"), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 120)) # Remonté
        self.ecran.blit(titre_surface, titre_rect)
        
        for bouton in self.boutons_menu_principal:
            bouton.dessiner(self.ecran)

    def gerer_menu_rejoindre(self, pos_souris):
        """Gère les événements du menu rejoindre (saisie IP)."""
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
                    # On pourrait afficher un message d'erreur ici
            
            # Gestion de la saisie au clavier pour l'IP
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
        """Dessine le menu pour rejoindre une partie."""
        self.ecran.fill(COULEUR_FOND)
        
        # Titre
        titre_surface = self.police_titre.render(langue.get_texte("rejoindre_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre_surface, titre_surface.get_rect(center=(self.largeur_ecran // 2, 150)))
        
        # Label
        label_surface = self.police_texte.render(langue.get_texte("rejoindre_label_ip"), True, COULEUR_TEXTE)
        self.ecran.blit(label_surface, label_surface.get_rect(center=(self.largeur_ecran // 2, 250)))

        # Input Box
        pygame.draw.rect(self.ecran, COULEUR_INPUT_BOX, self.input_box_ip, border_radius=5)
        texte_ip_surface = self.police_texte.render(self.input_ip_texte, True, COULEUR_TEXTE)
        self.ecran.blit(texte_ip_surface, (self.input_box_ip.x + 10, self.input_box_ip.y + 10))
        # Curseur simple
        if self.input_ip_actif and int(time.time() * 2) % 2 == 0:
            curseur_rect = pygame.Rect(self.input_box_ip.x + 12 + texte_ip_surface.get_width(), self.input_box_ip.y + 10, 3, self.police_texte.get_height() - 10)
            pygame.draw.rect(self.ecran, COULEUR_TEXTE, curseur_rect)

        # Boutons
        self.btn_connecter.dessiner(self.ecran)
        self.btn_retour_rejoindre.dessiner(self.ecran)

    def gerer_menu_slots(self, pos_souris):
        """Gère les clics dans les menus Nouvelle Partie et Continuer."""
        
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
                        # TODO: Ajouter confirmation si slot non vide
                        print(f"Lancement nouvelle partie, Slot {id_slot + 1}")
                        self.lancer_partie_locale(id_slot, est_nouvelle_partie=True)
                        
                    elif self.etat_jeu == "MENU_CONTINUER":
                        if not self.infos_slots[id_slot]["est_vide"]:
                            print(f"Chargement partie, Slot {id_slot + 1}")
                            self.lancer_partie_locale(id_slot, est_nouvelle_partie=False)
                        else:
                            print("Slot vide, ne peut pas charger.")
                            # On pourrait griser le bouton

    def dessiner_menu_slots(self):
        """Dessine l'écran de sélection des slots."""
        self.ecran.fill(COULEUR_FOND)
        
        # Titre dynamique
        titre_cle = "slots_titre_nouvelle" if self.etat_jeu == "MENU_NOUVELLE_PARTIE" else "slots_titre_continuer"
        titre_surface = self.police_titre.render(langue.get_texte(titre_cle), True, COULEUR_TITRE)
        titre_rect = titre_surface.get_rect(center=(self.largeur_ecran // 2, 120))
        self.ecran.blit(titre_surface, titre_rect)

        # Dessiner les boutons de slot
        for id_slot, bouton_slot in enumerate(self.boutons_slots):
            info = self.infos_slots[id_slot]
            
            # Personnaliser l'apparence du bouton
            if self.etat_jeu == "MENU_CONTINUER" and info["est_vide"]:
                bouton_slot.couleur_fond = (30, 30, 30) # Grisé
                bouton_slot.couleur_texte = (100, 100, 100)
            else:
                bouton_slot.couleur_fond = COULEUR_BOUTON
                bouton_slot.couleur_texte = COULEUR_TEXTE
            
            # Mettre à jour le texte du bouton (Nom + Description)
            bouton_slot.texte = info["nom"]
            bouton_slot.dessiner(self.ecran)
            
            # Ajouter la description sous le nom du slot
            desc_surface = self.police_texte.render(info["description"], True, COULEUR_TEXTE)
            desc_rect = desc_surface.get_rect(center=(bouton_slot.rect.centerx, bouton_slot.rect.centery + 20))
            self.ecran.blit(desc_surface, desc_rect)

        self.btn_retour_slots.dessiner(self.ecran)

    def gerer_menu_parametres(self, pos_souris):
        """Gère les événements du menu des paramètres."""
        
        for bouton in self.boutons_menu_params:
            bouton.verifier_survol(pos_souris)
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.etat_jeu = "QUITTER"

            # --- CAS 1: On est en train d'attendre une touche ---
            if self.touche_a_modifier:
                if event.type == pygame.KEYDOWN:
                    # On ignore les touches "sensibles" (ex: echap)
                    if event.key not in [pygame.K_ESCAPE, pygame.K_RETURN]:
                        nom_touche = pygame.key.name(event.key)
                        self.parametres_temp['controles'][self.touche_a_modifier] = nom_touche
                        self.touche_a_modifier = None # On quitte le mode attente
            
            # --- CAS 2: On gère les clics de souris normaux ---
            else:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.parametres_temp = {} # Annuler les changements
                        self.etat_jeu = self.etat_jeu_precedent # Retourne d'où on vient
                
                # Clic sur "Retour"
                if self.btn_retour_params.verifier_clic(event):
                    self.parametres_temp = {} # Annuler les changements
                    self.touche_a_modifier = None
                    self.etat_jeu = self.etat_jeu_precedent # Retourne d'où on vient
                
                # Clic sur "Appliquer"
                if self.btn_appliquer_params.verifier_clic(event):
                    # 1. Sauvegarder les changements
                    self.parametres = copy.deepcopy(self.parametres_temp)
                    gestion_parametres.sauvegarder_parametres(self.parametres)
                    # 2. Appliquer les changements (vidéo, langue)
                    self.appliquer_parametres_video()
                    self.actualiser_langues_widgets() # Met à jour tous les textes
                    # 3. Quitter le menu
                    self.touche_a_modifier = None
                    self.etat_jeu = self.etat_jeu_precedent # Retourne d'où on vient

                # Clic sur "Plein écran" (toggle)
                if self.btn_toggle_plein_ecran.verifier_clic(event):
                    self.parametres_temp['video']['plein_ecran'] = not self.parametres_temp['video']['plein_ecran']

                # Clics sur les boutons "Changer"
                if self.btn_changer_gauche.verifier_clic(event):
                    self.touche_a_modifier = "gauche"
                if self.btn_changer_droite.verifier_clic(event):
                    self.touche_a_modifier = "droite"
                if self.btn_changer_saut.verifier_clic(event):
                    self.touche_a_modifier = "saut"
                if self.btn_changer_echo.verifier_clic(event):
                    self.touche_a_modifier = "echo"

    def dessiner_menu_parametres(self):
        """Dessine le menu des paramètres."""
        self.ecran.fill(COULEUR_FOND)
        
        # Titre
        titre_surface = self.police_titre.render(langue.get_texte("param_titre"), True, COULEUR_TITRE)
        self.ecran.blit(titre_surface, titre_surface.get_rect(center=(self.largeur_ecran // 2, 80)))

        # --- Section Vidéo ---
        y_offset = 200
        titre_section = self.police_bouton.render(langue.get_texte("param_section_video"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_offset))
        y_offset += 60
        
        # Option Plein écran
        label_plein_ecran = self.police_texte.render(langue.get_texte("param_plein_ecran"), True, COULEUR_TEXTE)
        self.ecran.blit(label_plein_ecran, (120, y_offset + 5))
        
        # Sécurité au cas où on quitte et parametres_temp est vidé
        params = self.parametres_temp if self.parametres_temp else self.parametres
        
        texte_btn_plein_ecran = langue.get_texte("param_oui") if params['video']['plein_ecran'] else langue.get_texte("param_non")
        self.btn_toggle_plein_ecran.texte = texte_btn_plein_ecran
        self.btn_toggle_plein_ecran.dessiner(self.ecran)

        # --- Section Contrôles ---
        y_offset = 350
        titre_section = self.police_bouton.render(langue.get_texte("param_section_controles"), True, COULEUR_TITRE)
        self.ecran.blit(titre_section, (100, y_offset))
        y_offset += 60
        
        # Touche Gauche
        label_gauche = self.police_texte.render(langue.get_texte("param_gauche"), True, COULEUR_TEXTE)
        self.ecran.blit(label_gauche, (120, y_offset + 5))
        texte_btn_gauche = params['controles']['gauche'].upper()
        if self.touche_a_modifier == "gauche":
            texte_btn_gauche = langue.get_texte("param_attente_touche")
        self.btn_changer_gauche.texte = texte_btn_gauche
        self.btn_changer_gauche.dessiner(self.ecran)
        y_offset += 50
        
        # Touche Droite
        label_droite = self.police_texte.render(langue.get_texte("param_droite"), True, COULEUR_TEXTE)
        self.ecran.blit(label_droite, (120, y_offset + 5))
        texte_btn_droite = params['controles']['droite'].upper()
        if self.touche_a_modifier == "droite":
            texte_btn_droite = langue.get_texte("param_attente_touche")
        self.btn_changer_droite.texte = texte_btn_droite
        self.btn_changer_droite.dessiner(self.ecran)
        y_offset += 50

        # Touche Saut
        label_saut = self.police_texte.render(langue.get_texte("param_saut"), True, COULEUR_TEXTE)
        self.ecran.blit(label_saut, (120, y_offset + 5))
        texte_btn_saut = params['controles']['saut'].upper()
        if self.touche_a_modifier == "saut":
            texte_btn_saut = langue.get_texte("param_attente_touche")
        self.btn_changer_saut.texte = texte_btn_saut
        self.btn_changer_saut.dessiner(self.ecran)
        y_offset += 50
        
        # Touche Écho
        label_echo = self.police_texte.render(langue.get_texte("param_echo"), True, COULEUR_TEXTE)
        self.ecran.blit(label_echo, (120, y_offset + 5))
        texte_btn_echo = params['controles']['echo'].upper()
        if self.touche_a_modifier == "echo":
            texte_btn_echo = langue.get_texte("param_attente_touche")
        self.btn_changer_echo.texte = texte_btn_echo
        self.btn_changer_echo.dessiner(self.ecran)
        
        # Boutons Appliquer / Retour
        self.btn_appliquer_params.dessiner(self.ecran)
        self.btn_retour_params.dessiner(self.ecran)

    # --- GESTION DU RÉSEAU ET DU JEU ---

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        """Lance le serveur local ET s'y connecte."""
        
        # 1. Lancer le serveur en arrière-plan avec les bons arguments
        type_lancement = "nouvelle" if est_nouvelle_partie else "charger"
        print(f"[CLIENT] Lancement du serveur local (Slot {id_slot}, Type: {type_lancement})...")
        
        try:
            # --- CORRECTION [Errno 2] ---
            # On construit le chemin absolu vers le script serveur
            # __file__ est le chemin de ce script (client.py)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            serveur_path = os.path.join(script_dir, 'serveur.py')
            
            # 'sys.executable' est le chemin vers l'interpréteur Python actuel
            # On utilise maintenant le chemin absolu vers 'serveur.py'
            commande_lancement = [sys.executable, serveur_path, str(id_slot), type_lancement]
            print(f"[CLIENT] Exécution de: {' '.join(commande_lancement)}")
            
            self.processus_serveur = subprocess.Popen(commande_lancement)
            # --- FIN CORRECTION ---
            
            print("[CLIENT] Serveur démarré en arrière-plan.")
            time.sleep(2) # Laisse 2 secondes au serveur pour démarrer
        
        except FileNotFoundError as e: # Erreur spécifique
            print(f"[CLIENT] ERREUR CRITIQUE: Impossible de lancer 'serveur.py' ou 'python'.")
            print(f"Erreur: {e}")
            if 'serveur_path' in locals():
                print(f"Tentative de lancement: {sys.executable} {serveur_path}")
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        except Exception as e:
            print(f"[CLIENT] Erreur inconnue lors du lancement du serveur: {e}")
            self.etat_jeu = "MENU_PRINCIPAL"
            return
            
        # 2. Se connecter au serveur (en tant qu'hôte 'localhost')
        if self.connecter("localhost"):
            self.etat_jeu = "EN_JEU"
        else:
            print("[CLIENT] Erreur: Le serveur local n'a pas pu être rejoint.")
            print("[CLIENT] Assurez-vous que le serveur n'est pas bloqué par un pare-feu.")
            self.etat_jeu = "MENU_PRINCIPAL" # Retour au menu

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
            
            # Recevoir son ID
            self.mon_id = pickle.loads(self.client_socket.recv(2048))
            print(f"[CLIENT] Connecté avec succès. Mon ID est {self.mon_id}")
            
            # Initialiser les éléments de jeu
            self.carte = Carte()
            self.vis_map_locale = self.carte.creer_carte_visibilite_vierge()
            self.joueurs_locaux = {}
            self.ennemis_locaux = {}
            self.ames_perdues_locales = {}
            
            return True
        except socket.error as e:
            print(f"[CLIENT] Échec de la connexion: {e}")
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
        commandes_clavier = {'gauche': False, 'droite': False, 'saut': False}
        declencher_echo = False
        
        # Récupérer les codes de touches depuis les paramètres
        try:
            touche_gauche = pygame.key.key_code(self.parametres['controles']['gauche'])
            touche_droite = pygame.key.key_code(self.parametres['controles']['droite'])
            touche_saut = pygame.key.key_code(self.parametres['controles']['saut'])
            touche_echo = pygame.key.key_code(self.parametres['controles']['echo'])
        except Exception as e:
            print(f"Erreur de mapping des touches: {e}. Utilisation des touches par défaut.")
            # Fallback (au cas où les noms dans le JSON sont mauvais)
            touche_gauche, touche_droite, touche_saut, touche_echo = pygame.K_q, pygame.K_d, pygame.K_SPACE, pygame.K_e


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False # Arrête toute l'application
                self.etat_jeu = "QUITTER" # Force la sortie de la boucle jeu
            
            if event.type == pygame.KEYDOWN:
                # Gérer l'écho (appui unique)
                if event.key == touche_echo:
                    declencher_echo = True
                # Menu Pause
                if event.key == pygame.K_ESCAPE:
                    print("[CLIENT] Passage en mode Pause")
                    self.etat_jeu_interne = "PAUSE"
                    # On retourne des commandes vides pour ce tick
                    return {'clavier': {'gauche': False, 'droite': False, 'saut': False}, 'echo': False}
        
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

        # TODO: Dessiner le cooldown de l'écho

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
            commandes_a_envoyer = {'clavier': {'gauche': False, 'droite': False, 'saut': False}, 'echo': False}
            
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
                # Gérer le cas où les données reçues sont incomplètes ou mal formées
                pass

            # Le flip est maintenant géré ici, car le dessin est complexe
            pygame.display.flip()
            self.horloge.tick(FPS)

# --- Point d'entrée ---
if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()