# core/astar.py
# Pathfinding A* adapté au platformer 2D d'Écho.
#
# Nœuds = tuiles (tx, ty). Le graphe est implicite : pour chaque nœud on
# génère ses voisins à partir de carte.est_solide(). Contraintes :
#   - Gauche / Droite vers une tuile air        → coût 1.0
#   - Bas vers une tuile air (chute libre)      → coût 0.8
#   - Haut vers une tuile air                   → coût 1.6 × step, seulement
#     si la tuile sous le nœud courant est solide (saut depuis le sol).
#     Multi-tuiles jusqu'à `hauteur_saut` ; toutes les tuiles intermédiaires
#     doivent être air.
#
# Heuristique : Manhattan (admissible — plus petite arête = 0.8).
#
# Si l'arrivée n'est pas atteinte dans `max_iter` expansions, on renvoie
# le « meilleur effort » : chemin reconstruit vers le nœud visité dont
# l'heuristique vers l'arrivée est minimale. Évite que les ennemis restent
# figés quand le joueur est hors de portée.

import heapq


def heuristique(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _est_air(carte, x, y):
    if 0 <= x < carte.largeur_map and 0 <= y < carte.hauteur_map:
        return not carte.est_solide(x, y)
    return False


def _depart_valide(carte, depart):
    """Si la tuile de départ est solide (cas pathologique), on essaie une
    tuile air adjacente. Renvoie None si rien d'utilisable."""
    sx, sy = depart
    if _est_air(carte, sx, sy):
        return depart
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1)):
        nx, ny = sx + dx, sy + dy
        if _est_air(carte, nx, ny):
            return (nx, ny)
    return None


def trouver_chemin(carte, depart, arrivee, max_iter=1500, hauteur_saut=2):
    """A* sur la tilemap. Renvoie une liste [(tx, ty), ...] (chemin complet
    depuis le départ jusqu'à l'arrivée) ou [] si rien d'exploitable.

    Si l'arrivée est inatteignable mais que des nœuds ont été visités, on
    renvoie le chemin partiel vers le plus proche du but (meilleur effort).
    """
    depart = _depart_valide(carte, depart)
    if depart is None:
        return []
    if depart == arrivee:
        return [depart]

    largeur = carte.largeur_map
    hauteur = carte.hauteur_map
    est_solide = carte.est_solide

    h0 = heuristique(depart, arrivee)
    compteur = 0
    open_heap = [(h0, compteur, depart)]
    g_score = {depart: 0.0}
    parents = {depart: None}
    visites = set()

    meilleur_noeud = depart
    meilleur_h = h0

    def pousser(noeud, new_g, parent):
        nonlocal compteur
        if noeud in visites:
            return
        if new_g < g_score.get(noeud, float('inf')):
            g_score[noeud] = new_g
            parents[noeud] = parent
            compteur += 1
            heapq.heappush(
                open_heap,
                (new_g + heuristique(noeud, arrivee), compteur, noeud),
            )

    while open_heap and len(visites) < max_iter:
        _, _, courant = heapq.heappop(open_heap)
        if courant in visites:
            continue
        visites.add(courant)

        if courant == arrivee:
            return _reconstruire(parents, courant)

        cx, cy = courant
        g = g_score[courant]
        sur_sol = (cy + 1 < hauteur and est_solide(cx, cy + 1))

        # Gauche / Droite
        for ndx in (-1, 1):
            nx = cx + ndx
            if 0 <= nx < largeur and not est_solide(nx, cy):
                pousser((nx, cy), g + 1.0, courant)

        # Bas (chute)
        ny = cy + 1
        if ny < hauteur and not est_solide(cx, ny):
            pousser((cx, ny), g + 0.8, courant)

        # Haut (saut) — seulement depuis le sol
        if sur_sol:
            for step in range(1, hauteur_saut + 1):
                ny = cy - step
                if ny < 0 or est_solide(cx, ny):
                    break
                pousser((cx, ny), g + 1.6 * step, courant)

        h_cour = heuristique(courant, arrivee)
        if h_cour < meilleur_h:
            meilleur_h = h_cour
            meilleur_noeud = courant

    if meilleur_noeud == depart:
        return []
    return _reconstruire(parents, meilleur_noeud)


def _reconstruire(parents, noeud):
    chemin = []
    n = noeud
    while n is not None:
        chemin.append(n)
        n = parents.get(n)
    chemin.reverse()
    return chemin
