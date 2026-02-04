# points_sauvegarde.py
# Gère la logique des points de spawn.
# Convertit les IDs de checkpoint (format "x_y") en coordonnées pixels et en noms lisibles.

from parametres import TAILLE_TUILE

# Dictionnaire optionnel pour donner des noms sympas à certaines coordonnées
NOMS_CHECKPOINTS = {
    "3_21": "Point de Départ",
    "1_12": "Entrée de la Grotte",
    # Ajoutez d'autres noms ici si vous connaissez les coordonnées tuiles (x_y)
}

def get_point_depart():
    """Renvoie l'ID et les coordonnées du tout premier point de spawn."""
    # Coordonnées codées en dur pour le tout premier spawn
    # Correspond à la tuile (x=3, y=21) dans la map_data
    id_depart = "3_21" 
    coords = (3 * TAILLE_TUILE + (TAILLE_TUILE // 4), 21 * TAILLE_TUILE) # (x=104, y=672)
    return id_depart, coords

def get_coords_par_id(id_point):
    """
    Renvoie les (x, y) en pixels d'un checkpoint par son ID string (ex: "3_21").
    """
    try:
        x_tuile, y_tuile = map(int, id_point.split('_'))
        # On spawn centré sur le checkpoint
        x_pixel = x_tuile * TAILLE_TUILE + (TAILLE_TUILE // 4)
        y_pixel = y_tuile * TAILLE_TUILE
        return (x_pixel, y_pixel)
    except Exception as e:
        print(f"Erreur: ID de checkpoint invalide '{id_point}': {e}")
        # Sécurité : renvoyer au point de départ
        return get_point_depart()[1]

def get_nom_par_id(id_point):
    """
    Renvoie le nom lisible d'un checkpoint.
    Utilisé par le menu principal pour afficher où on en est.
    """
    if id_point in NOMS_CHECKPOINTS:
        return NOMS_CHECKPOINTS[id_point]
    
    # Si le point n'a pas de nom spécial, on renvoie une coordonnée générique
    return f"Zone {id_point}"