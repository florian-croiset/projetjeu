# tmx_io.py
# Chargement et sauvegarde des fichiers TMX (format Tiled) pour l'éditeur de niveaux.
# Conserve l'arbre ElementTree complet pour préserver les éléments non édités
# (objectgroup, imagelayer, properties) lors de la réécriture.

import os
import xml.etree.ElementTree as ET
import pygame


def charger_tmx(chemin):
    """Charge un fichier TMX et retourne un dict de données prêt à éditer.

    Le dict retourné contient :
      - chemin            : chemin absolu du fichier source
      - tree              : ElementTree gardé pour la sauvegarde
      - largeur, hauteur  : dimensions de la map (en tuiles)
      - layers            : liste de couches de tuiles éditables
                            chaque entrée = {'nom', 'element' (data XML), 'gids' (2D list)}
      - tileset           : pygame.Surface de l'image du tileset
      - tileset_firstgid  : gid de base
      - tileset_taille    : taille d'une tuile (px)
      - tileset_spacing   : espacement entre tuiles dans l'image
      - tileset_margin    : marge autour des tuiles dans l'image
      - tileset_colonnes  : nombre de colonnes de l'atlas
      - tileset_nb_tuiles : nombre total de tuiles
      - image_layers      : liste des PNG parallax {'surface', 'offset_x', 'offset_y'}
    """
    chemin = os.path.abspath(chemin)
    base = os.path.dirname(chemin)

    tree = ET.parse(chemin)
    root = tree.getroot()

    largeur = int(root.attrib['width'])
    hauteur = int(root.attrib['height'])

    # ------ Couches de tuiles (Wall.1, Sol.1, ...) ------
    layers = []
    for layer in root.findall('layer'):
        nom = layer.attrib.get('name', '')
        data_el = layer.find('data')
        if data_el is None or not data_el.text:
            continue
        valeurs = [int(v) for v in data_el.text.replace('\n', '').strip(',').split(',') if v.strip() != '']
        gids = []
        for y in range(hauteur):
            gids.append(valeurs[y * largeur:(y + 1) * largeur])
        layers.append({'nom': nom, 'element': data_el, 'gids': gids})

    # ------ Tileset (un seul attendu pour l'instant) ------
    ts_el = root.find('tileset')
    if ts_el is None:
        raise ValueError(f"Aucun tileset trouvé dans {chemin}")

    tileset_firstgid = int(ts_el.attrib.get('firstgid', 1))
    tsx_src = ts_el.attrib.get('source', '')
    if tsx_src:
        tsx_path = os.path.join(base, tsx_src)
        tsx_root = ET.parse(tsx_path).getroot()
        tileset_taille  = int(tsx_root.attrib.get('tilewidth', 32))
        tileset_spacing = int(tsx_root.attrib.get('spacing', 0))
        tileset_margin  = int(tsx_root.attrib.get('margin', 0))
        tilecount       = int(tsx_root.attrib.get('tilecount', 0))
        img_el = tsx_root.find('image')
        img_src = img_el.attrib.get('source', 'tileset.png')
        img_w = int(img_el.attrib.get('width', 0))
        if tileset_taille + tileset_spacing > 0:
            colonnes = (img_w - 2 * tileset_margin + tileset_spacing) // (tileset_taille + tileset_spacing)
        else:
            colonnes = int(tsx_root.attrib.get('columns', 1))
        chemin_image = os.path.join(os.path.dirname(tsx_path), img_src)
    else:
        tileset_taille  = int(ts_el.attrib.get('tilewidth', 32))
        tileset_spacing = int(ts_el.attrib.get('spacing', 0))
        tileset_margin  = int(ts_el.attrib.get('margin', 0))
        tilecount       = int(ts_el.attrib.get('tilecount', 0))
        colonnes        = int(ts_el.attrib.get('columns', 1))
        img_el = ts_el.find('image')
        img_src = img_el.attrib.get('source', 'tileset.png') if img_el is not None else 'tileset.png'
        chemin_image = os.path.join(base, img_src)

    tileset_surf = pygame.image.load(chemin_image).convert_alpha()

    # ------ Image layers (PNG parallax, lecture seule) ------
    image_layers = []
    for il in root.findall('imagelayer'):
        src = il.find('image')
        if src is None:
            continue
        chemin_img = os.path.join(base, src.attrib['source'])
        offset_x = float(il.attrib.get('offsetx', 0))
        offset_y = float(il.attrib.get('offsety', 0))
        try:
            img = pygame.image.load(chemin_img).convert_alpha()
            image_layers.append({'surface': img, 'offset_x': offset_x, 'offset_y': offset_y})
        except Exception as e:
            print(f"[EDITEUR] Image layer introuvable : {e}")

    return {
        'chemin': chemin,
        'tree': tree,
        'largeur': largeur,
        'hauteur': hauteur,
        'layers': layers,
        'tileset': tileset_surf,
        'tileset_firstgid': tileset_firstgid,
        'tileset_taille': tileset_taille,
        'tileset_spacing': tileset_spacing,
        'tileset_margin': tileset_margin,
        'tileset_colonnes': max(1, colonnes),
        'tileset_nb_tuiles': tilecount,
        'image_layers': image_layers,
    }


def sauvegarder_tmx(donnees):
    """Réécrit le fichier TMX avec les couches éditées.

    Les autres éléments (objectgroup, imagelayer, properties, tilesets) sont
    préservés tels quels via l'arbre ElementTree initial.
    Le format CSV utilisé respecte la convention Tiled (une rangée par ligne).
    """
    largeur = donnees['largeur']
    hauteur = donnees['hauteur']

    for layer in donnees['layers']:
        data_el = layer['element']
        # Encodage CSV : "v,v,...,v,\n" pour chaque rangée. Le dernier '\n' final aussi.
        rangees = []
        for y in range(hauteur):
            rangee = ','.join(str(g) for g in layer['gids'][y])
            rangees.append(rangee)
        # Tiled produit typiquement : un saut de ligne avant la première rangée
        # et après la dernière, avec une virgule séparant les rangées.
        data_el.text = '\n' + ',\n'.join(rangees) + '\n'

    donnees['tree'].write(donnees['chemin'], encoding='UTF-8', xml_declaration=True)


# ----------------------------------------------------------------------
# Cache de subsurfaces du tileset — recopie de core/carte.py:519-539.
# ----------------------------------------------------------------------
class CacheTuiles:
    """Cache les subsurfaces extraites de l'atlas pour éviter les re-découpes."""

    def __init__(self, donnees):
        self.donnees = donnees
        self._cache = {}

    def get(self, gid):
        """Retourne la pygame.Surface 32x32 correspondant au gid, ou None si vide."""
        if gid <= 0 or self.donnees['tileset'] is None:
            return None
        if gid in self._cache:
            return self._cache[gid]
        d = self.donnees
        idx = gid - d['tileset_firstgid']
        if idx < 0:
            self._cache[gid] = None
            return None
        col = idx % d['tileset_colonnes']
        row = idx // d['tileset_colonnes']
        x = d['tileset_margin'] + col * (d['tileset_taille'] + d['tileset_spacing'])
        y = d['tileset_margin'] + row * (d['tileset_taille'] + d['tileset_spacing'])
        ts_w, ts_h = d['tileset'].get_size()
        if x + d['tileset_taille'] > ts_w or y + d['tileset_taille'] > ts_h:
            self._cache[gid] = None
            return None
        surf = d['tileset'].subsurface(
            pygame.Rect(x, y, d['tileset_taille'], d['tileset_taille'])
        )
        self._cache[gid] = surf
        return surf
