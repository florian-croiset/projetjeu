# points_sauvegarde.py
# Gère la logique des points de spawn.
# Les points de sauvegarde sont maintenant LUS DEPUIS LA CARTE.
# Ce fichier ne gère que le spawn initial et la conversion ID <-> Coords.

from parametres import TAILLE_TUILE

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