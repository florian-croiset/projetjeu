# boucle_jeu.py
# Mixin pour la boucle de jeu en réseau (input, rendu monde, connexion).
# MISE À JOUR : Rendu Porte interactive + Orbes de capacités + Pancartes Lore.

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
import random

from parametres import *
from utils import envoyer_logs, music
from reseau import serveur
from reseau.relay_server import demarrer_relay_thread
from reseau.protocole import recv_complet, send_complet, obtenir_ip_locale
from reseau import udp_protocole as UDP_P
from reseau.udp_endpoint import UdpEndpoint
from reseau.udp_connexion import ConnexionUDP
from ui.camera import calculer_camera, creer_masque_halo
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
from core.pancarte_lore import PancarteLore, BulleLore, PopupPaiement   # NOUVEAU


def _extraire_id_handshake(reponse):
    """Le serveur répond soit un int (mode legacy), soit un dict
    {'id', 'udp_token', 'udp_port'}. On renvoie juste l'ID joueur."""
    if isinstance(reponse, dict):
        return reponse.get('id')
    return reponse


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

            elif self.etat_jeu == "MENU_LUMINOSITE":
                self.gerer_menu_luminosite(pos_souris)
                if self.etat_jeu == "MENU_LUMINOSITE":
                    self.dessiner_menu_luminosite()

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

    def _son_attaque(self, joueur):
        """Slash2/Slash3 si un ennemi est dans la portée d'attaque, sinon Slash1."""
        if joueur.direction == 1:
            rect_a = pygame.Rect(joueur.rect.right, joueur.rect.y, PORTEE_ATTAQUE, joueur.rect.height)
        else:
            rect_a = pygame.Rect(joueur.rect.left - PORTEE_ATTAQUE, joueur.rect.y, PORTEE_ATTAQUE, joueur.rect.height)
        for ennemi in self.ennemis_locaux.values():
            if not ennemi.est_mort and rect_a.colliderect(ennemi.rect):
                return random.choice(['slash2', 'slash3'])
        return 'attaque'

    def gerer_evenements_jeu(self):
        commandes = {
            'clavier':        {'gauche': False, 'droite': False,
                               'saut': False, 'attaque': False, 'dash': False},
            'echo':           False,
            'echo_dir':       False,
            'toggle_torche':  False,
            'interagir':      False,   # NOUVEAU
        }

        key = self._codes_touches.get

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if MODE_DEV and envoyer_logs.get_bouton().verifier_clic(event):
                envoyer_logs.envoyer_maintenant()

            # NOUVEAU — Laisser la bulle et la popup consommer les events en priorité
            if self.bulle_lore and self.bulle_lore.visible:
                if self.bulle_lore.gerer_event(event):
                    continue
            if self.popup_paiement and self.popup_paiement.visible:
                if self.popup_paiement.gerer_event(event):
                    continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    try:
                        self._dernier_frame_jeu = self.ecran.copy()
                    except Exception:
                        self._dernier_frame_jeu = None
                    self.etat_jeu_interne = "PAUSE"
                    music.pause()
                if event.key == key('attaque'):
                    commandes['clavier']['attaque'] = True
                    _j = self.joueurs_locaux.get(self.mon_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attaque_local_debut_ms >= COOLDOWN_ATTAQUE:
                        music.jouer_sfx(self._son_attaque(_j) if _j else 'attaque')
                        if _j:
                            _j._attaque_local_debut_ms = now
                if event.key == key('echo'):
                    commandes['echo'] = True
                    music.jouer_sfx('echo')
                if event.key == key('dash'):
                    commandes['clavier']['dash'] = True
                    music.jouer_sfx('dash')
                if event.key == key('echo_dir'):
                    commandes['echo_dir'] = True
                    music.jouer_sfx('echo_dir')
                if event.key == key('torche'):
                    commandes['toggle_torche'] = True
                    if not self.torche.allumee:
                        music.torche_boucle_start()
                    else:
                        music.torche_boucle_stop()

                # NOUVEAU — Touche interaction (F par défaut)
                if event.key == key('interagir'):
                    mon_joueur = self.joueurs_locaux.get(self.mon_id)
                    if mon_joueur and not self.bulle_lore.visible and not self.popup_paiement.visible:
                        pancarte_proche = None
                        for i, pancarte in self.pancartes_lore_locales.items():
                            dx = mon_joueur.rect.centerx - pancarte.rect.centerx
                            dy = mon_joueur.rect.centery - pancarte.rect.centery
                            if (dx**2 + dy**2) ** 0.5 <= PancarteLore.PORTEE_INTERACTION:
                                pancarte_proche = (i, pancarte)
                                break
                        if pancarte_proche:
                            i, pancarte = pancarte_proche
                            if pancarte.est_debloquee:
                                # Pancarte déjà payée → ouvrir directement la bulle de lore
                                self.bulle_lore.ouvrir()
                            else:
                                # Pancarte verrouillée → ouvrir la popup de paiement
                                self._pancarte_active_id = i

                                def _callback_paiement():
                                    commandes['interagir'] = True

                                self.popup_paiement.ouvrir_confirmation(
                                    mon_joueur.argent,
                                    _callback_paiement
                                )

            if event.type == pygame.MOUSEBUTTONDOWN:
                ms = self._codes_souris.get
                if ms('attaque') and event.button == ms('attaque'):
                    commandes['clavier']['attaque'] = True
                    _j = self.joueurs_locaux.get(self.mon_id)
                    now = pygame.time.get_ticks()
                    if _j is None or now - _j._attaque_local_debut_ms >= COOLDOWN_ATTAQUE:
                        music.jouer_sfx(self._son_attaque(_j) if _j else 'attaque')
                        if _j:
                            _j._attaque_local_debut_ms = now
                if ms('echo') and event.button == ms('echo'):
                    commandes['echo'] = True
                    music.jouer_sfx('echo')
                if ms('dash') and event.button == ms('dash'):
                    commandes['clavier']['dash'] = True
                    music.jouer_sfx('dash')
                if ms('echo_dir') and event.button == ms('echo_dir'):
                    commandes['echo_dir'] = True
                    music.jouer_sfx('echo_dir')

        touches = pygame.key.get_pressed()
        if key('gauche') and touches[key('gauche')]:
            commandes['clavier']['gauche'] = True
        if key('droite') and touches[key('droite')]:
            commandes['clavier']['droite'] = True
        if key('saut') and touches[key('saut')]:
            commandes['clavier']['saut'] = True
        if self._codes_souris:
            souris = pygame.mouse.get_pressed(num_buttons=5)
            for action in ('gauche', 'droite', 'saut'):
                btn = self._codes_souris.get(action)
                if btn and 1 <= btn <= 5 and souris[btn - 1]:
                    commandes['clavier'][action] = True

        mon_joueur = self.joueurs_locaux.get(self.mon_id)
        if mon_joueur and mon_joueur.pv <= 0:
            commandes['clavier']       = {'gauche': False, 'droite': False,
                                          'saut': False, 'attaque': False, 'dash': False}
            commandes['echo']          = False
            commandes['echo_dir']      = False
            commandes['toggle_torche'] = False
            commandes['interagir']     = False   # NOUVEAU

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
            if orbe.est_ramasse:
                continue
            if not camera_rect.colliderect(orbe.rect):
                continue
            # Ne pas afficher si le joueur a déjà cette capacité
            if orbe.capacite == 'double_saut' and getattr(mon_joueur, 'peut_double_saut', False):
                continue
            if orbe.capacite == 'dash' and getattr(mon_joueur, 'peut_dash', False):
                continue
            if orbe.capacite == 'echo_dir' and getattr(mon_joueur, 'peut_echo_dir', False):
                continue
            orbe.dessiner(surface_virtuelle, camera_offset, pygame.time.get_ticks())

        # NOUVEAU — Pancartes de lore
        for pancarte in self.pancartes_lore_locales.values():
            if camera_rect.colliderect(pancarte.rect):
                pancarte.dessiner(surface_virtuelle, camera_offset, pygame.time.get_ticks())

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
            elif flash_actif and not ennemi.est_mort:
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
            ame.mettre_a_jour_visuels(temps_ms, self.carte)
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
            lum = self.parametres.get('video', {}).get('luminosite', 0.3)
            alpha_base = int(220 * (1.0 - lum * 0.8))
            if getattr(self, '_halo_alpha_max', None) != alpha_base:
                self._masque_halo_joueur = creer_masque_halo(RAYON_HALO_JOUEUR, HALO_DEGRADE_ETENDUE, alpha_max=alpha_base)
                self._masque_halo_torche = creer_masque_halo(RAYON_LUMIERE_TORCHE, HALO_DEGRADE_ETENDUE, alpha_max=alpha_base)
                self._halo_alpha_max = alpha_base
            obscurite.fill((0, 0, 10, alpha_base))
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

        # --- Badge torche ---
        if self.torche.jamais_utilisee and mon_joueur:
            dx = mon_joueur.rect.centerx - self.torche.x
            dy = mon_joueur.rect.centery - self.torche.y
            if (dx**2 + dy**2)**0.5 <= DISTANCE_TORCHE_ECHO * 3:
                self._dessiner_badge_torche(surface_virtuelle, camera_offset)

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

        # NOUVEAU — Rendu UI pancarte par-dessus tout (sur self.ecran, pas sur surface_virtuelle)
        # La bulle et la popup sont dessinées dans boucle_jeu_reseau après display.flip

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
        # --- Horloge serveur (pour interpolation en TCP ou fallback UDP) ---
        t_serveur = donnees_recues.get('t')
        if t_serveur is not None:
            now_ms = int(time.monotonic() * 1000)
            self.udp_offset_serveur_ms = t_serveur - now_ms

        # --- Vis map ---
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
            joueur = self.joueurs_locaux[dj['id']]
            # Pour le joueur local en TCP : ne pas écraser la position 10 Hz
            # (sinon saccadement). On la passera par le buffer d'interpolation
            # juste après pour avoir un mouvement fluide à 60 fps.
            if not self.udp_actif and dj['id'] == self.mon_id:
                joueur.set_etat_local(dj)
            else:
                joueur.set_etat(dj)
            # En mode TCP : alimenter le buffer d'interpolation pour TOUS les
            # joueurs (y compris le local) afin de lisser le mouvement entre
            # deux paquets 10 Hz. En UDP, les snapshots 30 Hz s'en chargent
            # et un double push ici casserait la monotonie du buffer.
            if (not self.udp_actif
                    and t_serveur is not None
                    and hasattr(joueur, 'pousser_snapshot_interp')):
                joueur.pousser_snapshot_interp(t_serveur, dj['x'], dj['y'])

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
            ennemi = self.ennemis_locaux[de['id']]
            ennemi.set_etat(de)
            if (not self.udp_actif
                    and t_serveur is not None
                    and hasattr(ennemi, 'pousser_snapshot_interp')):
                ennemi.pousser_snapshot_interp(t_serveur, de['x'], de['y'])

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

        # NOUVEAU — Pancartes lore
        for i, dp in enumerate(donnees_recues.get('pancartes_lore', [])):
            if i not in self.pancartes_lore_locales:
                self.pancartes_lore_locales[i] = PancarteLore(dp['x'], dp['y'])
            pancarte = self.pancartes_lore_locales[i]
            etait_debloquee = pancarte.est_debloquee
            pancarte.set_etat(dp)
            # Si la pancarte vient d'être débloquée par CE joueur → ouvrir la bulle
            if not etait_debloquee and dp['est_debloquee']:
                if getattr(self, '_pancarte_active_id', None) == i:
                    self.bulle_lore.ouvrir()
                    self._pancarte_active_id = None

        # --- Porte ---
        data_porte = donnees_recues.get('porte')
        if data_porte:
            if self.porte_locale is None:
                self.porte_locale = Porte(data_porte['x'], data_porte['y'])
            self.porte_locale.set_etat(data_porte)
            if not self._porte_etait_en_ouverture and self.porte_locale.en_ouverture:
                music.jouer_sfx('porte')
            self._porte_etait_en_ouverture = self.porte_locale.en_ouverture

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
            etat_boss_actuel = data_boss['boss']['state']
            if self._boss_etat_precedent != 'CLEAVE' and etat_boss_actuel == 'CLEAVE':
                music.jouer_sfx('slash_boss')
            self._boss_etat_precedent = etat_boss_actuel

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
            'interagir': False,   # NOUVEAU
        }
        self._dernier_etat_serveur = None
        self._nouvel_etat_disponible = False
        self._erreur_reseau = None

        udp_actif = getattr(self, 'udp_actif', False)
        self._dernier_keepalive_tcp = time.monotonic()

        # En mode UDP on ne lance PAS le thread TCP bloquant : le client tournera
        # tout en non-bloquant dans la boucle Pygame. Le TCP reste ouvert
        # uniquement pour un keepalive rare (évite le timeout côté serveur).
        thread_reseau = None
        if not udp_actif:
            thread_reseau = threading.Thread(target=self._thread_reseau, daemon=True)
            thread_reseau.start()

        while self.etat_jeu == "EN_JEU" and self.running:
            en_plein_ecran = self.parametres.get('video', {}).get('plein_ecran', False)
            if en_plein_ecran:
                pygame.mouse.set_visible(self.etat_jeu_interne in ("PAUSE", "PARAMETRES_JEU", "LUMINOSITE_JEU"))

            pos_souris = pygame.mouse.get_pos()
            commandes_a_envoyer = {
                'clavier': {'gauche': False, 'droite': False,
                            'saut': False, 'attaque': False, 'dash': False},
                'echo': False,
                'interagir': False,   # NOUVEAU
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
            elif self.etat_jeu_interne == "LUMINOSITE_JEU":
                self.gerer_menu_luminosite(pos_souris)

            if self.etat_jeu != "EN_JEU" or not self.running:
                break

            if udp_actif:
                # 1. Envoi inputs via UDP.
                one_shot = {
                    'echo':           commandes_a_envoyer.get('echo', False),
                    'echo_dir':       commandes_a_envoyer.get('echo_dir', False),
                    'toggle_torche':  commandes_a_envoyer.get('toggle_torche', False),
                    'interagir':      commandes_a_envoyer.get('interagir', False),
                }
                self._udp_envoyer_inputs(commandes_a_envoyer, one_shot)
                # 2. Keepalive TCP toutes les 5 s pour que le serveur n'invalide pas le socket.
                if time.monotonic() - self._dernier_keepalive_tcp > 5.0:
                    try:
                        send_complet(self.client_socket, {})
                    except Exception as e:
                        self._erreur_reseau = f"TCP keepalive: {e}"
                    self._dernier_keepalive_tcp = time.monotonic()
                # 3. Pomper les paquets UDP entrants et appliquer.
                self._udp_pomper_et_appliquer()
            else:
                with self._reseau_lock:
                    self._commandes_a_envoyer = commandes_a_envoyer

            with self._reseau_lock:
                erreur = self._erreur_reseau

            if erreur:
                print(f"[CLIENT] Erreur réseau: {erreur}")
                self.message_erreur_connexion = "Connexion perdue."
                self.nettoyer_connexion()
                self.etat_jeu = "MENU_PRINCIPAL"
                break

            if not udp_actif:
                with self._reseau_lock:
                    donnees_recues = self._dernier_etat_serveur if self._nouvel_etat_disponible else None
                    self._nouvel_etat_disponible = False

                if donnees_recues:
                    self._appliquer_etat_serveur(donnees_recues)

            # Interpolation joueurs distants + ennemis (TCP comme UDP)
            self._mettre_a_jour_interpolations(int(time.monotonic() * 1000))

            # Dessiner le monde
            self.dessiner_jeu()
            if self.etat_jeu_interne == "PAUSE":
                self.dessiner_menu_pause()
            elif self.etat_jeu_interne == "PARAMETRES_JEU":
                self.dessiner_menu_parametres()
            elif self.etat_jeu_interne == "LUMINOSITE_JEU":
                self.dessiner_menu_luminosite()

            # NOUVEAU — Rendu UI pancarte sur self.ecran (au-dessus du zoom)
            if self.bulle_lore and self.bulle_lore.visible:
                self.bulle_lore.dessiner(self.ecran)
            if self.popup_paiement and self.popup_paiement.visible:
                self.popup_paiement.dessiner(self.ecran)

            pygame.display.flip()
            self.horloge.tick(FPS)

        self._reseau_actif = False

    # ==================================================================
    #  LANCEMENT ET CONNEXION
    # ==================================================================

    def lancer_partie_locale(self, id_slot, est_nouvelle_partie=False):
        type_lancement  = "nouvelle" if est_nouvelle_partie else "charger"
        self._serveur_instance = None
        relay_precedent = getattr(self, '_relay_instance', None)
        if relay_precedent:
            try:
                relay_precedent.arreter()
            except Exception:
                pass
        self._relay_instance   = None

        try:
            self._relay_instance = demarrer_relay_thread(RELAY_PORT)
            print(f"[CLIENT] Relay auto-démarré sur le port {RELAY_PORT}")
        except Exception as e:
            print(f"[CLIENT] Impossible de démarrer le relay: {e}")
            self._relay_instance = None

        relay_host = obtenir_ip_locale() if self._relay_instance else ""
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
            connecte = self.connecter(obtenir_ip_locale())
            if connecte:
                break
        if connecte:
            self.etat_jeu = "EN_JEU"
            if relay_host and self._serveur_instance:
                for _ in range(40):
                    if self._serveur_instance.code_room:
                        self.code_room = self._serveur_instance.code_room
                        print(f"[CLIENT] Code Room : {self.code_room}")
                        break
                    time.sleep(0.05)
        else:
            self.etat_jeu = "MENU_PRINCIPAL"

    def _initier_udp_si_dispo(self, reponse_handshake, hote_tcp: str) -> bool:
        """Tente un handshake UDP. Retourne True si l'UDP est actif, False si fallback TCP."""
        self.udp_actif      = False
        self.udp_endpoint   = None
        self.udp_conn       = None
        self.udp_offset_serveur_ms = None

        if not USE_UDP or not isinstance(reponse_handshake, dict):
            return False
        token = reponse_handshake.get('udp_token')
        port_udp = reponse_handshake.get('udp_port')
        if not token or not port_udp:
            return False

        try:
            self.udp_endpoint = UdpEndpoint(bind_host="0.0.0.0", bind_port=0)
        except OSError as exc:
            print(f"[CLIENT] Impossible d'ouvrir un socket UDP: {exc}")
            return False

        addr_serveur = (hote_tcp, port_udp)
        self.udp_conn = ConnexionUDP(self.udp_endpoint, addr_serveur,
                                     heartbeat_ms=UDP_HEARTBEAT_INTERVAL_MS,
                                     timeout_ms=UDP_CONNECTION_TIMEOUT_MS)

        # Envoie le token au serveur UDP et attend HANDSHAKE_ACK.
        self.udp_conn.envoyer_control(UDP_P.TYPE_HANDSHAKE_UDP, {'token': token})

        deadline = time.monotonic() + UDP_HANDSHAKE_TIMEOUT_MS / 1000.0
        intervalle_rtx = 0.2
        prochain_renvoi = time.monotonic() + intervalle_rtx
        while time.monotonic() < deadline:
            for data, addr in self.udp_endpoint.pomper():
                if addr != addr_serveur:
                    continue
                self.udp_conn.traiter_paquet_brut(data)
            for canal, type_, payload in self.udp_conn.drainer_recus():
                if canal == UDP_P.CANAL_CONTROL and type_ == UDP_P.TYPE_HANDSHAKE_ACK:
                    self.udp_actif = True
                    print(f"[CLIENT] UDP handshake validé (port local {self.udp_endpoint.bind_port})")
                    return True
            if time.monotonic() >= prochain_renvoi:
                self.udp_conn.envoyer_control(UDP_P.TYPE_HANDSHAKE_UDP, {'token': token})
                prochain_renvoi = time.monotonic() + intervalle_rtx
            time.sleep(0.02)

        # Échec → on abandonne le socket UDP, fallback TCP.
        print(f"[CLIENT] UDP handshake échoué après {UDP_HANDSHAKE_TIMEOUT_MS} ms, bascule TCP")
        try:
            self.udp_endpoint.fermer()
        except Exception:
            pass
        self.udp_endpoint = None
        self.udp_conn     = None
        self.udp_actif    = False
        return False

    def _udp_envoyer_inputs(self, commandes: dict, one_shot_commandes: dict):
        if not self.udp_actif or self.udp_conn is None:
            return
        # Continus : unreliable 60 Hz (même cadence que la frame)
        self.udp_conn.envoyer_unreliable(UDP_P.TYPE_INPUTS_CONTINUS, pickle.dumps(commandes.get('clavier', {})))
        # One-shot : reliable (echo, echo_dir, torche, interagir)
        if any(one_shot_commandes.values()):
            self.udp_conn.envoyer_reliable(UDP_P.TYPE_INPUT_ONESHOT, one_shot_commandes)

    def _udp_pomper_et_appliquer(self):
        """Drain l'UDP, applique snapshots (positions) + état discret (pickle)."""
        if not self.udp_actif or self.udp_conn is None or self.udp_endpoint is None:
            return
        for data, addr in self.udp_endpoint.pomper():
            if addr != self.udp_conn.addr_pair:
                continue
            self.udp_conn.traiter_paquet_brut(data)

        now_ms = int(time.monotonic() * 1000)
        self.udp_conn.tick(now_ms)
        if not self.udp_conn.actif:
            with self._reseau_lock:
                self._erreur_reseau = "Connexion UDP perdue (timeout)"
            return

        for canal, type_, payload in self.udp_conn.drainer_recus():
            if canal == UDP_P.CANAL_UNRELIABLE and type_ == UDP_P.TYPE_SNAPSHOT:
                self._appliquer_snapshot_udp(payload, now_ms)
            elif canal == UDP_P.CANAL_RELIABLE and type_ == UDP_P.TYPE_ETAT_DISCRET:
                if isinstance(payload, dict):
                    self._appliquer_etat_serveur(payload)

    def _appliquer_snapshot_udp(self, snap: dict, now_ms: int):
        """Applique positions struct : local → direct ; distants → buffer d'interp."""
        t_serveur = snap.get('t', 0)
        # Offset d'horloge : on ramène le temps serveur à la monotonic client.
        self.udp_offset_serveur_ms = t_serveur - now_ms

        for jd in snap.get('joueurs', []):
            jid = jd['id']
            joueur = self.joueurs_locaux.get(jid)
            if joueur is None:
                continue
            if jid == self.mon_id:
                # Joueur local : snapping direct (pas d'interp pour éviter le lag).
                joueur.rect.x = int(jd['x'])
                joueur.rect.y = int(jd['y'])
            else:
                if hasattr(joueur, 'pousser_snapshot_interp'):
                    joueur.pousser_snapshot_interp(t_serveur, jd['x'], jd['y'])

        for ed in snap.get('ennemis', []):
            ennemi = self.ennemis_locaux.get(ed['id'])
            if ennemi is None:
                continue
            if hasattr(ennemi, 'pousser_snapshot_interp'):
                ennemi.pousser_snapshot_interp(t_serveur, ed['x'], ed['y'])

        # Boss : snap direct à 60 Hz (l'état discret 10 Hz fournit pv/state/flags)
        boss_data = snap.get('boss')
        if boss_data and self.boss_local is not None:
            self.boss_local.pos.x = boss_data['x']
            self.boss_local.pos.y = boss_data['y']

    def _mettre_a_jour_interpolations(self, now_ms: int):
        if self.udp_offset_serveur_ms is None:
            return
        t_render = now_ms + self.udp_offset_serveur_ms - INTERP_DELAY_MS
        for jid, joueur in self.joueurs_locaux.items():
            # En UDP, le joueur local est snappé directement (cf. _appliquer_snapshot_udp)
            # à 30 Hz : pas besoin d'interp (et son buffer est vide de toute façon).
            # En TCP, on l'interpole comme les autres pour lisser les ticks 10 Hz.
            if self.udp_actif and jid == self.mon_id:
                continue
            if hasattr(joueur, 'mettre_a_jour_interp'):
                joueur.mettre_a_jour_interp(t_render)
        for ennemi in self.ennemis_locaux.values():
            if hasattr(ennemi, 'mettre_a_jour_interp'):
                ennemi.mettre_a_jour_interp(t_render)

    def _finaliser_connexion(self):
        """Initialise les données locales après un handshake réussi."""
        if getattr(sys, 'frozen', False):
            dossier_script = sys._MEIPASS
        else:
            dossier_script = os.path.dirname(os.path.abspath(__file__))
        chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
        self.carte                  = Carte(chemin_map)
        self.vis_map_locale         = self.carte.creer_carte_visibilite_vierge()
        self.joueurs_locaux         = {}
        self.ennemis_locaux         = {}
        self.ames_perdues_locales   = {}
        self.ames_libres_locales    = {}
        self.ames_loot_locales      = {}
        self.orbes_capacite_locaux  = {}
        self.pancartes_lore_locales = {}   # NOUVEAU
        self.porte_locale           = None
        self.cle_locale             = None
        # NOUVEAU — UI pancarte (taille dépend de l'écran courant)
        self.bulle_lore         = BulleLore(self.largeur_ecran, self.hauteur_ecran)
        self.popup_paiement     = PopupPaiement(self.largeur_ecran, self.hauteur_ecran)
        self._pancarte_active_id = None   # Indice de la pancarte en cours de paiement

    def connecter(self, hote):
        try:
            print(f"[CLIENT] Tentative de connexion vers {hote}:{PORT_SERVEUR}...")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((hote, PORT_SERVEUR))
            print(f"[CLIENT] Connexion TCP établie avec {hote}:{PORT_SERVEUR}")
            self.client_socket.settimeout(10.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = _extraire_id_handshake(reponse)
            print(f"[CLIENT] Connecté avec succès (ID joueur : {self.mon_id})")
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            self._initier_udp_si_dispo(reponse, hote)
            return True

        except socket.timeout:
            self.message_erreur_connexion = f"Timeout : {hote}:{PORT_SERVEUR} ne répond pas.\nVérifiez le pare-feu et la redirection de port."
            self.client_socket = None
            return False
        except ConnectionRefusedError:
            self.message_erreur_connexion = f"Connexion refusée : {hote}:{PORT_SERVEUR}\nLe serveur n'est pas démarré."
            self.client_socket = None
            return False
        except socket.gaierror as e:
            self.message_erreur_connexion = f"Adresse invalide : '{hote}'"
            self.client_socket = None
            return False
        except socket.error as e:
            self.message_erreur_connexion = f"Impossible de se connecter\nau serveur : {hote}"
            self.client_socket = None
            return False

    def connecter_relay(self, code_room, relay_host=None, relay_port=None):
        from reseau.relay_client import relay_rejoindre
        host = relay_host or RELAY_HOST
        port = relay_port or RELAY_PORT
        try:
            print(f"[CLIENT] Connexion relay ({host}:{port}) avec code '{code_room}'...")
            self.client_socket = relay_rejoindre(host, port, code_room)
            self.client_socket.settimeout(15.0)
            self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            reponse = recv_complet(self.client_socket)
            print(f"[CLIENT] Handshake reçu via relay : {reponse}")

            if isinstance(reponse, dict) and "erreur" in reponse:
                if reponse["erreur"] == "SERVEUR_PLEIN":
                    self.message_erreur_connexion = "Le serveur est plein !\n(3/3 joueurs)"
                    self.client_socket.close()
                    self.client_socket = None
                    return False

            self.mon_id = _extraire_id_handshake(reponse)
            self.message_erreur_connexion = None
            self._finaliser_connexion()
            # Le relay TCP ne transportera PAS l'UDP : on ne tente l'UDP
            # que sur une connexion directe (host param fourni côté ConnexionUDP).
            # Via relay, on reste en mode TCP.
            self.udp_actif = False
            return True

        except ConnectionError as e:
            self.message_erreur_connexion = str(e).replace("Relay: ", "")
            self.client_socket = None
            return False
        except socket.timeout:
            self.message_erreur_connexion = "Timeout : le serveur ne répond pas\nvia le relay."
            self.client_socket = None
            return False
        except Exception as e:
            self.message_erreur_connexion = f"Échec connexion relay :\n{e}"
            self.client_socket = None
            return False

    def nettoyer_connexion(self):
        pygame.mouse.set_visible(True)
        # UDP
        endpoint_udp = getattr(self, 'udp_endpoint', None)
        if endpoint_udp is not None:
            try:
                endpoint_udp.fermer()
            except Exception:
                pass
        self.udp_endpoint = None
        self.udp_conn     = None
        self.udp_actif    = False
        self.udp_offset_serveur_ms = None
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        srv = getattr(self, '_serveur_instance', None)
        if srv:
            try:
                srv.running = False
                srv.serveur_socket.close()
            except Exception:
                pass
        relay = getattr(self, '_relay_instance', None)
        if relay:
            try:
                relay.arreter()
                print("[CLIENT] Relay embarqué arrêté")
            except Exception as e:
                print(f"[CLIENT] Erreur arrêt relay: {e}")
        music.torche_boucle_stop()
        if hasattr(self, 'torche') and self.torche:
            self.torche.allumee = False
        self.client_socket          = None
        self.mon_id                 = -1
        self.code_room              = None
        self._serveur_instance      = None
        self._relay_instance        = None
        self.joueurs_locaux         = {}
        self.ennemis_locaux         = {}
        self.ames_perdues_locales   = {}
        self.ames_libres_locales    = {}
        self.ames_loot_locales      = {}
        self.orbes_capacite_locaux  = {}
        self.pancartes_lore_locales = {}   # NOUVEAU
        self.porte_locale           = None
        self.cle_locale             = None
        self.carte                  = None
        self.vis_map_locale         = None
        self.boss_local             = None
        self._porte_etait_en_ouverture  = False
        self._boss_etat_precedent       = None
        self.etat_jeu_interne           = "JEU"
        # NOUVEAU — reset UI pancarte
        self.bulle_lore          = None
        self.popup_paiement      = None
        self._pancarte_active_id = None