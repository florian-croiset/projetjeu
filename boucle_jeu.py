# boucle_jeu.py
# Mixin pour la boucle de jeu en réseau (input, rendu monde, connexion).
# MISE À JOUR : Rendu Porte interactive + Orbes de capacités.

from ui.tutoriel import Tutoriel
from sauvegarde import gestion_parametres

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
from reseau.relay_server import demarrer_relay_thread
from reseau.protocole import recv_complet, send_complet
from ui.camera import calculer_camera
from core.carte import Carte
from core.joueur import Joueur
from core.ennemi import Ennemi
from core.demon_slime_boss import DemonSlimeBoss
from core.ame_perdue import AmePerdue
from core.ame_libre import AmeLibre
from core.ame_loot import AmeLoot
from core.cle import Cle
from core.porte import Porte
from core.orbe_capacite import OrbeCapacite


class BoucleJeuMixin:
    """Méthodes de la boucle de jeu : boucle principale, input, rendu, réseau, connexion."""

    # ==================================================================
    #  BOUCLE PRINCIPALE DE L'APPLICATION
    # ==================================================================

    def lancer_application(self):
        if not self.parametres.get("meta", {}).get("tutoriel_vu", False):
            tuto = Tutoriel(
                self.ecran, self.largeur_ecran, self.hauteur_ecran,
                self.parametres['controles'],
                self.police_titre, self.police_texte,
                self.police_bouton, self.police_petit
            )
            tuto.lancer()
            self.parametres.setdefault("meta", {})["tutoriel_vu"] = True
            gestion_parametres.sauvegarder_parametres(self.parametres)

        while self.running:
            self.temps_anim = pygame.time.get_ticks()
            pos_souris      = pygame.mouse.get_pos()

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
                    self.parametres_temp    = copy.deepcopy(self.parametres)
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
        commandes = {
            'clavier':        {'gauche': False, 'droite': False,
                               'saut': False, 'attaque': False, 'dash': False},
            'echo':           False,
            'echo_dir':       False,
            'toggle_torche':  False,
        }

        key = self._codes_touches.get

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
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
            commandes['clavier']       = {'gauche': False, 'droite': False,
                                          'saut': False, 'attaque': False, 'dash': False}
            commandes['echo']          = False
            commandes['echo_dir']      = False
            commandes['toggle_torche'] = False

        return commandes

    # ==================================================================
    #  RENDU DU MONDE DE JEU
    # ==================================================================

    def dessiner_jeu(self):
        self._init_hud_cache()
        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if not mon_joueur or not self.carte or not self.vis_map_locale:
            self.ecran.fill(COULEUR_FOND)
            return

        zoom = self.zoom_effectif
        lv   = int(self.largeur_ecran / zoom)
        hv   = int(self.hauteur_ecran / zoom)
        if not hasattr(self, '_surface_virtuelle') or self._surface_virtuelle.get_size() != (lv, hv):
            self._surface_virtuelle = pygame.Surface((lv, hv))
        surface_virtuelle = self._surface_virtuelle

        lm = self.carte.largeur_map * TAILLE_TUILE
        hm = self.carte.hauteur_map * TAILLE_TUILE
        camera_offset = calculer_camera(mon_joueur.rect,
                                        self.largeur_ecran, self.hauteur_ecran,
                                        zoom, lm, hm)

        self.carte.dessiner_carte(surface_virtuelle, self.vis_map_locale, camera_offset)

        # --- Porte ---
        if self.porte_locale:
            self.porte_locale.dessiner(surface_virtuelle, camera_offset,
                                       pygame.time.get_ticks())

        # --- Orbes de capacité ---
        off_x, off_y = camera_offset
        camera_rect = pygame.Rect(off_x, off_y, lv, hv)
        for orbe in self.orbes_capacite_locaux.values():
            if not orbe.est_ramasse and camera_rect.colliderect(orbe.rect):
                orbe.dessiner(surface_virtuelle, camera_offset, pygame.time.get_ticks())

        # --- Joueurs ---
        for joueur in self.joueurs_locaux.values():
            joueur.dessiner(surface_virtuelle, camera_offset)

        temps_ms = pygame.time.get_ticks()

        # --- Ennemis ---
        detection_sq = DISTANCE_DETECTION_ENNEMI * DISTANCE_DETECTION_ENNEMI
        for ennemi in self.ennemis_locaux.values():
            if not camera_rect.colliderect(ennemi.rect):
                continue
            if mon_joueur:
                dx   = ennemi.rect.centerx - mon_joueur.rect.centerx
                dy   = ennemi.rect.centery - mon_joueur.rect.centery
                dist_sq = dx*dx + dy*dy
            else:
                dist_sq = 9999 * 9999

            temps_depuis_flash = temps_ms - getattr(ennemi, 'flash_echo_temps', 0)
            flash_actif        = temps_depuis_flash < DUREE_FLASH_ECHO_ENNEMI
            proche             = dist_sq <= detection_sq

            if proche:
                ennemi.dessiner(surface_virtuelle, camera_offset)
            elif flash_actif:
                ratio = 1.0 - (temps_depuis_flash / DUREE_FLASH_ECHO_ENNEMI)
                off_x, off_y = camera_offset
                cx = ennemi.rect.centerx - off_x
                cy = ennemi.rect.centery - off_y
                halo = self._flash_halo_surf
                halo.fill((0, 0, 0, 0))
                pygame.draw.circle(halo, (0, 212, 255, max(0, min(255, int(80 * ratio)))),
                                   (30, 30), 30)
                surface_virtuelle.blit(halo, (cx - 30, cy - 30))
                e_size = (ennemi.rect.w, ennemi.rect.h)
                if e_size not in self._flash_tmp_cache:
                    self._flash_tmp_cache[e_size] = pygame.Surface(e_size, pygame.SRCALPHA)
                tmp = self._flash_tmp_cache[e_size]
                tmp.fill((0, 212, 255, max(0, min(255, int(255 * ratio)))))
                surface_virtuelle.blit(tmp, (ennemi.rect.x - off_x, ennemi.rect.y - off_y))

        # --- Boss ---
        if self.boss_local and not getattr(self.boss_local, 'is_dead', False):
            off_x, off_y = camera_offset
            self.boss_local.pos.x -= off_x
            self.boss_local.pos.y -= off_y
            self.boss_local.draw(surface_virtuelle)
            self.boss_local.pos.x += off_x
            self.boss_local.pos.y += off_y

        if mon_joueur and mon_joueur.pv > 0:
            self._mort_depuis = None

        # --- Âmes (avec culling caméra) ---
        for ame in self.ames_perdues_locales.values():
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms)
        for ame in self.ames_libres_locales.values():
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms)
        for ame in self.ames_loot_locales.values():
            if camera_rect.colliderect(ame.rect):
                ame.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Clé ---
        if self.cle_locale and not self.cle_locale.est_ramassee:
            if camera_rect.colliderect(self.cle_locale.rect):
                self.cle_locale.dessiner(surface_virtuelle, camera_offset, temps_ms)

        # --- Torche ---
        self.torche.mettre_a_jour(temps_ms)
        self.torche.dessiner(surface_virtuelle, camera_offset, temps_ms)

        if self.torche.allumee and mon_joueur:
            dx   = mon_joueur.rect.centerx - self.torche.x
            dy   = mon_joueur.rect.centery - self.torche.y
            dist = (dx**2 + dy**2) ** 0.5
            music.torche_mettre_a_jour_volume(dist)

        # --- Calque obscurité ---
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
                ty = self.torche.y + TAILLE_TUILE     - camera_offset[1]
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

    def _thread_reseau(self):
        """Thread dédié au réseau : envoie les commandes, reçoit l'état du serveur."""
        while self._reseau_actif and self.running:
            try:
                with self._reseau_lock:
                    cmd = copy.copy(self._commandes_a_envoyer)

                send_complet(self.client_socket, cmd)
                donnees = recv_complet(self.client_socket)

                with self._reseau_lock:
                    # Accumuler les vis_delta pour éviter la perte de tuiles
                    # quand plusieurs états arrivent entre deux frames
                    if self._dernier_etat_serveur is not None and self._nouvel_etat_disponible:
                        ancien_delta = self._dernier_etat_serveur.get('vis_delta')
                        if ancien_delta and donnees.get('vis_map') is None:
                            nouveau_delta = donnees.get('vis_delta')
                            if nouveau_delta is not None:
                                donnees['vis_delta'] = ancien_delta + nouveau_delta
                            else:
                                donnees['vis_delta'] = ancien_delta
                        ancien_full = self._dernier_etat_serveur.get('vis_map')
                        if ancien_full is not None and donnees.get('vis_map') is None:
                            donnees['vis_map'] = ancien_full
                    self._dernier_etat_serveur = donnees
                    self._nouvel_etat_disponible = True

            except (EOFError, socket.timeout, socket.error, OSError) as e:
                with self._reseau_lock:
                    self._erreur_reseau = str(e)
                break
            except (pickle.UnpicklingError, ValueError):
                continue

    def _appliquer_etat_serveur(self, donnees_recues):
        """Applique l'état reçu du serveur aux entités locales."""
        # --- Vis map (full ou delta) ---
        if donnees_recues.get('vis_map') is not None:
            self.vis_map_locale = donnees_recues['vis_map']
            if self.carte:
                self.carte._vis_map_dirty = True
        if donnees_recues.get('vis_delta') and self.vis_map_locale:
            for x, y in donnees_recues['vis_delta']:
                self.vis_map_locale[y][x] = True
            if self.carte and donnees_recues['vis_delta']:
                self.carte._tuiles_a_reveler.extend(donnees_recues['vis_delta'])

        # --- Joueurs ---
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

        # --- Ennemis ---
        ids_e = {e['id'] for e in donnees_recues['ennemis']}
        for id_local in list(self.ennemis_locaux.keys()):
            if id_local not in ids_e:
                del self.ennemis_locaux[id_local]
        for de in donnees_recues['ennemis']:
            if de['id'] not in self.ennemis_locaux:
                self.ennemis_locaux[de['id']] = Ennemi(
                    de['x'], de['y'], de['id'],
                    de.get('type_ennemi', 'garde'))
            self.ennemis_locaux[de['id']].set_etat(de)

        for ennemi_local in self.ennemis_locaux.values():
            for nom_son in ennemi_local.sons_a_jouer:
                music.jouer_sfx(nom_son)
            ennemi_local.sons_a_jouer.clear()

        # --- Âmes perdues ---
        ids_a = {a['id'] for a in donnees_recues.get('ames_perdues', [])}
        for id_local in list(self.ames_perdues_locales.keys()):
            if id_local not in ids_a:
                del self.ames_perdues_locales[id_local]
        for da in donnees_recues.get('ames_perdues', []):
            if da['id'] not in self.ames_perdues_locales:
                self.ames_perdues_locales[da['id']] = AmePerdue(
                    da['x'], da['y'], da['id_joueur'])
            self.ames_perdues_locales[da['id']].set_etat(da)

        # --- Âmes libres ---
        ids_al = {a['id'] for a in donnees_recues.get('ames_libres', [])}
        for id_local in list(self.ames_libres_locales.keys()):
            if id_local not in ids_al:
                del self.ames_libres_locales[id_local]
        for dal in donnees_recues.get('ames_libres', []):
            if dal['id'] not in self.ames_libres_locales:
                self.ames_libres_locales[dal['id']] = AmeLibre(
                    dal['x'], dal['y'], dal.get('valeur'))
            self.ames_libres_locales[dal['id']].set_etat(dal)

        # --- Âmes loot ---
        ids_loot = {a['id'] for a in donnees_recues.get('ames_loot', [])}
        for id_local in list(self.ames_loot_locales.keys()):
            if id_local not in ids_loot:
                del self.ames_loot_locales[id_local]
        for dl in donnees_recues.get('ames_loot', []):
            if dl['id'] not in self.ames_loot_locales:
                self.ames_loot_locales[dl['id']] = AmeLoot(dl['x'], dl['y'], dl.get('valeur', 1))
            self.ames_loot_locales[dl['id']].set_etat(dl)

        # --- Orbes de capacité ---
        ids_orbes = {o['id'] for o in donnees_recues.get('orbes_capacite', [])}
        for id_local in list(self.orbes_capacite_locaux.keys()):
            if id_local not in ids_orbes:
                del self.orbes_capacite_locaux[id_local]
        for do in donnees_recues.get('orbes_capacite', []):
            if do['id'] not in self.orbes_capacite_locaux:
                self.orbes_capacite_locaux[do['id']] = OrbeCapacite(
                    do['x'], do['y'], do['capacite'])
            self.orbes_capacite_locaux[do['id']].set_etat(do)

        # --- Porte ---
        data_porte = donnees_recues.get('porte')
        if data_porte:
            if self.porte_locale is None:
                self.porte_locale = Porte(data_porte['x'], data_porte['y'])
            self.porte_locale.set_etat(data_porte)

        # --- Boss ---
        data_boss = donnees_recues.get('boss_room')
        if data_boss and not data_boss['boss_defeated']:
            if self.boss_local is None:
                _base = (sys._MEIPASS if getattr(sys, 'frozen', False)
                         else os.path.dirname(os.path.abspath(__file__)))
                self.boss_local = DemonSlimeBoss(
                    x=0, y=0,
                    json_path=os.path.join(_base, "demon_slime.json"),
                    png_path =os.path.join(_base, "assets", "demon_slime.png"))
            self.boss_local.set_etat(data_boss['boss'])

        # --- Clé ---
        data_cle = donnees_recues.get('cle')
        if data_cle:
            if self.cle_locale is None:
                self.cle_locale = Cle(data_cle['x'], data_cle['y'])
            self.cle_locale.set_etat(data_cle)

        # --- Torche ---
        torche_serveur = donnees_recues.get('torche_allumee', False)
        if torche_serveur != self.torche.allumee:
            self.torche.allumee = torche_serveur
            if torche_serveur:
                self.torche.particules = []

        # --- Données boss pour HUD ---
        self._derniere_data_boss = donnees_recues.get('boss_room')

    def boucle_jeu_reseau(self):
        if not self.client_socket:
            self.etat_jeu = "MENU_PRINCIPAL"
            return
        music.demarrer()

        # --- Initialiser le thread réseau ---
        self._reseau_lock = threading.Lock()
        self._reseau_actif = True
        self._commandes_a_envoyer = {
            'clavier': {'gauche': False, 'droite': False,
                        'saut': False, 'attaque': False, 'dash': False},
            'echo': False,
        }
        self._dernier_etat_serveur = None
        self._nouvel_etat_disponible = False
        self._erreur_reseau = None

        thread_reseau = threading.Thread(target=self._thread_reseau, daemon=True)
        thread_reseau.start()

        while self.etat_jeu == "EN_JEU" and self.running:
            # Masquer la souris en jeu (plein écran), la montrer en pause/menus
            en_plein_ecran = self.parametres.get('video', {}).get('plein_ecran', False)
            if en_plein_ecran:
                pygame.mouse.set_visible(self.etat_jeu_interne in ("PAUSE", "PARAMETRES_JEU"))

            pos_souris = pygame.mouse.get_pos()
            commandes_a_envoyer = {
                'clavier': {'gauche': False, 'droite': False,
                            'saut': False, 'attaque': False, 'dash': False},
                'echo': False,
            }

            if self.etat_jeu_interne == "JEU":
                commandes_a_envoyer = self.gerer_evenements_jeu()
            elif self.etat_jeu_interne == "PAUSE":
                self.gerer_evenements_pause(pos_souris)
            elif self.etat_jeu_interne == "PARAMETRES_JEU":
                if not self.parametres_temp:
                    self.parametres_temp = copy.deepcopy(self.parametres)
                self.etat_jeu_precedent = "_RETOUR_PAUSE"
                self.gerer_menu_parametres(pos_souris)
                if self.etat_jeu == "_RETOUR_PAUSE":
                    self.etat_jeu = "EN_JEU"
                    self.etat_jeu_interne = "PAUSE"

            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            # Envoyer les commandes au thread réseau
            with self._reseau_lock:
                self._commandes_a_envoyer = commandes_a_envoyer

            # Vérifier erreur réseau
            with self._reseau_lock:
                erreur = self._erreur_reseau

            if erreur:
                print(f"[CLIENT] Erreur réseau: {erreur}")
                self.message_erreur_connexion = "Connexion perdue."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break

            # Appliquer le dernier état reçu (si disponible)
            with self._reseau_lock:
                donnees_recues = self._dernier_etat_serveur if self._nouvel_etat_disponible else None
                self._nouvel_etat_disponible = False

            if donnees_recues:
                self._appliquer_etat_serveur(donnees_recues)

            # Dessiner (toujours, même sans nouvel état serveur)
            self.dessiner_jeu()
            if self.etat_jeu_interne == "PAUSE":
                self.dessiner_menu_pause()
            elif self.etat_jeu_interne == "PARAMETRES_JEU":
                self.dessiner_menu_parametres()

            pygame.display.flip()
            self.horloge.tick(FPS)

        # Arrêter le thread réseau proprement
        self._reseau_actif = False

    # ==================================================================
    #  LANCEMENT ET CONNEXION
    # ==================================================================

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement  = "nouvelle" if est_nouvelle_partie else "charger"
        self._serveur_instance = None
        self._relay_instance   = None

        # Auto-démarrer le relay server en tant que thread
        try:
            self._relay_instance = demarrer_relay_thread(RELAY_PORT)
            print(f"[CLIENT] Relay auto-démarré sur le port {RELAY_PORT}")
        except Exception as e:
            print(f"[CLIENT] Impossible de démarrer le relay: {e}")
            self._relay_instance = None

        relay_host = "localhost" if self._relay_instance else ""
        relay_port = RELAY_PORT

        def _demarrer_serveur():
            self._serveur_instance = serveur.creer_serveur(
                id_slot, type_lancement,
                relay_host=relay_host, relay_port=relay_port)
            self._serveur_instance.demarrer()

        thread_serveur = threading.Thread(target=_demarrer_serveur, daemon=True)
        thread_serveur.start()
        connecte = False
        for _ in range(6):
            time.sleep(0.5)
            connecte = self.connecter("localhost")
            if connecte:
                break
        if connecte:
            self.etat_jeu = "EN_JEU"
            # Récupérer le code room du serveur (si relay actif)
            if relay_host and self._serveur_instance:
                for _ in range(40):  # max 2 secondes
                    if self._serveur_instance.code_room:
                        self.code_room = self._serveur_instance.code_room
                        print(f"[CLIENT] Code Room : {self.code_room}")
                        break
                    time.sleep(0.05)
        else:
            self.etat_jeu = "MENU_PRINCIPAL"

    def _finaliser_connexion(self):
        """Initialise les données locales après un handshake réussi."""
        if getattr(sys, 'frozen', False):
            dossier_script = sys._MEIPASS
        else:
            dossier_script = os.path.dirname(os.path.abspath(__file__))
        chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
        self.carte             = Carte(chemin_map)
        self.vis_map_locale    = self.carte.creer_carte_visibilite_vierge()
        self.joueurs_locaux    = {}
        self.ennemis_locaux    = {}
        self.ames_perdues_locales  = {}
        self.ames_libres_locales   = {}
        self.ames_loot_locales     = {}
        self.orbes_capacite_locaux = {}
        self.porte_locale          = None
        self.cle_locale            = None

    def connecter(self, hote):
        try:
            print(f"[CLIENT] Tentative de connexion vers {hote}:{PORT_SERVEUR}...")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[CLIENT] Socket TCP créée (timeout connexion : 5s)")
            self.client_socket.settimeout(5)
            print(f"[CLIENT] Connexion TCP en cours vers {hote}:{PORT_SERVEUR}...")
            self.client_socket.connect((hote, PORT_SERVEUR))
            print(f"[CLIENT] Connexion TCP établie avec {hote}:{PORT_SERVEUR}")
            self.client_socket.settimeout(10.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[CLIENT] En attente du handshake serveur (timeout : 10s)...")
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    print(f"[CLIENT] Connexion refusée : serveur plein")
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = reponse
            print(f"[CLIENT] Connecté avec succès (ID joueur : {self.mon_id})")
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            return True

        except socket.timeout:
            print(f"[CLIENT] Echec connexion: TIMEOUT — {hote}:{PORT_SERVEUR} ne répond pas (firewall ou port non ouvert ?)")
            self.message_erreur_connexion = f"Timeout : {hote}:{PORT_SERVEUR} ne répond pas.\nVérifiez le pare-feu et la redirection de port."
            self.client_socket = None
            return False
        except ConnectionRefusedError:
            print(f"[CLIENT] Echec connexion: CONNEXION REFUSÉE — aucun serveur sur {hote}:{PORT_SERVEUR}")
            self.message_erreur_connexion = f"Connexion refusée : {hote}:{PORT_SERVEUR}\nLe serveur n'est pas démarré."
            self.client_socket = None
            return False
        except socket.gaierror as e:
            print(f"[CLIENT] Echec connexion: ADRESSE INVALIDE — impossible de résoudre '{hote}' : {e}")
            self.message_erreur_connexion = f"Adresse invalide : '{hote}'"
            self.client_socket = None
            return False
        except socket.error as e:
            print(f"[CLIENT] Echec connexion: {type(e).__name__}: {e}")
            self.message_erreur_connexion = f"Impossible de se connecter\nau serveur : {hote}"
            self.client_socket = None
            return False

    def connecter_relay(self, code_room, relay_host=None, relay_port=None):
        """Se connecte au serveur via le relay avec un room code."""
        from reseau.relay_client import relay_rejoindre
        host = relay_host or RELAY_HOST
        port = relay_port or RELAY_PORT
        try:
            print(f"[CLIENT] Connexion relay ({host}:{port}) avec code '{code_room}'...")
            self.client_socket = relay_rejoindre(host, port, code_room)
            print(f"[CLIENT] Relay bridgé, en attente du handshake serveur...")
            self.client_socket.settimeout(15.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu via relay : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    print(f"[CLIENT] Connexion refusée : serveur plein")
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = reponse
            print(f"[CLIENT] Connecté via relay (ID joueur : {self.mon_id})")
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            return True

        except ConnectionError as e:
            print(f"[CLIENT] Echec relay: {e}")
            self.message_erreur_connexion = str(e).replace("Relay: ", "")
            self.client_socket = None
            return False
        except socket.timeout:
            print(f"[CLIENT] Echec relay: TIMEOUT après connexion au relay")
            self.message_erreur_connexion = "Timeout : le serveur ne répond pas\nvia le relay."
            self.client_socket = None
            return False
        except Exception as e:
            print(f"[CLIENT] Echec relay: {type(e).__name__}: {e}")
            self.message_erreur_connexion = f"Échec connexion relay :\n{e}"
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        pygame.mouse.set_visible(True)
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        # Arrêter le relay embarqué si présent
        relay = getattr(self, '_relay_instance', None)
        if relay:
            try:
                relay.arreter()
                print("[CLIENT] Relay embarqué arrêté")
            except Exception as e:
                print(f"[CLIENT] Erreur arrêt relay: {e}")
        self.client_socket         = None
        self.mon_id                = -1
        self.code_room             = None
        self._serveur_instance     = None
        self._relay_instance       = None
        self.joueurs_locaux        = {}
        self.ennemis_locaux        = {}
        self.ames_perdues_locales  = {}
        self.ames_libres_locales   = {}
        self.ames_loot_locales     = {}
        self.orbes_capacite_locaux = {}
        self.porte_locale          = None
        self.cle_locale            = None
        self.carte                 = None
        self.vis_map_locale        = None
        self.etat_jeu_interne      = "JEU"