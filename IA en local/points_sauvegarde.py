# points_sauvegarde.py
# Définit les points de sauvegarde (checkpoints) du jeu.
# Le serveur utilisera ce fichier pour savoir où faire apparaître le joueur
# en fonction de l'ID stocké dans la sauvegarde.

POINTS_SAUVEGARDE = {
    "spawn_01": {
        "x": 100, 
        "y": 680, # Au sol
        "nom": "Point de Départ"
    },
    "cave_entree": {
        "x": 460, 
        "y": 580, # Sur la plateforme
        "nom": "Entrée de la Grotte"
    }
    # Ajoutez d'autres checkpoints ici
}

def get_point_depart():
    """Renvoie l'ID et les coordonnées du premier point de spawn."""
    id_depart = "spawn_01"
    coords = (POINTS_SAUVEGARDE[id_depart]['x'], POINTS_SAUVEGARDE[id_depart]['y'])
    return id_depart, coords

def get_coords_par_id(id_point):
    """Renvoie les (x, y) d'un checkpoint par son ID."""
    if id_point in POINTS_SAUVEGARDE:
        return (POINTS_SAUVEGARDE[id_point]['x'], POINTS_SAUVEGARDE[id_point]['y'])
    else:
        # Sécurité : renvoyer au point de départ si l'ID est invalide
        return get_point_depart()[1]

def get_nom_par_id(id_point):
    """Renvoie le nom lisible d'un checkpoint par son ID."""
    if id_point in POINTS_SAUVEGARDE:
        return POINTS_SAUVEGARDE[id_point]['nom']
    else:
        return "Lieu inconnu"