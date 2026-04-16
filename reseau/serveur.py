# reseau/serveur.py
# Gestion centrale : Physique, IA, Combat, Sauvegarde.
# MISE À JOUR : Porte interactive, Orbes de capacités, ennemis typés.

import socket
import threading
import pickle
import time
import sys
import pygame

from core.joueur import Joueur
from core.carte import Carte
from parametres import *
from sauvegarde import gestion_sauvegarde
from sauvegarde import points_sauvegarde
from core.ennemi import Ennemi
from core.boss_room import BossRoom
from core.ame_perdue import AmePerdue
from core.ame_libre import AmeLibre
from core.ame_loot import AmeLoot
from core.cle import Cle
from core.porte import Porte
from core.orbe_capacite import OrbeCapacite
from reseau.protocole import obtenir_ip_locale, obtenir_ip_vpn, recvall, recv_complet, send_complet


class Serveur:
    def __init__(self, id_slot, est_nouvelle_partie, relay_host="", relay_port=7777):
        # ===== RÉSEAU =====
        self.serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, 'SO_REUSEPORT'):
            self.serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.serveur_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            ip_serveur = obtenir_ip_locale()
            self.serveur_socket.bind((ip_serveur, PORT_SERVEUR))
            print(f"[SERVEUR] Demarre sur le port {PORT_SERVEUR}")
            print(f"[SERVEUR] IP locale : {ip_serveur}")
        except OSError as e:
            print(f"[SERVEUR] ERREUR lors du bind: {e}")
            raise

        # ===== VERROU THREAD =====
        self.lock = threading.Lock()

        # ===== DONNÉES DE JEU =====
        self.clients             = {}
        self.joueurs             = {}
        self.cartes_visibilite   = {}
        self.vis_map_dirty       = {}
        self.ennemis             = {}
        self.ames_perdues        = {}
        self.ames_libres         = {}
        self.ames_loot           = {}
        self.orbes_capacite      = {}   # NOUVEAU
        self.vis_delta_buffer    = {}   # {id_joueur: set((x,y),...)}
        self.vis_needs_full      = {}   # {id_joueur: bool} — forcer vis_full au 1er tick
        self.cle                 = None
        self.porte               = None  # NOUVEAU
        self.echos_en_cours      = []

        # ===== CARTE =====
        import os
        if getattr(sys, 'frozen', False):
            dossier_script = sys._MEIPASS
        else:
            dossier_script = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
        self.carte_jeu = Carte(chemin_map)

        self.rects_collision      = self.carte_jeu.get_rects_collisions()
        self.carte_jeu.construire_grille_collision()
        self.points_sauvegarde_map = self.scanner_points_sauvegarde()

        # ===== SAUVEGARDE =====
        self.id_slot       = id_slot
        self.donnees_partie = None

        if est_nouvelle_partie:
            self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
            gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)
        else:
            self.donnees_partie = gestion_sauvegarde.charger_partie(self.id_slot)
            if self.donnees_partie is None:
                self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)

        # ===== SPAWN POINT =====
        id_checkpoint    = self.donnees_partie["id_dernier_checkpoint"]
        self.spawn_point = points_sauvegarde.get_coords_par_id(id_checkpoint)

        # ===== DEBUG =====
        print(f"[DEBUG] Dimensions carte : {self.carte_jeu.largeur_map}x{self.carte_jeu.hauteur_map}")
        print(f"[DEBUG] Spawn point : {self.spawn_point}")

        # ===== INIT FINALE =====
        self.creer_ennemis()
        self.creer_ames_libres()
        self.creer_orbes_capacite()   # NOUVEAU
        self.creer_porte()             # NOUVEAU

        self.boss_room = BossRoom(
            room_rect       = pygame.Rect(72*32, 13*32, (93-72)*32, (20-13)*32),
            boss_x          = 87*32,
            boss_y          = 19*32,
            json_path       = os.path.join(dossier_script, "demon_slime.json"),
            png_path        = os.path.join(dossier_script, "assets", "demon_slime.png"),
            rects_collision = self.rects_collision,
        )

        # self.cle              = Cle(x=1011, y=1027)  # Deplace vers boucle_jeu_serveur apres mort boss
        self._ids_pool        = list(range(3))
        self.torche_allumee   = False
        self.torche_x         = 32
        self.torche_y         = 672
        self.running          = True
        self._etat_broadcast  = None
        self._broadcast_lock  = threading.Lock()
        self.code_room        = None       # Room code relay (si activé)
        self.relay_host       = relay_host
        self.relay_port       = relay_port

    # ------------------------------------------------------------------
    #  CREATION DES ENTITES
    # ------------------------------------------------------------------

    def scanner_points_sauvegarde(self):
        points = {}
        for y, rangee in enumerate(self.carte_jeu.map_data):
            for x, tuile in enumerate(rangee):
                if tuile == 3:
                    id_str = f"{x}_{y}"
                    rect   = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE,
                                         TAILLE_TUILE, TAILLE_TUILE)
                    points[id_str] = rect
        return points

    def creer_ennemis(self):
        """
        Place des ennemis avec des types variés (PV 1-3) cohérents
        avec leur position/importance dans la map.
        """
        # Tuples : (x, y, id, type_ennemi)
        configs = [
            # Zone de spawn — patrouilleurs légers (1 PV)
            (587,  1251, 0, 'patrouilleur'),
            # Zone médiane — gardes standard (2 PV)
            (1867, 1123, 1, 'garde'),
            (1191,  707, 2, 'garde'),
            # Zone avancée — gardiens lourds (3 PV), proches du boss
            (2427,  163, 3, 'gardien'),
            (2851,  259, 4, 'gardien'),
        ]
        for x, y, eid, type_e in configs:
            self.ennemis[eid] = Ennemi(x=x, y=y, id=eid, type_ennemi=type_e)

    def creer_ames_libres(self):
        """Place des âmes libres à divers endroits de la map."""
        positions = [
            (680,  515), (747, 1123), (1021, 1251),
            (1333,  995), (1510, 515), (2427, 163), (2851,  259),
        ]
        for x, y in positions:
            ame = AmeLibre(x, y)
            self.ames_libres[ame.id] = ame

    def creer_orbes_capacite(self):
        """
        Place des orbes de déblocage de capacités.
        - Double saut : zone accessible tôt, encourage l'exploration verticale.
        - Dash : zone intermédiaire, récompense la progression.
        """
        configs = [
            (419,  1190, 'double_saut'),   # Zone basse-gauche, accessible sans dash
            (2920, 1126, 'dash'),           # Zone plus haute, nécessite le double saut
        ]
        for x, y, capacite in configs:
            orbe = OrbeCapacite(x, y, capacite)
            self.orbes_capacite[orbe.id] = orbe
        print(f"[SERVEUR] {len(self.orbes_capacite)} orbes de capacité créés")

    def creer_porte(self):
        """
        Place la porte principale qui nécessite la clé.
        Positionnée comme point de progression logique (après la clé).
        """
        # Porte placée dans un couloir clé de la map
        self.porte = Porte(x=995, y=960)
        print(f"[SERVEUR] Porte créée à ({self.porte.x}, {self.porte.y})")

    # ------------------------------------------------------------------
    #  GESTION CLIENT
    # ------------------------------------------------------------------

    def gerer_client(self, connexion_client, id_joueur):
        spawn_x, spawn_y = (self.spawn_point
                            if id_joueur == 0
                            else points_sauvegarde.get_point_depart()[1])

        nouveau_joueur = Joueur(spawn_x, spawn_y, id_joueur)
        if id_joueur == 0:
            nouveau_joueur.argent = self.donnees_partie.get("argent", 0)
        ameliorations = self.donnees_partie.get("ameliorations", {})
        nouveau_joueur.peut_double_saut = ameliorations.get("double_saut", False)
        nouveau_joueur.peut_dash        = ameliorations.get("dash", False)
        nouveau_joueur.peut_echo_dir    = ameliorations.get("echo_dir", False)

        if MODE_DEV:
            nouveau_joueur.peut_double_saut = True
            nouveau_joueur.peut_dash        = True
            nouveau_joueur.peut_echo_dir    = True

        self.joueurs[id_joueur] = nouveau_joueur

        if id_joueur == 0:
            vis_sauvegarde = self.donnees_partie["vis_map"]
            if (len(vis_sauvegarde) != self.carte_jeu.hauteur_map
                    or len(vis_sauvegarde[0]) != self.carte_jeu.largeur_map):
                self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()
            else:
                self.cartes_visibilite[id_joueur] = [row[:] for row in vis_sauvegarde]
        else:
            self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()
        self.vis_map_dirty[id_joueur] = True
        self.vis_delta_buffer[id_joueur] = set()
        self.vis_needs_full[id_joueur] = True  # Forcer vis_full au premier tick

        print(f"[SERVEUR] Envoi handshake (ID={id_joueur}) au client {connexion_client.getpeername()}...")
        send_complet(connexion_client, id_joueur)
        print(f"[SERVEUR] Handshake envoyé, démarrage boucle de jeu pour joueur {id_joueur}")
        connexion_client.settimeout(10.0)
        connexion_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Drapeau partagé pour arrêter les sous-threads quand l'un tombe
        client_actif = [True]

        def thread_recv():
            """Reçoit les commandes du client en continu."""
            try:
                while self.running and client_actif[0]:
                    try:
                        commandes = recv_complet(connexion_client)
                    except EOFError:
                        break

                    with self.lock:
                        if id_joueur not in self.joueurs:
                            break
                        self.joueurs[id_joueur].commandes = commandes['clavier']

                        if commandes.get('echo'):
                            t_echo = pygame.time.get_ticks()
                            joueur = self.joueurs[id_joueur]
                            if t_echo - joueur.dernier_echo_temps > COOLDOWN_ECHO:
                                joueur.dernier_echo_temps = t_echo
                                self.echos_en_cours.append({
                                    'id_joueur':       id_joueur,
                                    'cx':              joueur.rect.centerx,
                                    'cy':              joueur.rect.centery,
                                    'debut':           t_echo,
                                    'rayon_precedent': 0,
                                    'type':            'normal',
                                    'portee_max':      PORTEE_ECHO,
                                })

                        if commandes.get('echo_dir'):
                            t_echo_dir = pygame.time.get_ticks()
                            joueur = self.joueurs[id_joueur]
                            if (joueur.peut_echo_dir
                                    and t_echo_dir - joueur.dernier_echo_dir_temps > COOLDOWN_ECHO_DIR):
                                joueur.dernier_echo_dir_temps = t_echo_dir
                                self.echos_en_cours.append({
                                    'id_joueur':       id_joueur,
                                    'cx':              joueur.rect.centerx,
                                    'cy':              joueur.rect.centery,
                                    'debut':           t_echo_dir,
                                    'rayon_precedent': 0,
                                    'type':            'dir',
                                    'portee_max':      PORTEE_ECHO_DIR,
                                    'direction':       joueur.direction,
                                })

                        if commandes.get('toggle_torche'):
                            nouvelle_valeur = not self.torche_allumee
                            self.torche_allumee = nouvelle_valeur
                            # Checkpoint à l'allumage (hôte uniquement)
                            if nouvelle_valeur and id_joueur == 0 and id_joueur in self.joueurs:
                                joueur_ckpt = self.joueurs[id_joueur]
                                x_tuile = joueur_ckpt.rect.x // TAILLE_TUILE
                                y_tuile = joueur_ckpt.rect.y // TAILLE_TUILE
                                id_ckpt = f"{x_tuile}_{y_tuile}"
                                self.donnees_partie["id_dernier_checkpoint"] = id_ckpt
                                self.donnees_partie["vis_map"] = [
                                    row[:] for row in self.cartes_visibilite[id_joueur]]
                                self.donnees_partie["argent"] = joueur_ckpt.argent
                                self.donnees_partie["ameliorations"]["double_saut"] = joueur_ckpt.peut_double_saut
                                self.donnees_partie["ameliorations"]["dash"] = joueur_ckpt.peut_dash
                                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)
                                print(f"[SERVEUR] Checkpoint torche sauvegardé : {id_ckpt}, argent={joueur_ckpt.argent}")

            except (socket.timeout, socket.error, ValueError):
                pass
            finally:
                client_actif[0] = False

        def thread_send():
            """Envoie l'état au client à TICK_RATE_RESEAU Hz."""
            intervalle = 1.0 / TICK_RATE_RESEAU
            try:
                while self.running and client_actif[0]:
                    debut = time.time()

                    with self._broadcast_lock:
                        etat_commun = self._etat_broadcast

                    if etat_commun is None:
                        time.sleep(0.005)
                        continue

                    with self.lock:
                        vis_delta = None
                        vis_full = None
                        needs_full = self.vis_needs_full.get(id_joueur, False)
                        if needs_full:
                            vis_actuelle = self.cartes_visibilite.get(id_joueur)
                            if vis_actuelle is not None:
                                vis_full = [row[:] for row in vis_actuelle]
                            self.vis_needs_full[id_joueur] = False
                            self.vis_delta_buffer[id_joueur].clear()
                            self.vis_map_dirty[id_joueur] = False
                        elif self.vis_map_dirty.get(id_joueur):
                            buf = self.vis_delta_buffer.get(id_joueur)
                            vis_delta = list(buf)
                            buf.clear()
                            self.vis_map_dirty[id_joueur] = False

                    donnees_pour_client = {**etat_commun, 'vis_map': vis_full, 'vis_delta': vis_delta}
                    send_complet(connexion_client, donnees_pour_client)

                    elapsed = time.time() - debut
                    if elapsed < intervalle:
                        time.sleep(intervalle - elapsed)

            except (socket.error, OSError):
                pass
            finally:
                client_actif[0] = False

        t_recv = threading.Thread(target=thread_recv, daemon=True)
        t_send = threading.Thread(target=thread_send, daemon=True)
        t_recv.start()
        t_send.start()

        # Attendre que l'un des deux threads se termine (= déconnexion)
        t_recv.join()
        t_send.join()

        print(f"[SERVEUR] Client {id_joueur} deconnecte.")
        try:
            connexion_client.close()
        except Exception:
            pass
        with self.lock:
            if connexion_client in self.clients:
                del self.clients[connexion_client]
            if id_joueur in self.joueurs:
                del self.joueurs[id_joueur]
                if id_joueur in self.cartes_visibilite:
                    del self.cartes_visibilite[id_joueur]
                if id_joueur in self.vis_map_dirty:
                    del self.vis_map_dirty[id_joueur]
                if id_joueur in self.vis_delta_buffer:
                    del self.vis_delta_buffer[id_joueur]
                if hasattr(self, 'vis_needs_full') and id_joueur in self.vis_needs_full:
                    del self.vis_needs_full[id_joueur]
                if id_joueur not in self._ids_pool:
                    self._ids_pool.append(id_joueur)
                    self._ids_pool.sort()

    # ------------------------------------------------------------------
    #  BOUCLE JEU SERVEUR
    # ------------------------------------------------------------------

    def boucle_jeu_serveur(self):
        horloge = pygame.time.Clock()
        while self.running:
            temps_actuel = pygame.time.get_ticks()

            with self.lock:
                # 0. Révélation progressive des échos
                echos_restants = []
                for echo in self.echos_en_cours:
                    elapsed    = temps_actuel - echo['debut']
                    if elapsed <= ECHO_DUREE_REVEAL:
                        portee_max = echo.get('portee_max', PORTEE_ECHO)
                        rayon_max  = int((elapsed / ECHO_DUREE_REVEAL) * portee_max)
                        rayon_prec = echo.get('rayon_precedent', 0)
                        if rayon_max > rayon_prec and echo['id_joueur'] in self.cartes_visibilite:
                            id_j = echo['id_joueur']
                            buf = self.vis_delta_buffer.get(id_j)
                            if buf is None:
                                buf = set()
                                self.vis_delta_buffer[id_j] = buf
                            if echo.get('type') == 'dir':
                                self.carte_jeu.reveler_par_echo_dir_partiel(
                                    echo['cx'], echo['cy'], rayon_max,
                                    self.cartes_visibilite[id_j],
                                    echo['direction'], delta_set=buf)
                            else:
                                self.carte_jeu.reveler_par_echo_partiel(
                                    echo['cx'], echo['cy'], rayon_max,
                                    self.cartes_visibilite[id_j], delta_set=buf)
                            echo['rayon_precedent'] = rayon_max
                            self.vis_map_dirty[echo['id_joueur']] = True
                        echos_restants.append(echo)
                self.echos_en_cours = echos_restants

            # Flash sonar sur les ennemis
            portee_echo_sq = PORTEE_ECHO * PORTEE_ECHO
            for echo in echos_restants:
                for ennemi in self.ennemis.values():
                    dx   = ennemi.rect.centerx - echo['cx']
                    dy   = ennemi.rect.centery - echo['cy']
                    if dx*dx + dy*dy <= portee_echo_sq:
                        ennemi.flash_echo_temps = temps_actuel

            with self.lock:
                # 1. Âmes libres : animation + collecte
                for ame in self.ames_libres.values():
                    ame.mettre_a_jour(temps_actuel)
                for id_joueur, joueur in list(self.joueurs.items()):
                    for id_ame, ame in list(self.ames_libres.items()):
                        if id_ame not in self.ames_libres:
                            continue
                        if joueur.rect.colliderect(ame.rect):
                            joueur.argent += ame.valeur
                            del self.ames_libres[id_ame]

                # 1b. Âmes loot : physique + collecte + despawn
                for id_ame, ame in list(self.ames_loot.items()):
                    ame.mettre_a_jour(temps_actuel, self.carte_jeu.get_rects_proches(ame.rect))
                    if ame.est_expiree(temps_actuel):
                        del self.ames_loot[id_ame]
                        continue
                    for id_joueur, joueur in self.joueurs.items():
                        if joueur.rect.colliderect(ame.rect):
                            joueur.argent += ame.valeur
                            if id_ame in self.ames_loot:
                                del self.ames_loot[id_ame]
                            break

                # 2. Orbes de capacité : animation + collecte
                for orbe in list(self.orbes_capacite.values()):
                    if not orbe.est_ramasse:
                        orbe.mettre_a_jour(temps_actuel)
                for id_joueur, joueur in list(self.joueurs.items()):
                    for id_orbe, orbe in list(self.orbes_capacite.items()):
                        if orbe.est_ramasse:
                            continue
                        if joueur.rect.colliderect(orbe.rect):
                            if orbe.tenter_collecte(joueur):
                                # Sauvegarder l'amélioration immédiatement
                                if id_joueur == 0:
                                    self.donnees_partie['ameliorations'][orbe.capacite] = True
                                    gestion_sauvegarde.sauvegarder_partie(
                                        self.id_slot, self.donnees_partie)

                # 3. Clé : animation + collecte
                if self.cle and not self.cle.est_ramassee:
                    self.cle.mettre_a_jour(temps_actuel)
                    for id_joueur, joueur in list(self.joueurs.items()):
                        if joueur.rect.colliderect(self.cle.rect):
                            self.cle.est_ramassee = True
                            joueur.have_key       = True
                            print(f"[SERVEUR] Joueur {id_joueur} a ramasse la cle !")

                # 4. Porte : animation + interaction
                if self.porte and not self.porte.est_ouverte:
                    self.porte.mettre_a_jour(temps_actuel)
                    if not self.porte.en_ouverture:
                        for joueur in self.joueurs.values():
                            if joueur.rect.colliderect(
                                    pygame.Rect(self.porte.x - 8, self.porte.y,
                                                self.porte.LARGEUR + 16, self.porte.HAUTEUR)):
                                self.porte.tenter_ouverture(joueur)

                # 5. (Collision porte intégrée dans la section 8)

                # 6. Ennemis — physique + respawn
                for id_ennemi, ennemi in list(self.ennemis.items()):
                    if ennemi.est_mort:
                        if temps_actuel - ennemi.temps_mort >= TEMPS_RESPAWN_ENNEMI:
                            ennemi.respawn()
                            print(f"[SERVEUR] Ennemi {id_ennemi} ({ennemi.type_ennemi}) respawn !")
                    else:
                        rects_proches = self.carte_jeu.get_rects_proches(ennemi.rect)
                        ennemi.appliquer_logique(rects_proches, self.carte_jeu)

                # 7. Boss Room
                if not self.boss_room.boss_defeated:
                    self.boss_room.update(
                        temps_actuel - getattr(self, '_temps_precedent', temps_actuel),
                        self.joueurs)
                    
                    if self.boss_room.boss_defeated:
                        # Le boss vient de mourir -> Drop la cle au centre du boss
                        bx = self.boss_room.boss.pos.x + self.boss_room.boss.sprite_w // 2
                        by = self.boss_room.boss.pos.y + self.boss_room.boss.sprite_h // 2
                        self.cle = Cle(bx, by)
                        print(f"[SERVEUR] Le boss a lâché la clé à ({bx}, {by})")

                self._temps_precedent = temps_actuel

                # 8. Joueurs — collisions spatiales + porte
                porte_rect = None
                if self.porte and not self.porte.est_ouverte:
                    r = self.porte.rect_collision
                    if r.width > 0 and r.height > 0:
                        porte_rect = r
                for id_joueur, joueur in list(self.joueurs.items()):
                    rects_proches = self.carte_jeu.get_rects_proches(joueur.rect)
                    if porte_rect and joueur.rect.colliderect(
                            porte_rect.inflate(TAILLE_TUILE * 2, TAILLE_TUILE * 2)):
                        rects_proches = rects_proches + [porte_rect]
                    joueur.appliquer_physique(rects_proches)

                    # A. Attaque
                    joueur.gerer_attaque(temps_actuel)
                    if joueur.est_en_attaque and joueur.rect_attaque:
                        for id_ennemi, ennemi in list(self.ennemis.items()):
                            if (not ennemi.est_mort
                                    and id_ennemi not in joueur.ennemis_touches  # hit registry
                                    and joueur.rect_attaque.colliderect(ennemi.rect)):
                                joueur.ennemis_touches.add(id_ennemi)  # enregistre avant d'infliger
                                mort = ennemi.prendre_degat(DEGATS_JOUEUR, temps_actuel)
                                if mort:
                                    cx, cy = ennemi.rect.centerx, ennemi.rect.centery
                                    for _ in range(ennemi.argent_drop):
                                        ame = AmeLoot(cx, cy, valeur=1)
                                        ame.temps_creation = temps_actuel
                                        self.ames_loot[ame.id] = ame
                        for id_ame, ame in list(self.ames_perdues.items()):
                            if ame.id_joueur == id_joueur:
                                if joueur.rect_attaque.colliderect(ame.rect):
                                    joueur.argent  += ame.argent
                                    joueur.ame_perdue = None
                                    del self.ames_perdues[id_ame]
                        self.boss_room.recevoir_attaque_joueur(joueur.rect_attaque, DEGATS_JOUEUR)

                    # B. Dégâts reçus des ennemis
                    for ennemi in self.ennemis.values():
                        if not ennemi.est_mort and joueur.rect.colliderect(ennemi.rect):
                            joueur.prendre_degat(1, temps_actuel)

                    # C. Mort et Respawn
                    if joueur.pv <= 0:
                        if joueur.temps_mort is None:
                            joueur.temps_mort = temps_actuel
                            if joueur.ame_perdue and joueur.ame_perdue.id in self.ames_perdues:
                                del self.ames_perdues[joueur.ame_perdue.id]
                            nouvelle_ame = AmePerdue(
                                joueur.rect.centerx, joueur.rect.centery,
                                id_joueur, joueur.argent)
                            self.ames_perdues[nouvelle_ame.id] = nouvelle_ame
                            joueur.ame_perdue = nouvelle_ame
                            joueur.argent     = 0
                        elif temps_actuel - joueur.temps_mort >= 3000:
                            id_ckpt = (self.donnees_partie["id_dernier_checkpoint"]
                                       if id_joueur == 0
                                       else points_sauvegarde.get_point_depart()[0])
                            coords_spawn = points_sauvegarde.get_coords_par_id(id_ckpt)
                            joueur.respawn(coords_spawn)
                            joueur.temps_mort = None

                    # D. Sauvegarde aux checkpoints (hôte uniquement)
                    if id_joueur == 0:
                        for id_save, rect_save in self.points_sauvegarde_map.items():
                            if joueur.rect.colliderect(rect_save):
                                if self.donnees_partie["id_dernier_checkpoint"] != id_save:
                                    self.donnees_partie["id_dernier_checkpoint"] = id_save
                                    self.donnees_partie["vis_map"] = [
                                        row[:] for row in self.cartes_visibilite[id_joueur]]
                                    self.donnees_partie["argent"] = joueur.argent
                                    self.donnees_partie["ameliorations"]["double_saut"] = joueur.peut_double_saut
                                    self.donnees_partie["ameliorations"]["dash"]        = joueur.peut_dash
                                    gestion_sauvegarde.sauvegarder_partie(
                                        self.id_slot, self.donnees_partie)

            # 9. Broadcast réseau
            if not hasattr(self, '_dernier_broadcast'):
                self._dernier_broadcast = 0
            intervalle = 1000 / TICK_RATE_RESEAU
            if temps_actuel - self._dernier_broadcast >= intervalle:
                self._dernier_broadcast = temps_actuel
                with self.lock:
                    etat_commun = {
                        'joueurs':       [j.get_etat() for j in self.joueurs.values()],
                        'ennemis':       [e.get_etat() for e in self.ennemis.values()],
                        'ames_perdues':  [a.get_etat() for a in self.ames_perdues.values()],
                        'ames_libres':   [a.get_etat() for a in self.ames_libres.values()],
                        'ames_loot':     [a.get_etat() for a in self.ames_loot.values()],
                        'orbes_capacite': [o.get_etat() for o in self.orbes_capacite.values()],
                        'cle':           self.cle.get_etat() if self.cle else None,
                        'porte':         self.porte.get_etat() if self.porte else None,
                        'torche_allumee': self.torche_allumee,
                        'boss_room':     self.boss_room.get_etat(),
                    }
                with self._broadcast_lock:
                    self._etat_broadcast = etat_commun

            horloge.tick(FPS)

    # ------------------------------------------------------------------
    #  DÉMARRAGE
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    #  ACCEPTATION CLIENT (direct ou relay)
    # ------------------------------------------------------------------

    def _accepter_client(self, connexion_client, adresse):
        """Accepte un client (direct ou relay). Même logique pour les deux."""
        print(f"[SERVEUR] Tentative de connexion depuis {adresse}")

        if not self._ids_pool:
            print(f"[SERVEUR] Connexion refusee — Serveur plein (3/3)")
            try:
                send_complet(connexion_client, {"erreur": "SERVEUR_PLEIN"})
                time.sleep(0.1)
                connexion_client.close()
            except Exception as e:
                print(f"[SERVEUR] Erreur lors du refus : {e}")
            return

        id_joueur = self._ids_pool.pop(0)
        print(f"[SERVEUR] Joueur {id_joueur} accepte depuis {adresse}")

        self.clients[connexion_client] = id_joueur
        thread_client = threading.Thread(
            target=self.gerer_client,
            args=(connexion_client, id_joueur),
            daemon=True,
        )
        thread_client.start()
        print(f"[SERVEUR] Thread client démarré pour joueur {id_joueur} depuis {adresse}")

    # ------------------------------------------------------------------
    #  RELAY : écoute des clients relayés
    # ------------------------------------------------------------------

    def _ecouter_relay(self):
        """Thread relay : crée une room et accepte les clients relayés."""
        from reseau.relay_client import relay_creer_room, relay_attendre_client, relay_ouvrir_canal_data
        try:
            ctrl, self.code_room = relay_creer_room(self.relay_host, self.relay_port)
            print(f"[SERVEUR] Relay connecté — Code Room : {self.code_room}")
        except Exception as e:
            print(f"[SERVEUR] Impossible de se connecter au relay ({self.relay_host}:{self.relay_port}): {e}")
            return

        while self.running:
            try:
                slot_id = relay_attendre_client(ctrl, self.relay_host, self.relay_port)
                print(f"[SERVEUR] Nouveau client relay (slot {slot_id})")
                data_sock = relay_ouvrir_canal_data(self.relay_host, self.relay_port, self.code_room, slot_id)
                self._accepter_client(data_sock, ("relay", slot_id))
            except EOFError:
                print("[SERVEUR] Connexion relay perdue")
                break
            except Exception as e:
                print(f"[SERVEUR] Erreur relay: {e}")
                break

        self.code_room = None
        print("[SERVEUR] Thread relay terminé")

    # ------------------------------------------------------------------
    #  DÉMARRAGE
    # ------------------------------------------------------------------

    def demarrer(self):
        thread_boucle_jeu = threading.Thread(target=self.boucle_jeu_serveur)
        thread_boucle_jeu.daemon = True
        thread_boucle_jeu.start()

        # Démarrer le thread relay si configuré
        if self.relay_host:
            thread_relay = threading.Thread(target=self._ecouter_relay, daemon=True)
            thread_relay.start()

        self.serveur_socket.listen()
        print("[SERVEUR] En attente de connexions...")

        while True:
            connexion_client, adresse = self.serveur_socket.accept()
            self._accepter_client(connexion_client, adresse)


def creer_serveur(id_slot, type_lancement, relay_host="", relay_port=7777):
    """Crée et retourne une instance Serveur (sans la démarrer)."""
    pygame.init()
    ip = obtenir_ip_locale()
    ip_vpn = obtenir_ip_vpn()
    print(f"[SERVEUR] IP locale : {ip}")
    if ip_vpn != "Non connecté":
        print(f"[SERVEUR] IP VPN (Tailscale/Hamachi) : {ip_vpn}")
    est_nouvelle_partie = (type_lancement == "nouvelle")
    return Serveur(id_slot=id_slot, est_nouvelle_partie=est_nouvelle_partie,
                   relay_host=relay_host, relay_port=relay_port)


def main(id_slot, type_lancement):
    s = creer_serveur(id_slot, type_lancement,
                      relay_host=RELAY_HOST, relay_port=RELAY_PORT)
    s.demarrer()