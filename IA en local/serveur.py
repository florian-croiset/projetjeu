# serveur.py
# Le CERVEAU du jeu. À lancer par l'hôte.
# Gère la logique, la physique, et envoie l'état du jeu aux clients.

import socket
import threading
import pickle # Pour sérialiser (convertir) les objets Python pour le réseau
import time
import sys # Pour lire les arguments de la ligne de commande
import pygame

from joueur import Joueur
from carte import Carte
from parametres import *
import gestion_sauvegarde
import points_sauvegarde
from ennemi import Ennemi # Import de la nouvelle classe

class Serveur:
    def __init__(self, id_slot, est_nouvelle_partie):
        self.serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serveur_socket.bind(('', PORT_SERVEUR)) # Écoute sur toutes les interfaces
        self.clients = {} # Dictionnaire {connexion_client: id_joueur}
        self.joueurs = {} # Dictionnaire {id_joueur: objet Joueur}
        self.cartes_visibilite = {} # Dictionnaire {id_joueur: vis_map}
        self.ennemis = {} # Dictionnaire {id_ennemi: objet Ennemi}
        
        self.carte_jeu = Carte()
        self.rects_collision = self.carte_jeu.get_rects_collisions()
        
        # --- Chargement de la Sauvegarde ---
        self.id_slot = id_slot
        self.donnees_partie = None
        self.spawn_point = None
        
        if est_nouvelle_partie:
            print(f"[SERVEUR] Création d'une nouvelle partie (Slot {id_slot + 1})")
            self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
            gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)
        else:
            print(f"[SERVEUR] Chargement de la partie (Slot {id_slot + 1})")
            self.donnees_partie = gestion_sauvegarde.charger_partie(self.id_slot)
            if self.donnees_partie is None:
                print("[SERVEUR] ERREUR: Slot de sauvegarde non trouvé. Création d'une nouvelle partie.")
                self.donnees_partie = gestion_sauvegarde.creer_sauvegarde_vierge()
                gestion_sauvegarde.sauvegarder_partie(self.id_slot, self.donnees_partie)

        # Définir le point de spawn de l'hôte
        id_checkpoint = self.donnees_partie["id_dernier_checkpoint"]
        self.spawn_point = points_sauvegarde.get_coords_par_id(id_checkpoint)
        
        # --- Création des ennemis ---
        self.creer_ennemis()
        
        # --- Fin Chargement Sauvegarde ---
        
        self.prochain_id_joueur = 0
        self.running = True
        
        print(f"[SERVEUR] Démarré sur le port {PORT_SERVEUR}")
        
    def creer_ennemis(self):
        """Place les ennemis sur la carte."""
        # Pour l'instant, on en ajoute un en dur pour tester
        # On le place sur la plateforme au-dessus du spawn
        ennemi_1 = Ennemi(x=200, y=680, id=0)
        self.ennemis[0] = ennemi_1
        
        ennemi_2 = Ennemi(x=500, y=420, id=1) # Sur la plateforme du milieu
        self.ennemis[1] = ennemi_2

    def gerer_client(self, connexion_client, id_joueur):
        """Gère la connexion pour un client unique (dans un thread séparé)."""
        print(f"[SERVEUR] Nouveau client connecté, ID: {id_joueur}")
        
        # 1. Créer le joueur et sa carte de visibilité
        
        # L'hôte (ID 0) apparaît au point de sauvegarde
        # Les autres joueurs apparaissent au point de spawn initial (pour l'instant)
        spawn_x, spawn_y = self.spawn_point
        if id_joueur != 0:
            spawn_x, spawn_y = points_sauvegarde.get_point_depart()[1] # Spawn de base pour les invités
            
        nouveau_joueur = Joueur(spawn_x, spawn_y, id_joueur)
        self.joueurs[id_joueur] = nouveau_joueur
        
        # ATTRIBUTION DE LA CARTE DE VISIBILITÉ
        if id_joueur == 0:
            # L'hôte (ID 0) récupère la carte de visibilité de la sauvegarde
            self.cartes_visibilite[id_joueur] = self.donnees_partie["vis_map"]
            print(f"[SERVEUR] Hôte (ID 0) connecté, chargement de la vis_map sauvegardée.")
        else:
            # Les autres joueurs ont une carte vierge
            self.cartes_visibilite[id_joueur] = self.carte_jeu.creer_carte_visibilite_vierge()
            print(f"[SERVEUR] Client (ID {id_joueur}) connecté, création d'une vis_map vierge.")

        # 2. Envoyer l'ID au client
        connexion_client.send(pickle.dumps(id_joueur))
        
        try:
            while self.running:
                # 3. Recevoir les commandes du client
                try:
                    commandes = pickle.loads(connexion_client.recv(2048))
                except EOFError:
                    break # Le client s'est déconnecté
                
                # Mettre à jour les commandes du joueur
                self.joueurs[id_joueur].commandes = commandes['clavier']
                
                # Gérer l'écho
                if commandes['echo']:
                    print(f"[SERVEUR] Joueur {id_joueur} utilise l'écho.")
                    centre_x = self.joueurs[id_joueur].rect.centerx
                    centre_y = self.joueurs[id_joueur].rect.centery
                    self.carte_jeu.reveler_par_echo(centre_x, centre_y, self.cartes_visibilite[id_joueur])

                # 4. Préparer l'état du jeu à renvoyer
                
                # Obtenir l'état de tous les joueurs
                etat_joueurs = [j.get_etat() for j in self.joueurs.values()]
                # Obtenir l'état de tous les ennemis
                etat_ennemis = [e.get_etat() for e in self.ennemis.values()]
                
                # Préparer les données spécifiques à CE client
                donnees_pour_client = {
                    'joueurs': etat_joueurs,
                    'vis_map': self.cartes_visibilite[id_joueur], # N'envoie que SA carte
                    'ennemis': etat_ennemis
                }

                # 5. Envoyer l'état du jeu au client
                connexion_client.send(pickle.dumps(donnees_pour_client))
                
        except socket.error as e:
            print(f"[SERVEUR] Erreur de socket client {id_joueur}: {e}")
        finally:
            # Nettoyer en cas de déconnexion
            print(f"[SERVEUR] Client {id_joueur} déconnecté.")
            connexion_client.close()
            del self.clients[connexion_client]
            del self.joueurs[id_joueur]
            del self.cartes_visibilite[id_joueur]

    def boucle_jeu_serveur(self):
        """
        Boucle principale du serveur.
        Met à jour la physique de tous les joueurs.
        """
        horloge = pygame.time.Clock()
        while self.running:
            # Mettre à jour la physique de chaque joueur
            for id_joueur, joueur in list(self.joueurs.items()):
                joueur.appliquer_physique(self.rects_collision)
            
            # Mettre à jour la logique de chaque ennemi
            for id_ennemi, ennemi in list(self.ennemis.items()):
                ennemi.appliquer_logique(self.rects_collision, self.carte_jeu)
            
            # Limiter la boucle (ticks du serveur)
            horloge.tick(FPS)

    def demarrer(self):
        """Accepte les nouvelles connexions et lance la boucle de jeu."""
        
        # Lancer la boucle de jeu (physique) dans un thread séparé
        thread_boucle_jeu = threading.Thread(target=self.boucle_jeu_serveur)
        thread_boucle_jeu.daemon = True # S'arrête si le script principal s'arrête
        thread_boucle_jeu.start()
        
        # Accepter les connexions
        self.serveur_socket.listen()
        
        while True:
            connexion_client, adresse = self.serveur_socket.accept()
            
            id_joueur = self.prochain_id_joueur
            self.prochain_id_joueur += 1
            
            self.clients[connexion_client] = id_joueur
            
            # Démarrer un thread pour gérer ce client
            thread_client = threading.Thread(target=self.gerer_client, args=(connexion_client, id_joueur))
            thread_client.daemon = True
            thread_client.start()

# --- Point d'entrée ---
if __name__ == "__main__":
    # Initialiser pygame pour l'horloge (pas besoin de fenêtre)
    pygame.init() 
    
    # --- Lecture des arguments de lancement ---
    # sys.argv[0] est le nom du script (serveur.py)
    # sys.argv[1] sera l'id_slot (0, 1, ou 2)
    # sys.argv[2] sera 'nouvelle' ou 'charger'
    
    if len(sys.argv) != 3:
        print("Usage: python serveur.py <id_slot> <nouvelle|charger>")
        sys.exit(1)
        
    try:
        id_slot_arg = int(sys.argv[1])
        type_lancement = sys.argv[2]
        
        if id_slot_arg not in range(NB_SLOTS_SAUVEGARDE):
            raise ValueError("ID de slot invalide")
            
        est_nouvelle_partie_arg = (type_lancement == 'nouvelle')
        
    except ValueError as e:
        print(f"Erreur d'arguments: {e}")
        sys.exit(1)

    # --- Fin Lecture Arguments ---
    
    serveur_jeu = Serveur(id_slot=id_slot_arg, est_nouvelle_partie=est_nouvelle_partie_arg)
    try:
        serveur_jeu.demarrer()
    except KeyboardInterrupt:
        print("[SERVEUR] Arrêt manuel.")
        serveur_jeu.running = False
        serveur_jeu.serveur_socket.close()