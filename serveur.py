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


def _recv_complet_serveur(sock):
    """Reçoit un paquet pickle complet depuis le client, quelle que soit sa taille."""
    morceaux = b""
    sock.settimeout(2.0)
    try:
        while True:
            morceau = sock.recv(65536)
            if not morceau:
                break
            morceaux += morceau
            try:
                pickle.loads(morceaux)
                break  # données complètes et décodables
            except Exception:
                continue  # on attend la suite
    except socket.timeout:
        pass
    finally:
        sock.settimeout(None)
    if not morceaux:
        raise EOFError("Connexion fermée")
    return pickle.loads(morceaux)


class Serveur:
    def __init__(self, id_slot, est_nouvelle_partie):
        # ===== RÉSEAU =====
        self.serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.serveur_socket.bind(('0.0.0.0', PORT_SERVEUR))
            ip_serveur = obtenir_ip_locale()
            print(f"[SERVEUR] Démarré sur le port {PORT_SERVEUR}")
            print(f"[SERVEUR] IP locale : {ip_serveur}")
        except OSError as e:
            print(f"[SERVEUR] ERREUR lors du bind: {e}")
            raise

        # ===== DONNÉES DE JEU =====
        self.clients = {}
        self.joueurs = {}
        self.cartes_visibilite = {}
        self.ennemis = {}
        self.ames_perdues = {}
        self.ames_libres = {}
        self.cle = None
        self.echos_en_cours = []

        # ===== CARTE =====
        import os
        dossier_script = os.path.dirname(os.path.abspath(__file__))
        chemin_map = os.path.join(dossier_script, "map.json")
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
        self.cle = Cle(x=806, y=80)
        self.prochain_id_joueur = 0
        self.torche_allumee = False
        self.torche_x = 32
        self.torche_y = 672
        self.running = True

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

        self.joueurs[id_joueur] = nouveau_joueur

        if id_joueur == 0:
            self.cartes_visibilite[id_joueur] = self.donnees_partie["vis_map"]
        else:
            self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()

        connexion_client.send(pickle.dumps(id_joueur))

        try:
            while self.running:
                # ← ICI : appel correct de la fonction au niveau module
                try:
                    commandes = _recv_complet_serveur(connexion_client)
                except EOFError:
                    break

                self.joueurs[id_joueur].commandes = commandes['clavier']

                # Gestion Écho → révélation progressive
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
                        })

                if commandes.get('toggle_torche'):
                    self.torche_allumee = not self.torche_allumee

                # Préparation données
                etat_joueurs = [j.get_etat() for j in self.joueurs.values()]
                etat_ennemis = [e.get_etat() for e in self.ennemis.values()]
                etat_ames = [a.get_etat() for a in self.ames_perdues.values()]
                etat_ames_libres = [a.get_etat() for a in self.ames_libres.values()]
                etat_cle = self.cle.get_etat() if self.cle else None

                donnees_pour_client = {
                    'joueurs': etat_joueurs,
                    'vis_map': self.cartes_visibilite[id_joueur],
                    'ennemis': etat_ennemis,
                    'ames_perdues': etat_ames,
                    'ames_libres': etat_ames_libres,
                    'cle': etat_cle,
                    'torche_allumee': self.torche_allumee,
                }

                connexion_client.send(pickle.dumps(donnees_pour_client))

        except socket.error as e:
            print(f"[SERVEUR] Erreur socket {id_joueur}: {e}")
        finally:
            print(f"[SERVEUR] Client {id_joueur} déconnecté.")
            connexion_client.close()
            if connexion_client in self.clients:
                del self.clients[connexion_client]
            if id_joueur in self.joueurs:
                del self.joueurs[id_joueur]
            if id_joueur in self.cartes_visibilite:
                del self.cartes_visibilite[id_joueur]

    def boucle_jeu_serveur(self):
        horloge = pygame.time.Clock()
        while self.running:
            temps_actuel = pygame.time.get_ticks()

            # 0. Révélation progressive des échos
            echos_restants = []
            for echo in self.echos_en_cours:
                elapsed = temps_actuel - echo['debut']
                if elapsed <= ECHO_DUREE_REVEAL:
                    rayon_max = int((elapsed / ECHO_DUREE_REVEAL) * PORTEE_ECHO)
                    rayon_prec = echo.get('rayon_precedent', 0)
                    if rayon_max > rayon_prec and echo['id_joueur'] in self.cartes_visibilite:
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

            # 1. Âmes libres : animation + collecte
            for ame in self.ames_libres.values():
                ame.mettre_a_jour(temps_actuel)
            for id_joueur, joueur in list(self.joueurs.items()):
                for id_ame, ame in list(self.ames_libres.items()):
                    if joueur.rect.colliderect(ame.rect):
                        joueur.argent += ame.valeur
                        print(f"[SERVEUR] Joueur {id_joueur} ramasse âme libre (+{ame.valeur})")
                        del self.ames_libres[id_ame]

            # 2. Clé : animation + collecte
            if self.cle and not self.cle.est_ramassee:
                self.cle.mettre_a_jour(temps_actuel)
                for id_joueur, joueur in list(self.joueurs.items()):
                    if joueur.rect.colliderect(self.cle.rect):
                        self.cle.est_ramassee = True
                        joueur.have_key = True
                        print(f"[SERVEUR] Joueur {id_joueur} a ramassé la clé !")

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
                                print(f"[SERVEUR] Ennemi {id_ennemi} tué par Joueur {id_joueur}")
                                joueur.argent += ARGENT_PAR_ENNEMI
                                del self.ennemis[id_ennemi]

                    # Contre les Âmes Perdues
                    for id_ame, ame in list(self.ames_perdues.items()):
                        if ame.id_joueur == id_joueur:
                            if joueur.rect_attaque.colliderect(ame.rect):
                                print(f"[SERVEUR] Joueur {id_joueur} a récupéré son âme ({ame.argent} argents)")
                                joueur.argent += ame.argent
                                joueur.ame_perdue = None
                                del self.ames_perdues[id_ame]

                # B. Dégâts reçus
                for id_ennemi, ennemi in list(self.ennemis.items()):
                    if joueur.rect.colliderect(ennemi.rect):
                        joueur.prendre_degat(1, temps_actuel)

                # C. Mort et Respawn
                if joueur.pv <= 0:
                    if not hasattr(joueur, 'temps_mort') or joueur.temps_mort is None:
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
                                self.donnees_partie["vis_map"] = self.cartes_visibilite[id_joueur]
                                self.donnees_partie["argent"] = joueur.argent
                                self.donnees_partie["ameliorations"]["double_saut"] = joueur.peut_double_saut
                                self.donnees_partie["ameliorations"]["dash"] = joueur.peut_dash
                                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)

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

            if len(self.clients) >= 3:
                print(f"[SERVEUR] Connexion refusee de {adresse} - Serveur plein (3/3)")
                try:
                    connexion_client.send(pickle.dumps({"erreur": "SERVEUR_PLEIN"}))
                    time.sleep(0.1)
                    connexion_client.close()
                except Exception as e:
                    print(f"[SERVEUR] Erreur lors du refus : {e}")
                continue

            id_joueur = self.prochain_id_joueur
            self.prochain_id_joueur += 1

            print(f"[SERVEUR] Joueur {id_joueur} accepté depuis {adresse} ({len(self.clients)+1}/3)")

            self.clients[connexion_client] = id_joueur
            thread_client = threading.Thread(target=self.gerer_client, args=(connexion_client, id_joueur))
            thread_client.daemon = True
            thread_client.start()


def main(id_slot, type_lancement):
    #pygame.init()
    import os
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    ip = obtenir_ip_locale()
    print(f"[SERVEUR] IP locale : {ip}")
    print(f"[SERVEUR] Les autres joueurs peuvent se connecter avec : {ip}")
    est_nouvelle_partie = (type_lancement == "nouvelle")
    serveur_jeu = Serveur(id_slot=id_slot, est_nouvelle_partie=est_nouvelle_partie)
    serveur_jeu.demarrer()