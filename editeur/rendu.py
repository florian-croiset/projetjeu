# rendu.py
# Fonctions pures de rendu de la carte (image layers, tiles, grille, curseur)
# avec une caméra (cam_x, cam_y) en pixels-monde et un facteur de zoom.

import pygame
from parametres import COULEUR_CYAN


# Cache de tuiles redimensionnées : (id(surface), zoom_quantifié) -> Surface
_cache_tuiles_zoomees = {}
# Cache de tuiles redimensionnées + dimmées (pour les couches inactives) :
# (id(surface), zoom_quantifié, alpha) -> Surface
_cache_tuiles_dimmees = {}
# Cache d'image layers redimensionnées : (id(image), zoom_quantifié) -> Surface
_cache_images_zoomees = {}


def _zoom_quantifie(zoom):
    """Quantifie le zoom au centième pour limiter la taille du cache."""
    return round(zoom * 100) / 100.0


def _surface_zoomee(surface_originale, zoom, taille_tuile):
    """Retourne la version redimensionnée d'une tuile au zoom donné, avec cache."""
    cle = (id(surface_originale), _zoom_quantifie(zoom))
    surf = _cache_tuiles_zoomees.get(cle)
    if surf is None:
        taille = max(1, int(round(taille_tuile * zoom)))
        surf = pygame.transform.scale(surface_originale, (taille, taille))
        _cache_tuiles_zoomees[cle] = surf
    return surf


def _surface_zoomee_dimmee(surface_originale, zoom, taille_tuile, alpha=110):
    """Variante de _surface_zoomee dont l'alpha est appliqué une seule fois et
    mise en cache : évite un copy()+set_alpha par tuile par frame pour les
    couches inactives."""
    cle = (id(surface_originale), _zoom_quantifie(zoom), alpha)
    surf = _cache_tuiles_dimmees.get(cle)
    if surf is None:
        base = _surface_zoomee(surface_originale, zoom, taille_tuile)
        surf = base.copy()
        surf.set_alpha(alpha)
        _cache_tuiles_dimmees[cle] = surf
    return surf


def _image_zoomee(image_originale, zoom):
    """Retourne la version redimensionnée d'une image layer parallax (PNG plein
    écran), avec cache. Évite de re-scaler à chaque frame quand le zoom est
    constant."""
    cle = (id(image_originale), _zoom_quantifie(zoom))
    img = _cache_images_zoomees.get(cle)
    if img is None:
        w = max(1, int(image_originale.get_width() * zoom))
        h = max(1, int(image_originale.get_height() * zoom))
        img = pygame.transform.scale(image_originale, (w, h))
        _cache_images_zoomees[cle] = img
    return img


def vider_cache_zoom():
    """À appeler quand le zoom change beaucoup pour libérer la mémoire."""
    _cache_tuiles_zoomees.clear()
    _cache_tuiles_dimmees.clear()
    _cache_images_zoomees.clear()


def monde_vers_ecran(x_monde, y_monde, cam_x, cam_y, zoom):
    """Convertit des coordonnées-monde en coordonnées-écran."""
    return ((x_monde - cam_x) * zoom, (y_monde - cam_y) * zoom)


def ecran_vers_case(x_ecran, y_ecran, cam_x, cam_y, zoom, taille_tuile):
    """Convertit une position écran en coordonnée-case (tx, ty). Peut sortir des bornes."""
    if zoom <= 0:
        return (0, 0)
    tx = int((x_ecran / zoom + cam_x) // taille_tuile)
    ty = int((y_ecran / zoom + cam_y) // taille_tuile)
    return (tx, ty)


def dessiner_image_layers(surface, image_layers, cam_x, cam_y, zoom, viewport_rect):
    """Dessine les image layers (PNG parallax) en respectant la caméra et le zoom."""
    surface.set_clip(viewport_rect)
    for il in image_layers:
        img = il['surface']
        x = (il['offset_x'] - cam_x) * zoom + viewport_rect.x
        y = (il['offset_y'] - cam_y) * zoom + viewport_rect.y
        if zoom != 1.0:
            img = _image_zoomee(img, zoom)
        surface.blit(img, (x, y))
    surface.set_clip(None)


def dessiner_tile_layers(surface, layers, cache_tuiles, cam_x, cam_y, zoom,
                         taille_tuile, largeur_map, hauteur_map, viewport_rect,
                         layer_actif=None):
    """Dessine toutes les couches de tuiles avec culling. La couche active est
    rendue normalement ; les autres en semi-transparent pour mettre en avant
    celle qu'on édite."""
    surface.set_clip(viewport_rect)

    taille_zoomee = max(1, int(round(taille_tuile * zoom)))

    # Culling : ne dessiner que les cases visibles dans le viewport
    case_x_min = max(0, int(cam_x // taille_tuile))
    case_y_min = max(0, int(cam_y // taille_tuile))
    case_x_max = min(largeur_map, int((cam_x + viewport_rect.width / zoom) // taille_tuile) + 1)
    case_y_max = min(hauteur_map, int((cam_y + viewport_rect.height / zoom) // taille_tuile) + 1)

    for index_layer, layer in enumerate(layers):
        gids = layer['gids']
        couche_active = (layer_actif is None or index_layer == layer_actif)
        for ty in range(case_y_min, case_y_max):
            ligne = gids[ty]
            for tx in range(case_x_min, case_x_max):
                gid = ligne[tx]
                if gid <= 0:
                    continue
                surf = cache_tuiles.get(gid)
                if surf is None:
                    continue
                if couche_active:
                    surf_z = _surface_zoomee(surf, zoom, taille_tuile)
                else:
                    surf_z = _surface_zoomee_dimmee(surf, zoom, taille_tuile)
                px = (tx * taille_tuile - cam_x) * zoom + viewport_rect.x
                py = (ty * taille_tuile - cam_y) * zoom + viewport_rect.y
                surface.blit(surf_z, (px, py))

    surface.set_clip(None)


def dessiner_grille(surface, cam_x, cam_y, zoom, taille_tuile,
                    largeur_map, hauteur_map, viewport_rect):
    """Dessine la grille des cases (lignes fines) sur le viewport."""
    if zoom < 0.4:
        return  # grille illisible quand on dézoome trop

    surface.set_clip(viewport_rect)
    couleur = (60, 70, 95)

    # Calcul des bornes visibles
    x_min = max(0, int(cam_x // taille_tuile))
    y_min = max(0, int(cam_y // taille_tuile))
    x_max = min(largeur_map, int((cam_x + viewport_rect.width / zoom) // taille_tuile) + 1)
    y_max = min(hauteur_map, int((cam_y + viewport_rect.height / zoom) // taille_tuile) + 1)

    # Lignes verticales
    for tx in range(x_min, x_max + 1):
        x = (tx * taille_tuile - cam_x) * zoom + viewport_rect.x
        if viewport_rect.left <= x <= viewport_rect.right:
            pygame.draw.line(
                surface, couleur,
                (x, max(viewport_rect.top, (y_min * taille_tuile - cam_y) * zoom + viewport_rect.y)),
                (x, min(viewport_rect.bottom, (y_max * taille_tuile - cam_y) * zoom + viewport_rect.y)),
                1
            )
    # Lignes horizontales
    for ty in range(y_min, y_max + 1):
        y = (ty * taille_tuile - cam_y) * zoom + viewport_rect.y
        if viewport_rect.top <= y <= viewport_rect.bottom:
            pygame.draw.line(
                surface, couleur,
                (max(viewport_rect.left, (x_min * taille_tuile - cam_x) * zoom + viewport_rect.x), y),
                (min(viewport_rect.right, (x_max * taille_tuile - cam_x) * zoom + viewport_rect.x), y),
                1
            )

    surface.set_clip(None)


def dessiner_surbrillance_couche(surface, layer, cam_x, cam_y, zoom,
                                 taille_tuile, largeur_map, hauteur_map,
                                 viewport_rect, couleur=(60, 140, 255, 130)):
    """Recouvre les cases non-vides de la couche d'un voile bleu translucide.
    Utilisé pour mettre en évidence l'étendue de la couche en cours d'édition."""
    surface.set_clip(viewport_rect)
    taille_zoomee = max(1, int(round(taille_tuile * zoom)))

    case_x_min = max(0, int(cam_x // taille_tuile))
    case_y_min = max(0, int(cam_y // taille_tuile))
    case_x_max = min(largeur_map, int((cam_x + viewport_rect.width / zoom) // taille_tuile) + 1)
    case_y_max = min(hauteur_map, int((cam_y + viewport_rect.height / zoom) // taille_tuile) + 1)

    overlay = pygame.Surface((taille_zoomee, taille_zoomee), pygame.SRCALPHA)
    overlay.fill(couleur)

    gids = layer['gids']
    for ty in range(case_y_min, case_y_max):
        ligne = gids[ty]
        for tx in range(case_x_min, case_x_max):
            if ligne[tx] <= 0:
                continue
            px = (tx * taille_tuile - cam_x) * zoom + viewport_rect.x
            py = (ty * taille_tuile - cam_y) * zoom + viewport_rect.y
            surface.blit(overlay, (px, py))

    surface.set_clip(None)


def dessiner_curseur_case(surface, case_x, case_y, cam_x, cam_y, zoom,
                          taille_tuile, largeur_map, hauteur_map, viewport_rect,
                          gid_apercu_surface=None):
    """Dessine le contour de la case sous la souris + un aperçu translucide
    de la tuile sélectionnée si gid_apercu_surface est fourni."""
    if not (0 <= case_x < largeur_map and 0 <= case_y < hauteur_map):
        return

    surface.set_clip(viewport_rect)
    taille_zoomee = max(1, int(round(taille_tuile * zoom)))
    px = (case_x * taille_tuile - cam_x) * zoom + viewport_rect.x
    py = (case_y * taille_tuile - cam_y) * zoom + viewport_rect.y

    # Aperçu translucide
    if gid_apercu_surface is not None:
        apercu = _surface_zoomee(gid_apercu_surface, zoom, taille_tuile).copy()
        apercu.set_alpha(140)
        surface.blit(apercu, (px, py))

    # Cadre cyan néon
    pygame.draw.rect(
        surface, COULEUR_CYAN,
        pygame.Rect(int(px), int(py), taille_zoomee, taille_zoomee),
        2
    )
    surface.set_clip(None)
