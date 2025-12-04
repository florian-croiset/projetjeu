# gestion_sauvegarde.py
# S'occupe de lire et écrire les fichiers slot_X.json.
# Utilise des chemins absolus pour éviter les erreurs de fichiers introuvables.

import json
import os
from parametres import NB_SLOTS_SAUVEGARDE
import points_sauvegarde
from carte import Carte

def get_chemin_absolu_slot(id_slot):
    """Renvoie le chemin complet vers le fichier de sauvegarde."""
    nom_fichier = f"slot_{id_slot + 1}.json"
    # On récupère le dossier où se trouve CE script (gestion_sauvegarde.py)
    dossier_script = os.path.dirname(os.path.abspath(__file__))
    chemin_complet = os.path.join(dossier_script, nom_fichier)
    return chemin_complet

def creer_sauvegarde_vierge():
    """Crée un dictionnaire de données pour une nouvelle partie."""
    id_depart, coords = points_sauvegarde.get_point_depart()
    
    # Crée une carte de visibilité vierge
    carte_temp = Carte()
    vis_map_vierge = carte_temp.creer_carte_visibilite_vierge()
    
    return {
        "id_dernier_checkpoint": id_depart,
        "vis_map": vis_map_vierge,
        "items": [],
        "ameliorations": {
            "double_saut": False
        }
    }

def sauvegarder_partie(id_slot, donnees_partie):
    """Sauvegarde le dictionnaire de données dans le fichier slot correspondant."""
    chemin_fichier = get_chemin_absolu_slot(id_slot)
    try:
        with open(chemin_fichier, 'w', encoding='utf-8') as f:
            json.dump(donnees_partie, f, indent=4)
        print(f"Partie sauvegardée dans {chemin_fichier}")
    except IOError as e:
        print(f"Erreur lors de la sauvegarde de {chemin_fichier}: {e}")

def charger_partie(id_slot):
    """Charge les données du fichier slot. Renvoie None si le slot est vide ou corrompu."""
    chemin_fichier = get_chemin_absolu_slot(id_slot)
    
    if not os.path.exists(chemin_fichier):
        return None
    
    try:
        with open(chemin_fichier, 'r', encoding='utf-8') as f:
            donnees = json.load(f)
            # TODO: Valider les données (vérifier que les clés existent)
            return donnees
    except (IOError, json.JSONDecodeError) as e:
        print(f"Erreur lors du chargement de {chemin_fichier}: {e}")
        return None

def get_infos_slots():
    """
    Renvoie une liste d'infos pour les menus "Continuer" et "Nouvelle Partie".
    Chaque élément est un dictionnaire {nom, id_checkpoint, est_vide}.
    """
    infos = []
    for i in range(NB_SLOTS_SAUVEGARDE):
        donnees = charger_partie(i)
        nom_slot = f"Slot {i + 1}"
        
        if donnees:
            # Cette ligne causait l'erreur avant car get_nom_par_id manquait
            nom_checkpoint = points_sauvegarde.get_nom_par_id(donnees.get("id_dernier_checkpoint", "spawn_01"))
            infos.append({
                "nom": nom_slot,
                "description": f"Checkpoint: {nom_checkpoint}",
                "est_vide": False
            })
        else:
            infos.append({
                "nom": nom_slot,
                "description": "[ Emplacement Vide ]",
                "est_vide": True
            })
    return infos