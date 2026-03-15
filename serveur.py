# serveur.py
# Gestion centrale : Physique, IA, Combat, Sauvegarde.

import socket
import threading
import pickle
import time
import sys
import pygame

from joueur import Joueur
from carte import Carte
from parametres import *
import gestion_sauvegarde
import points_sauvegarde
from ennemi import Ennemi
from ame_perdue import AmePerdue
from ame_libre import AmeLibre
from cle import Cle


def obtenir_ip_locale():
    """Retourne l'IP locale de la machine sur le réseau."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_locale = s.getsockname()[0]
        s.close()
        return ip_locale
    except Exception:
        return "127.0.0.1"


def _recvall(sock, n):
    """Lit exactement n octets depuis le socket (TCP peut fragmenter)."""
    data = b""
    while len(data) < n:
        paquet = sock.recv(n - len(data))
        if not paquet:
            raise EOFError("Connexion fermee")
        data += paquet
    return data

def _recv_complet_serveur(sock):
    """Reçoit un paquet complet : 4 octets taille + payload."""
    header = _recvall(sock, 4)
    taille = int.from_bytes(header, 'big')
    if taille > 10_000_000:  # sécurité : max 10 MB
        raise ValueError(f"Paquet trop grand : {taille} octets")
    return pickle.loads(_recvall(sock, taille))

def _send_complet(sock, obj):
    """Envoie un objet pickle précédé de 4 octets de taille."""
    data = pickle.dumps(obj)
    sock.sendall(len(data).to_bytes(4, 'big') + data)


class Serveur:
    def __init__(self, id_slot, est_nouvelle_partie):
        # ===== RÉSEAU =====
        self.serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serveur_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            self.serveur_socket.bind(('0.0.0.0', PORT_SERVEUR))
            ip_serveur = obtenir_ip_locale()
            print(f"[SERVEUR] Demarre sur le port {PORT_SERVEUR}")
            print(f"[SERVEUR] IP locale : {ip_serveur}")
        except OSError as e:
            print(f"[SERVEUR] ERREUR lors du bind: {e}")
            raise

        # ===== VERROU THREAD =====
        self.lock = threading.Lock()

        # ===== DONNÉES DE JEU =====
        self.clients = {}
        self.joueurs = {}
        self.cartes_visibilite = {}
        self.ennemis = {}
        self.ames_perdues = {}
        self.ames_libres = {}
        self.vis_map_precedente = {}  # pour delta vis_map
        self.cle = None
        self.echos_en_cours = []

        # ===== CARTE =====
        import os
        dossier_script = os.path.dirname(os.path.abspath(__file__))
        chemin_map = os.path.join(dossier_script, "assets/MapS2.tmx")
        self.carte_jeu = Carte(chemin_map)

        self.rects_collision = self.carte_jeu.get_rects_collisions()
        self.points_sauvegarde_map = self.scanner_points_sauvegarde()

        # ===== SAUVEGARDE =====
        self.id_slot = id_slot
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
        id_checkpoint = self.donnees_partie["id_dernier_checkpoint"]
        self.spawn_point = points_sauvegarde.get_coords_par_id(id_checkpoint)

        # ===== DEBUG =====
        print(f"[DEBUG] Dimensions carte : {self.carte_jeu.largeur_map}x{self.carte_jeu.hauteur_map}")
        print(f"[DEBUG] Spawn point : {self.spawn_point}")
        spawn_x = int(self.spawn_point[0] // TAILLE_TUILE)
        spawn_y = int(self.spawn_point[1] // TAILLE_TUILE)
        print(f"[DEBUG] Tuile au spawn : x={spawn_x}, y={spawn_y}")

        if spawn_y + 1 < self.carte_jeu.hauteur_map and spawn_x < self.carte_jeu.largeur_map:
            tuile_dessous = self.carte_jeu.map_data[spawn_y + 1][spawn_x]
            print(f"[DEBUG] Tuile sous le spawn : {tuile_dessous} (devrait etre 1 pour un mur)")

        print(f"[DEBUG] Nombre de murs : {len(self.rects_collision)}")

        # ===== INIT FINALE =====
        self.creer_ennemis()
        self.creer_ames_libres()
        self.cle = Cle(x=1034, y=399)
        self._ids_pool = list(range(3))  # IDs réutilisables : 0, 1, 2
        self.torche_allumee = False
        self.torche_x = 32
        self.torche_y = 672
        self.running = True
        self._etat_broadcast = None
        self._broadcast_lock = threading.Lock()

    def scanner_points_sauvegarde(self):
        points = {}
        for y, rangee in enumerate(self.carte_jeu.map_data):
            for x, tuile in enumerate(rangee):
                if tuile == 3:
                    id_str = f"{x}_{y}"
                    rect = pygame.Rect(x * TAILLE_TUILE, y * TAILLE_TUILE, TAILLE_TUILE, TAILLE_TUILE)
                    points[id_str] = rect
        return points

    def creer_ennemis(self):
        self.ennemis[0] = Ennemi(x=200, y=680, id=0)
        self.ennemis[1] = Ennemi(x=500, y=420, id=1)
        self.ennemis[2] = Ennemi(x=800, y=260, id=2)

    def creer_ames_libres(self):
        """Place des âmes libres à divers endroits de la map."""
        positions = [
            (320, 320), (640, 320), (900, 200),
            (250, 640), (480, 380), (730, 640), (960, 420),
        ]
        for x, y in positions:
            ame = AmeLibre(x, y)
            self.ames_libres[ame.id] = ame

    def creer_cle(self):
        """Place la clé en haut à droite de la map."""
        largeur_px = self.carte_jeu.largeur_map * TAILLE_TUILE
        self.cle = Cle(x=largeur_px - 4 * TAILLE_TUILE, y=2 * TAILLE_TUILE + 16)

    def gerer_client(self, connexion_client, id_joueur):
        spawn_x, spawn_y = self.spawn_point if id_joueur == 0 else points_sauvegarde.get_point_depart()[1]

        nouveau_joueur = Joueur(spawn_x, spawn_y, id_joueur)
        if id_joueur == 0:
            nouveau_joueur.argent = self.donnees_partie.get("argent", 0)
        ameliorations = self.donnees_partie.get("ameliorations", {})
        nouveau_joueur.peut_double_saut = ameliorations.get("double_saut", False)
        nouveau_joueur.peut_dash = ameliorations.get("dash", False)
        nouveau_joueur.peut_echo_dir = ameliorations.get("echo_dir", False)

        if MODE_DEV:
            nouveau_joueur.peut_double_saut = True
            nouveau_joueur.peut_dash = True
            nouveau_joueur.peut_echo_dir = True

        self.joueurs[id_joueur] = nouveau_joueur

        if id_joueur == 0:
            # Copie profonde pour éviter la mutation de la sauvegarde
            vis_sauvegarde = self.donnees_partie["vis_map"]
            if (len(vis_sauvegarde) != self.carte_jeu.hauteur_map or len(vis_sauvegarde[0]) != self.carte_jeu.largeur_map):
                self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()
            else:
                self.cartes_visibilite[id_joueur] = [row[:] for row in vis_sauvegarde]
        # Version précédente pour détecter les changements (delta vis_map)
        self.vis_map_precedente[id_joueur] = None

        _send_complet(connexion_client, id_joueur)
        connexion_client.settimeout(10.0)  # kick si inactif > 10s
        connexion_client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            while self.running:
                # ← ICI : appel correct de la fonction au niveau module
                try:
                    commandes = _recv_complet_serveur(connexion_client)
                except EOFError:
                    break

                with self.lock:
                    self.joueurs[id_joueur].commandes = commandes['clavier']

                    # Gestion Écho → révélation progressive
                    # Gestion Écho normal → révélation progressive
                    if commandes.get('echo'):
                        t_echo = pygame.time.get_ticks()
                        joueur = self.joueurs[id_joueur]
                        if t_echo - joueur.dernier_echo_temps > COOLDOWN_ECHO:
                            joueur.dernier_echo_temps = t_echo
                            self.echos_en_cours.append({
                                'id_joueur': id_joueur,
                                'cx': joueur.rect.centerx,
                                'cy': joueur.rect.centery,
                                'debut': t_echo,
                                'rayon_precedent': 0,
                                'type': 'normal',
                                'portee_max': PORTEE_ECHO,
                            })

                    # Gestion Écho Directionnel → révélation dans un cône
                    if commandes.get('echo_dir'):
                        t_echo_dir = pygame.time.get_ticks()
                        joueur = self.joueurs[id_joueur]
                        if (joueur.peut_echo_dir and
                                t_echo_dir - joueur.dernier_echo_dir_temps > COOLDOWN_ECHO_DIR):
                            joueur.dernier_echo_dir_temps = t_echo_dir
                            self.echos_en_cours.append({
                                'id_joueur': id_joueur,
                                'cx': joueur.rect.centerx,
                                'cy': joueur.rect.centery,
                                'debut': t_echo_dir,
                                'rayon_precedent': 0,
                                'type': 'dir',
                                'portee_max': PORTEE_ECHO_DIR,
                                'direction': joueur.direction,
                            })

                    if commandes.get('toggle_torche'):
                        self.torche_allumee = not self.torche_allumee

                # Récupérer l'état commun pré-calculé par boucle_jeu_serveur
                with self._broadcast_lock:
                    etat_commun = self._etat_broadcast

                if etat_commun is None:
                    time.sleep(0.001)
                    continue

                # Delta vis_map : spécifique à ce joueur, calculé ici
                with self.lock:
                    vis_actuelle = self.cartes_visibilite.get(id_joueur)
                    vis_prec = self.vis_map_precedente.get(id_joueur)
                    if vis_actuelle != vis_prec:
                        vis_a_envoyer = [row[:] for row in vis_actuelle]
                        self.vis_map_precedente[id_joueur] = [row[:] for row in vis_actuelle]
                    else:
                        vis_a_envoyer = None

                donnees_pour_client = {**etat_commun, 'vis_map': vis_a_envoyer}
                _send_complet(connexion_client, donnees_pour_client)

        except socket.error as e:
            print(f"[SERVEUR] Erreur socket {id_joueur}: {e}")
        finally:
            print(f"[SERVEUR] Client {id_joueur} deconnecte.")
            connexion_client.close()
            with self.lock:
                if connexion_client in self.clients:
                    del self.clients[connexion_client]
                if id_joueur in self.joueurs:
                    del self.joueurs[id_joueur]
                if id_joueur in self.cartes_visibilite:
                    del self.cartes_visibilite[id_joueur]
                if id_joueur in self.vis_map_precedente:
                    del self.vis_map_precedente[id_joueur]
                # Remettre l'ID dans le pool pour réutilisation
                if id_joueur not in self._ids_pool:
                    self._ids_pool.append(id_joueur)
                    self._ids_pool.sort()

    def boucle_jeu_serveur(self):
        horloge = pygame.time.Clock()
        while self.running:
            temps_actuel = pygame.time.get_ticks()

            with self.lock:
              # 0. Révélation progressive des échos
              echos_restants = []
              for echo in self.echos_en_cours:
                elapsed = temps_actuel - echo['debut']
                if elapsed <= ECHO_DUREE_REVEAL:
                    portee_max = echo.get('portee_max', PORTEE_ECHO)
                    rayon_max = int((elapsed / ECHO_DUREE_REVEAL) * portee_max)
                    rayon_prec = echo.get('rayon_precedent', 0)
                    if rayon_max > rayon_prec and echo['id_joueur'] in self.cartes_visibilite:
                        if echo.get('type') == 'dir':
                            self.carte_jeu.reveler_par_echo_dir_partiel(
                                echo['cx'], echo['cy'],
                                rayon_max,
                                self.cartes_visibilite[echo['id_joueur']],
                                echo['direction']
                            )
                        else:
                            self.carte_jeu.reveler_par_echo_partiel(
                                echo['cx'], echo['cy'],
                                rayon_max,
                                self.cartes_visibilite[echo['id_joueur']]
                            )
                        echo['rayon_precedent'] = rayon_max
                    echos_restants.append(echo)
            self.echos_en_cours = echos_restants

            # Flash sonar
            for echo in echos_restants:
                for id_ennemi, ennemi in self.ennemis.items():
                    dx = ennemi.rect.centerx - echo['cx']
                    dy = ennemi.rect.centery - echo['cy']
                    dist = (dx**2 + dy**2) ** 0.5
                    if dist <= PORTEE_ECHO:
                        ennemi.flash_echo_temps = temps_actuel

            with self.lock:
              # 1. Âmes libres : animation + collecte
              for ame in self.ames_libres.values():
                  ame.mettre_a_jour(temps_actuel)
              for id_joueur, joueur in list(self.joueurs.items()):
                  for id_ame, ame in list(self.ames_libres.items()):
                      if id_ame not in self.ames_libres:  # déjà ramassée ?
                          continue
                      if joueur.rect.colliderect(ame.rect):
                          joueur.argent += ame.valeur
                          print(f"[SERVEUR] Joueur {id_joueur} ramasse ame libre (+{ame.valeur})")
                          del self.ames_libres[id_ame]

            # 2. Clé : animation + collecte
            if self.cle and not self.cle.est_ramassee:
                self.cle.mettre_a_jour(temps_actuel)
                for id_joueur, joueur in list(self.joueurs.items()):
                    if joueur.rect.colliderect(self.cle.rect):
                        self.cle.est_ramassee = True
                        joueur.have_key = True
                        print(f"[SERVEUR] Joueur {id_joueur} a ramasse la cle !")

            # 3. Ennemis
            for id_ennemi, ennemi in list(self.ennemis.items()):
                ennemi.appliquer_logique(self.rects_collision, self.carte_jeu)

            # 4. Joueurs
            for id_joueur, joueur in list(self.joueurs.items()):
                joueur.appliquer_physique(self.rects_collision)

                # A. Attaque
                joueur.gerer_attaque(temps_actuel)

                if joueur.est_en_attaque and joueur.rect_attaque:
                    # Contre les Ennemis
                    for id_ennemi, ennemi in list(self.ennemis.items()):
                        if joueur.rect_attaque.colliderect(ennemi.rect):
                            mort = ennemi.prendre_degat(DEGATS_JOUEUR)
                            if mort:
                                print(f"[SERVEUR] Ennemi {id_ennemi} tue par Joueur {id_joueur}")
                                joueur.argent += ARGENT_PAR_ENNEMI
                                del self.ennemis[id_ennemi]

                    # Contre les Âmes Perdues
                    for id_ame, ame in list(self.ames_perdues.items()):
                        if ame.id_joueur == id_joueur:
                            if joueur.rect_attaque.colliderect(ame.rect):
                                print(f"[SERVEUR] Joueur {id_joueur} a recupere son ame ({ame.argent} argents)")
                                joueur.argent += ame.argent
                                joueur.ame_perdue = None
                                del self.ames_perdues[id_ame]

                # B. Dégâts reçus
                for id_ennemi, ennemi in list(self.ennemis.items()):
                    if joueur.rect.colliderect(ennemi.rect):
                        joueur.prendre_degat(1, temps_actuel)

                # C. Mort et Respawn
                if joueur.pv <= 0:
                    if joueur.pv <= 0:
                        if joueur.temps_mort is None:
                            joueur.temps_mort = temps_actuel

                            if joueur.ame_perdue and joueur.ame_perdue.id in self.ames_perdues:
                                del self.ames_perdues[joueur.ame_perdue.id]

                            nouvelle_ame = AmePerdue(joueur.rect.centerx, joueur.rect.centery, id_joueur, joueur.argent)
                            self.ames_perdues[nouvelle_ame.id] = nouvelle_ame
                            joueur.ame_perdue = nouvelle_ame
                            joueur.argent = 0

                        elif temps_actuel - joueur.temps_mort >= 3000:
                            id_checkpoint = self.donnees_partie["id_dernier_checkpoint"] if id_joueur == 0 else points_sauvegarde.get_point_depart()[0]
                            coords_spawn = points_sauvegarde.get_coords_par_id(id_checkpoint)
                            joueur.respawn(coords_spawn)
                            joueur.temps_mort = None

                # D. Sauvegarde (Hôte uniquement)
                if id_joueur == 0:
                    for id_save, rect_save in self.points_sauvegarde_map.items():
                        if joueur.rect.colliderect(rect_save):
                            if self.donnees_partie["id_dernier_checkpoint"] != id_save:
                                self.donnees_partie["id_dernier_checkpoint"] = id_save
                                self.donnees_partie["vis_map"] = [row[:] for row in self.cartes_visibilite[id_joueur]]
                                self.donnees_partie["argent"] = joueur.argent
                                self.donnees_partie["ameliorations"]["double_saut"] = joueur.peut_double_saut
                                self.donnees_partie["ameliorations"]["dash"] = joueur.peut_dash
                                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)

            # fin du bloc with self.lock (les indentations du bloc lock couvrent tout)
            # Construire le broadcast seulement au tick rate réseau
            if not hasattr(self, '_dernier_broadcast'):
                self._dernier_broadcast = 0
            intervalle = 1000 / TICK_RATE_RESEAU
            if temps_actuel - self._dernier_broadcast >= intervalle:
                self._dernier_broadcast = temps_actuel
                with self.lock:
                    etat_commun = {
                        'joueurs':        [j.get_etat() for j in self.joueurs.values()],
                        'ennemis':        [e.get_etat() for e in self.ennemis.values()],
                        'ames_perdues':   [a.get_etat() for a in self.ames_perdues.values()],
                        'ames_libres':    [a.get_etat() for a in self.ames_libres.values()],
                        'cle':            self.cle.get_etat() if self.cle else None,
                        'torche_allumee': self.torche_allumee,
                    }
                with self._broadcast_lock:
                    self._etat_broadcast = etat_commun

            horloge.tick(FPS)

    def demarrer(self):
        thread_boucle_jeu = threading.Thread(target=self.boucle_jeu_serveur)
        thread_boucle_jeu.daemon = True
        thread_boucle_jeu.start()

        self.serveur_socket.listen()
        print("[SERVEUR] En attente de connexions...")

        while True:
            connexion_client, adresse = self.serveur_socket.accept()
            print(f"[SERVEUR] Tentative de connexion depuis {adresse}")

            if not self._ids_pool:
                print(f"[SERVEUR] Connexion refusee de {adresse} - Serveur plein (3/3)")
                try:
                    _send_complet(connexion_client, {"erreur": "SERVEUR_PLEIN"})
                    time.sleep(0.1)
                    connexion_client.close()
                except Exception as e:
                    print(f"[SERVEUR] Erreur lors du refus : {e}")
                continue

            id_joueur = self._ids_pool.pop(0)  # prend le plus petit ID libre

            print(f"[SERVEUR] Joueur {id_joueur} accepte depuis {adresse} ({3 - len(self._ids_pool)}/3)")

            self.clients[connexion_client] = id_joueur
            thread_client = threading.Thread(target=self.gerer_client, args=(connexion_client, id_joueur))
            thread_client.daemon = True
            thread_client.start()


def main(id_slot, type_lancement):
    pygame.init()
    ip = obtenir_ip_locale()
    print(f"[SERVEUR] IP locale : {ip}")
    print(f"[SERVEUR] Les autres joueurs peuvent se connecter avec : {ip}")
    est_nouvelle_partie = (type_lancement == "nouvelle")
    serveur_jeu = Serveur(id_slot=id_slot, est_nouvelle_partie=est_nouvelle_partie)
    serveur_jeu.demarrer()