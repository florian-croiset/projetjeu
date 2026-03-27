# boucle_jeu.py
# Mixin pour la boucle de jeu en réseau (input, rendu monde, connexion).
# Hérité par la classe Client.

import pygame
import socket
import pickle
import sys
import os
import threading
import time
import copy

from parametres import *
from utils import envoyer_logs, music
from reseau import serveur
from reseau.protocole import recv_complet, send_complet
from ui.camera import calculer_camera
from core.carte import Carte
from core.joueur import Joueur
from core.ennemi import Ennemi
from core.demon_slime_boss import DemonSlimeBoss
from core.ame_perdue import AmePerdue
from core.ame_libre import AmeLibre
from core.cle import Cle


class BoucleJeuMixin:
    """Méthodes de la boucle de jeu : boucle principale, input, rendu, réseau, connexion."""

    # ==================================================================
    #  BOUCLE PRINCIPALE DE L'APPLICATION
    # ==================================================================

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

    # ==================================================================
    #  GESTION DES ÉVÉNEMENTS EN JEU
    # ==================================================================

    def gerer_evenements_jeu(self):
        commandes = {'clavier': {'gauche': False, 'droite': False, 'saut': False, 'attaque': False, 'dash': False},
                    'echo': False, 'echo_dir': False, 'toggle_torche': False,}

        key = self._codes_touches.get

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                print("[LOG] Clic bouton detecte : envoi en cours...")
                envoyer_logs.envoyer_maintenant()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.etat_jeu_interne = "PAUSE"
                    music.pause()
                if event.key == key('attaque'):
                    commandes['clavier']['attaque'] = True
                    music.jouer_sfx('attaque')
                if event.key == key('echo'):
                    commandes['echo'] = True
                    music.jouer_sfx('echo')
                if event.key == key('dash'):
                    commandes['clavier']['dash'] = True
                    music.jouer_sfx('dash')
                if event.key == key('echo_dir'):
                    commandes['echo_dir'] = True
                    music.jouer_sfx('echo_dir')
                if event.key == pygame.K_l:
                    if self.mon_id not in self.joueurs_locaux:
                        continue
                    joueur = self.joueurs_locaux[self.mon_id]
                    vient_dallumer = self.torche.toggle()
                    if vient_dallumer:
                        music.torche_boucle_start()
                    else:
                        music.torche_boucle_stop()
                    commandes['toggle_torche'] = True
                    if vient_dallumer:
                        dx = joueur.rect.centerx - self.torche.x
                        dy = joueur.rect.centery - self.torche.y
                        if (dx**2 + dy**2)**0.5 <= DISTANCE_TORCHE_ECHO:
                            commandes['echo'] = True

        touches = pygame.key.get_pressed()
        if key('gauche') and touches[key('gauche')]:
            commandes['clavier']['gauche'] = True
        if key('droite') and touches[key('droite')]:
            commandes['clavier']['droite'] = True
        if key('saut') and touches[key('saut')]:
            commandes['clavier']['saut'] = True

        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if mon_joueur and mon_joueur.pv <= 0:
            commandes['clavier'] = {'gauche': False, 'droite': False, 'saut': False,
                                    'attaque': False, 'dash': False}
            commandes['echo'] = False
            commandes['echo_dir'] = False
            commandes['toggle_torche'] = False

        return commandes

    # ==================================================================
    #  RENDU DU MONDE DE JEU
    # ==================================================================

    def dessiner_jeu(self):
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur or not self.carte or not self.vis_map_locale:
            self.ecran.fill(COULEUR_FOND)
            return

        zoom = ZOOM_CAMERA
        lv = int(self.largeur_ecran / zoom)
        hv = int(self.hauteur_ecran / zoom)
        if not hasattr(self, '_surface_virtuelle') or self._surface_virtuelle.get_size() != (lv, hv):
            self._surface_virtuelle = pygame.Surface((lv, hv))
        surface_virtuelle = self._surface_virtuelle

        lm = self.carte.largeur_map * TAILLE_TUILE
        hm = self.carte.hauteur_map * TAILLE_TUILE
        camera_offset = calculer_camera(mon_joueur.rect,
                                        self.largeur_ecran, self.hauteur_ecran,
                                        zoom, lm, hm)

        self.carte.dessiner_carte(surface_virtuelle, self.vis_map_locale, camera_offset)

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
                pygame.draw.circle(halo, (0, 212, 255, max(0, min(255, int(80 * ratio)))), (30, 30), 30)
                surface_virtuelle.blit(halo, (cx - 30, cy - 30))
                tmp = pygame.Surface((ennemi.rect.w, ennemi.rect.h), pygame.SRCALPHA)
                tmp.fill((0, 212, 255, max(0, min(255, int(255 * ratio)))))
                surface_virtuelle.blit(tmp, (ennemi.rect.x - off_x, ennemi.rect.y - off_y))

        # Boss
        if self.boss_local and not getattr(self.boss_local, 'is_dead', False):
            off_x, off_y = camera_offset
            self.boss_local.pos.x -= off_x
            self.boss_local.pos.y -= off_y
            self.boss_local.draw(surface_virtuelle)
            self.boss_local.pos.x += off_x
            self.boss_local.pos.y += off_y

        if mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        for ame in self.ames_perdues_locales.values():
            ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        for ame in self.ames_libres_locales.values():
            ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        if self.cle_locale and not self.cle_locale.est_ramassee:
            self.cle_locale.dessiner(surface_virtuelle, camera_offset, temps_ms)

        self.torche.mettre_a_jour(temps_ms)
        self.torche.dessiner(surface_virtuelle, camera_offset, temps_ms)

        if self.torche.allumee and mon_joueur:
            dx = mon_joueur.rect.centerx - self.torche.x
            dy = mon_joueur.rect.centery - self.torche.y
            dist = (dx**2 + dy**2) ** 0.5
            music.torche_mettre_a_jour_volume(dist)

        # Calque obscurité avec halo
        if mon_joueur and ASSOMBRISSEMENT:
            sz = surface_virtuelle.get_size()
            if not hasattr(self, '_obscurite') or self._obscurite.get_size() != sz:
                self._obscurite = pygame.Surface(sz, pygame.SRCALPHA)
            obscurite = self._obscurite
            obscurite.fill((0, 0, 10, 220))

            rayon = RAYON_HALO_JOUEUR
            cx = mon_joueur.rect.centerx - camera_offset[0]
            cy = mon_joueur.rect.centery - camera_offset[1]
            obscurite.blit(self._masque_halo_joueur,
                           (cx - rayon - 1, cy - rayon - 1),
                           special_flags=pygame.BLEND_RGBA_MIN)

            if self.torche.allumee:
                rayon_t = RAYON_LUMIERE_TORCHE
                tx = self.torche.x + TAILLE_TUILE // 2 - camera_offset[0]
                ty = self.torche.y + TAILLE_TUILE - camera_offset[1]
                obscurite.blit(self._masque_halo_torche,
                               (tx - rayon_t - 1, ty - rayon_t - 1),
                               special_flags=pygame.BLEND_RGBA_MIN)

            surface_virtuelle.blit(obscurite, (0, 0))

        if mon_joueur and mon_joueur.pv <= 0:
            if self._mort_depuis is None:
                music.jouer_sfx('mort')
            self._dessiner_ecran_mort(surface_virtuelle)
        elif mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        surface_zoomee = pygame.transform.scale(
            surface_virtuelle, (self.largeur_ecran, self.hauteur_ecran))
        self.ecran.blit(surface_zoomee, (0, 0))

        if MODE_DEV:
            btn = envoyer_logs.get_bouton()
            btn.rect.topleft = (self.largeur_ecran - 175, 140)
            btn.verifier_survol(pygame.mouse.get_pos())
            btn.dessiner(self.ecran)

        self.dessiner_hud()

    # ==================================================================
    #  BOUCLE JEU RÉSEAU
    # ==================================================================

    def boucle_jeu_reseau(self):
        if not self.client_socket:
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        music.demarrer()

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
                send_complet(self.client_socket, commandes_a_envoyer)
                donnees_recues = recv_complet(self.client_socket)

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

                mon_joueur_local = self.joueurs_locaux.get(self.mon_id)
                if mon_joueur_local:
                    for nom_son in mon_joueur_local.sons_a_jouer:
                        music.jouer_sfx(nom_son)
                    mon_joueur_local.sons_a_jouer.clear()

                ids_e = {e['id'] for e in donnees_recues['ennemis']}
                for id_local in list(self.ennemis_locaux.keys()):
                    if id_local not in ids_e:
                        del self.ennemis_locaux[id_local]
                for de in donnees_recues['ennemis']:
                    if de['id'] not in self.ennemis_locaux:
                        self.ennemis_locaux[de['id']] = Ennemi(de['x'], de['y'], de['id'])
                    self.ennemis_locaux[de['id']].set_etat(de)

                for ennemi_local in self.ennemis_locaux.values():
                    for nom_son in ennemi_local.sons_a_jouer:
                        music.jouer_sfx(nom_son)
                    ennemi_local.sons_a_jouer.clear()

                ids_a = {a['id'] for a in donnees_recues.get('ames_perdues', [])}
                for id_local in list(self.ames_perdues_locales.keys()):
                    if id_local not in ids_a:
                        del self.ames_perdues_locales[id_local]
                for da in donnees_recues.get('ames_perdues', []):
                    if da['id'] not in self.ames_perdues_locales:
                        self.ames_perdues_locales[da['id']] = AmePerdue(
                            da['x'], da['y'], da['id_joueur'])
                    self.ames_perdues_locales[da['id']].set_etat(da)

                ids_al = {a['id'] for a in donnees_recues.get('ames_libres', [])}
                for id_local in list(self.ames_libres_locales.keys()):
                    if id_local not in ids_al:
                        del self.ames_libres_locales[id_local]
                for dal in donnees_recues.get('ames_libres', []):
                    if dal['id'] not in self.ames_libres_locales:
                        self.ames_libres_locales[dal['id']] = AmeLibre(dal['x'], dal['y'], dal.get('valeur'))
                    self.ames_libres_locales[dal['id']].set_etat(dal)

                # Boss
                data_boss = donnees_recues.get('boss_room')
                if data_boss and not data_boss['boss_defeated']:
                    if self.boss_local is None:
                        _base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                        self.boss_local = DemonSlimeBoss(x=0, y=0,json_path=os.path.join(_base, "demon_slime.json"),png_path=os.path.join(_base, "assets", "demon_slime.png"))
                        self.boss_local.set_etat(data_boss['boss'])

                # Clé
                data_cle = donnees_recues.get('cle')
                if data_cle:
                    if self.cle_locale is None:
                        self.cle_locale = Cle(data_cle['x'], data_cle['y'])
                    self.cle_locale.set_etat(data_cle)

                # Torche
                torche_serveur = donnees_recues.get('torche_allumee', False)
                if torche_serveur != self.torche.allumee:
                    self.torche.allumee = torche_serveur
                    if torche_serveur:
                        self.torche.particules = []

                # Boss (état pour HUD)
                self._derniere_data_boss = donnees_recues.get('boss_room')
                data_boss = self._derniere_data_boss
                if data_boss and not data_boss['boss_defeated']:
                    if self.boss_local is None:
                        _base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                        self.boss_local = DemonSlimeBoss(x=0, y=0,
                                json_path=os.path.join(_base, "demon_slime.json"),
                                png_path=os.path.join(_base, "assets", "demon_slime.png"))
                    self.boss_local.set_etat(data_boss['boss'])

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
            except (pickle.UnpicklingError,) as e:
                print(f"[CLIENT] Paquet corrompu ignoré: {e}")
            except ValueError as e:
                print(f"[CLIENT] Erreur valeur (probablement Pygame): {e}")
                import traceback; traceback.print_exc()

            pygame.display.flip()
            self.horloge.tick(FPS)

    # ==================================================================
    #  LANCEMENT ET CONNEXION
    # ==================================================================

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement = "nouvelle" if est_nouvelle_partie else "charger"
        print(f"[CLIENT] Demarrage serveur local (slot {id_slot}, {type_lancement})")
        thread_serveur = threading.Thread(
            target=serveur.main,
            args=(id_slot, type_lancement),
            daemon=True
        )
        thread_serveur.start()
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
            self.client_socket.settimeout(5)
            print(f"[CLIENT] Connexion a {hote}:{PORT_SERVEUR}...")
            self.client_socket.connect((hote, PORT_SERVEUR))
            self.client_socket.settimeout(10.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs connectés)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = reponse
            self.message_erreur_connexion = None

            if getattr(sys, 'frozen', False):
                dossier_script = sys._MEIPASS
            else:
                dossier_script = os.path.dirname(os.path.abspath(__file__))
            chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
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
        self.joueurs_locaux = {}
        self.ennemis_locaux = {}
        self.ames_perdues_locales = {}
        self.ames_libres_locales = {}
        self.cle_locale  = None
        self.carte = None
        self.vis_map_locale = None
        self.etat_jeu_interne = "JEU"
