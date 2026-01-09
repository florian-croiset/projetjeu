# serveur.py
# Gestion centrale : Physique, IA, Combat, Sauvegarde.
# CORRECTION : Ajout du gain d'argent à la mort d'un ennemi.

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

def obtenir_ip_locale():
    """Retourne l'IP locale de la machine sur le réseau."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_locale = s.getsockname()[0]
        s.close()
        return ip_locale
    except Exception:
        return "127.0.0.1"  # il se passe rien si pas de connexion

ip_serveur = obtenir_ip_locale()
print(f"[SERVEUR] IP locale : {ip_serveur}")
print(f"[SERVEUR] Les autres joueurs peuvent se connecter avec : {ip_serveur}")

class Serveur:
    def __init__(self, id_slot, est_nouvelle_partie):
        #Pour le réseau debut
        self.serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.serveur_socket.bind(('0.0.0.0', PORT_SERVEUR))
            ip_serveur = obtenir_ip_locale()
            print(f"[SERVEUR] Démarré sur le port {PORT_SERVEUR}")
            print(f"[SERVEUR] IP locale : {ip_serveur}")
            print(f"[SERVEUR] Les autres joueurs peuvent se connecter avec : {ip_serveur}")
        except OSError as e:
            print(f"[SERVEUR] ERREUR lors du bind: {e}")
            raise 
        #fin

        self.clients = {}
        self.joueurs = {}
        self.cartes_visibilite = {}
        self.ennemis = {}
        self.ames_perdues = {}
        
        self.carte_jeu = Carte()
        self.rects_collision = self.carte_jeu.get_rects_collisions()
        self.points_sauvegarde_map = self.scanner_points_sauvegarde()
        
        # --- Chargement Sauvegarde ---
        self.id_slot = id_slot
        self.donnees_partie = None
        self.spawn_point = None
        
        if est_nouvelle_partie:
            self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
            gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)
        else:
            self.donnees_partie = gestion_sauvegarde.charger_partie(self.id_slot)
            if self.donnees_partie is None:
                self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)

        id_checkpoint = self.donnees_partie["id_dernier_checkpoint"]
        self.spawn_point = points_sauvegarde.get_coords_par_id(id_checkpoint)
        
        # --- Init ---
        self.creer_ennemis()
        self.prochain_id_joueur = 0
        self.running = True
        print(f"[SERVEUR] Démarré sur le port {PORT_SERVEUR}")

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
        # Création de quelques ennemis pour tester
        self.ennemis[0] = Ennemi(x=200, y=680, id=0)
        self.ennemis[1] = Ennemi(x=500, y=420, id=1)
        self.ennemis[2] = Ennemi(x=800, y=260, id=2)

    def gerer_client(self, connexion_client, id_joueur):
        spawn_x, spawn_y = self.spawn_point if id_joueur == 0 else points_sauvegarde.get_point_depart()[1]
        
        nouveau_joueur = Joueur(spawn_x, spawn_y, id_joueur)
        # Si c'est l'hôte, on charge aussi son argent
        if id_joueur == 0:
            nouveau_joueur.argent = self.donnees_partie.get("argent", 0) 
            
        self.joueurs[id_joueur] = nouveau_joueur
        
        if id_joueur == 0:
            self.cartes_visibilite[id_joueur] = self.donnees_partie["vis_map"]
        else:
            self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()

        connexion_client.send(pickle.dumps(id_joueur))
        
        try:
            while self.running:
                try:
                    commandes = pickle.loads(connexion_client.recv(2048))
                except EOFError:
                    break
                
                self.joueurs[id_joueur].commandes = commandes['clavier']
                
                # Gestion Écho
                if commandes['echo']:
                    temps_actuel = pygame.time.get_ticks()
                    joueur = self.joueurs[id_joueur]
                    if temps_actuel - joueur.dernier_echo_temps > COOLDOWN_ECHO:
                        joueur.dernier_echo_temps = temps_actuel
                        self.carte_jeu.reveler_par_echo(joueur.rect.centerx, joueur.rect.centery, self.cartes_visibilite[id_joueur])

                # Préparation données
                etat_joueurs = [j.get_etat() for j in self.joueurs.values()]
                etat_ennemis = [e.get_etat() for e in self.ennemis.values()]
                etat_ames = [a.get_etat() for a in self.ames_perdues.values()]
                
                donnees_pour_client = {
                    'joueurs': etat_joueurs,
                    'vis_map': self.cartes_visibilite[id_joueur],
                    'ennemis': etat_ennemis,
                    'ames_perdues': etat_ames
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
            
            # 1. Ennemis
            for id_ennemi, ennemi in list(self.ennemis.items()):
                ennemi.appliquer_logique(self.rects_collision, self.carte_jeu)

            # 2. Joueurs (Physique, Combat, Mort)
            for id_joueur, joueur in list(self.joueurs.items()):
                joueur.appliquer_physique(self.rects_collision)
                
                # A. Gestion de l'Attaque du Joueur
                a_attaque = joueur.gerer_attaque(temps_actuel)
                
                if joueur.est_en_attaque and joueur.rect_attaque:
                    # Contre les Ennemis
                    for id_ennemi, ennemi in list(self.ennemis.items()):
                        if joueur.rect_attaque.colliderect(ennemi.rect):
                            mort = ennemi.prendre_degat(DEGATS_JOUEUR)
                            if mort:
                                print(f"[SERVEUR] Ennemi {id_ennemi} tué par Joueur {id_joueur}")
                                # --- CORRECTION ICI ---
                                joueur.argent += ARGENT_PAR_ENNEMI 
                                del self.ennemis[id_ennemi]
                                
                    # Contre les Âmes Perdues (Récupération)
                    for id_ame, ame in list(self.ames_perdues.items()):
                        if ame.id_joueur == id_joueur:
                            if joueur.rect_attaque.colliderect(ame.rect):
                                print(f"[SERVEUR] Joueur {id_joueur} a récupéré son âme ({ame.argent} argents)")
                                joueur.argent += ame.argent
                                joueur.ame_perdue = None 
                                del self.ames_perdues[id_ame]

                # B. Gestion des Dégâts reçus (Joueur touche Ennemi)
                for id_ennemi, ennemi in list(self.ennemis.items()):
                    if joueur.rect.colliderect(ennemi.rect):
                        joueur.prendre_degat(1, temps_actuel)
                
                # C. Mort et Respawn
                if joueur.pv <= 0:
                    # Perte de l'ancienne âme si elle existait
                    if joueur.ame_perdue and joueur.ame_perdue.id in self.ames_perdues:
                        del self.ames_perdues[joueur.ame_perdue.id]
                    
                    # Création nouvelle âme avec l'argent actuel
                    nouvelle_ame = AmePerdue(joueur.rect.centerx, joueur.rect.centery, id_joueur, joueur.argent)
                    self.ames_perdues[nouvelle_ame.id] = nouvelle_ame
                    joueur.ame_perdue = nouvelle_ame
                    
                    joueur.argent = 0 # Perte de l'argent porté
                    
                    # Respawn
                    id_checkpoint = self.donnees_partie["id_dernier_checkpoint"] if id_joueur == 0 else points_sauvegarde.get_point_depart()[0]
                    coords_spawn = points_sauvegarde.get_coords_par_id(id_checkpoint)
                    joueur.respawn(coords_spawn)

                # D. Sauvegarde (Hôte)
                if id_joueur == 0: 
                    for id_save, rect_save in self.points_sauvegarde_map.items():
                        if joueur.rect.colliderect(rect_save):
                            if self.donnees_partie["id_dernier_checkpoint"] != id_save:
                                self.donnees_partie["id_dernier_checkpoint"] = id_save
                                self.donnees_partie["vis_map"] = self.cartes_visibilite[id_joueur]
                                self.donnees_partie["argent"] = joueur.argent # Sauvegarde argent
                                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)
            
            horloge.tick(FPS)

    def demarrer(self):
        thread_boucle_jeu = threading.Thread(target=self.boucle_jeu_serveur)
        thread_boucle_jeu.daemon = True
        thread_boucle_jeu.start()
        
        self.serveur_socket.listen()
        print("[SERVEUR] En attente de connexions...")
        
        while True:
            # Accepter la connexion
            connexion_client, adresse = self.serveur_socket.accept()
            print(f"[SERVEUR] Tentative de connexion depuis {adresse}")
            
            # ⬇️ VÉRIFICATION : LIMITE DE 3 JOUEURS
            if len(self.clients) >= 3:
                print(f"[SERVEUR] Connexion refusée de {adresse} - Serveur plein (3/3)")
                try:
                    connexion_client.send(pickle.dumps({"erreur": "SERVEUR_PLEIN"}))
                    time.sleep(0.1)
                    connexion_client.close()
                except Exception as e:
                    print(f"[SERVEUR] Erreur lors du refus : {e}")
                continue
            
            # Accepter le joueur
            id_joueur = self.prochain_id_joueur
            self.prochain_id_joueur += 1
            
            print(f"[SERVEUR] Joueur {id_joueur} accepté depuis {adresse} ({len(self.clients)+1}/3)")
            
            self.clients[connexion_client] = id_joueur
            thread_client = threading.Thread(target=self.gerer_client, args=(connexion_client, id_joueur))
            thread_client.daemon = True
            thread_client.start()


#if __name__ == "__main__":
#    pygame.init() 
 #   if len(sys.argv) != 3:
  #      sys.exit(1)
   # try:
   #     id_slot_arg = int(sys.argv[1])
    #    type_lancement = sys.argv[2]
  #      est_nouvelle_partie_arg = (type_lancement == 'nouvelle')
 #   except ValueError:
       # sys.exit(1)
#
 #   serveur_jeu = Serveur(id_slot=id_slot_arg, est_nouvelle_partie=est_nouvelle_partie_arg)
  #  try:
   #     serveur_jeu.demarrer()
    #except KeyboardInterrupt:
     #   serveur_jeu.running = False
      #  serveur_jeu.serveur_socket.close()


def main(id_slot, type_lancement):
    pygame.init()
    est_nouvelle_partie = (type_lancement == "nouvelle")
    serveur_jeu = Serveur(id_slot=id_slot, est_nouvelle_partie=est_nouvelle_partie)
    serveur_jeu.demarrer()