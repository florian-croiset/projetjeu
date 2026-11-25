# tmx_io.py
# Loading and saving TMX files (Tiled format) for the level editor.
# Keeps the whole ElementTree to preserve the elements that are not edited
# (objectgroup, imagelayer, properties) when rewriting.

import os
import xml.etree.ElementTree as ET
import pygame


def load_tmx(path):
    """Load a TMX file and return a data dict ready to be edited.

    The returned dict contains:
    - path             : absolute path of the source file
    - tree             : ElementTree kept for saving
    - width, height    : map dimensions (in tiles)
    - layers           : list of editable tile layers
                         each entry = {'name', 'element' (XML data), 'gids' (2D list)}
    - tileset          : pygame.Surface of the tileset image
    - tileset_firstgid : base gid
    - tileset_size     : tile size (px)
    - tileset_spacing  : spacing between tiles in the image
    - tileset_margin   : margin around the tiles in the image
    - tileset_columns  : number of columns of the atlas
    - tileset_num_tiles: total number of tiles
    - image_layers     : list of parallax PNGs {'surface', 'offset_x', 'offset_y'}
    """
    path = os.path.abspath(path)
    base = os.path.dirname(path)

    tree = ET.parse(path)
    root = tree.getroot()

    width = int(root.attrib['width'])
    height = int(root.attrib['height'])

    # ------ Tile layers (Wall.1, Sol.1, ...) ------
    layers = []
    for layer in root.findall('layer'):
        name = layer.attrib.get('name', '')
        data_el = layer.find('data')
        if data_el is None or not data_el.text:
            continue
        # Tiled also supports base64 (with/without compression) and child XML;
        # save_tmx can only write CSV, so any other encoding is explicitly refused
        # rather than crashing on int() or silently emptying the
        # layer.
        encoding = data_el.attrib.get('encoding', 'xml')
        if encoding != 'csv':
            raise ValueError(
                f"Layer {name!r} uses encoding={encoding!r}, which is not supported. "
                f"Re-export it from Tiled as CSV (Edit > Preferences > Tile Layer Format)."
            )
        values = [int(v) for v in data_el.text.replace('\n', '').strip(',').split(',') if v.strip() != '']
        gids = []
        for y in range(height):
            gids.append(values[y * width:(y + 1) * width])
        layers.append({'name': name, 'element': data_el, 'gids': gids})

    # ------ Tileset (only one expected for now) ------
    ts_el = root.find('tileset')
    if ts_el is None:
        raise ValueError(f"No tileset found in {path}")

    tileset_firstgid = int(ts_el.attrib.get('firstgid', 1))
    tsx_src = ts_el.attrib.get('source', '')
    if tsx_src:
        tsx_path = os.path.join(base, tsx_src)
        tsx_root = ET.parse(tsx_path).getroot()
        tileset_size  = int(tsx_root.attrib.get('tilewidth', 32))
        tileset_spacing = int(tsx_root.attrib.get('spacing', 0))
        tileset_margin  = int(tsx_root.attrib.get('margin', 0))
        tilecount       = int(tsx_root.attrib.get('tilecount', 0))
        img_el = tsx_root.find('image')
        img_src = img_el.attrib.get('source', 'tileset.png')
        img_w = int(img_el.attrib.get('width', 0))
        if tileset_size + tileset_spacing > 0:
            columns = (img_w - 2 * tileset_margin + tileset_spacing) // (tileset_size + tileset_spacing)
        else:
            columns = int(tsx_root.attrib.get('columns', 1))
        path_image = os.path.join(os.path.dirname(tsx_path), img_src)
    else:
        tileset_size  = int(ts_el.attrib.get('tilewidth', 32))
        tileset_spacing = int(ts_el.attrib.get('spacing', 0))
        tileset_margin  = int(ts_el.attrib.get('margin', 0))
        tilecount       = int(ts_el.attrib.get('tilecount', 0))
        columns        = int(ts_el.attrib.get('columns', 1))
        img_el = ts_el.find('image')
        img_src = img_el.attrib.get('source', 'tileset.png') if img_el is not None else 'tileset.png'
        path_image = os.path.join(base, img_src)

    tileset_surf = pygame.image.load(path_image).convert_alpha()

    # ------ Image layers (parallax PNGs, read-only) ------
    image_layers = []
    for il in root.findall('imagelayer'):
        src = il.find('image')
        if src is None:
            continue
        path_img = os.path.join(base, src.attrib['source'])
        offset_x = float(il.attrib.get('offsetx', 0))
        offset_y = float(il.attrib.get('offsety', 0))
        try:
            img = pygame.image.load(path_img).convert_alpha()
            image_layers.append({'surface': img, 'offset_x': offset_x, 'offset_y': offset_y})
        except Exception as e:
            print(f"[EDITOR] image layer not found: {e}")

    return {
        'path': path,
        'tree': tree,
        'width': width,
        'height': height,
        'layers': layers,
        'tileset': tileset_surf,
        'tileset_firstgid': tileset_firstgid,
        'tileset_size': tileset_size,
        'tileset_spacing': tileset_spacing,
        'tileset_margin': tileset_margin,
        'tileset_columns': max(1, columns),
        'tileset_num_tiles': tilecount,
        'image_layers': image_layers,
    }


def save_tmx(data):
    """Rewrite the TMX file with the edited layers.

    The other elements (objectgroup, imagelayer, properties, tilesets) are
    preserved as-is through the initial ElementTree.
    The CSV format follows the Tiled convention (one row per line).
    """
    data['width']
    height = data['height']

    for layer in data['layers']:
        data_el = layer['element']
        # CSV encoding: "v,v,...,v,\n" for every row. The final '\n' as well.
        rows = []
        for y in range(height):
            row = ','.join(str(g) for g in layer['gids'][y])
            rows.append(row)
        # Tiled typically produces: a line break before the first row
        # and after the last one, with a comma separating the rows.
        data_el.text = '\n' + ',\n'.join(rows) + '\n'

    # Atomic write: a crash mid-write must not truncate the
    # canonical file. os.replace is atomic on POSIX and Win32 since Python 3.3.
    path_final = data['path']
    path_tmp = path_final + '.tmp'
    data['tree'].write(path_tmp, encoding='UTF-8', xml_declaration=True)
    os.replace(path_tmp, path_final)


# ----------------------------------------------------------------------
# Cache of the tileset subsurfaces - copy of core/game_map.py get_tile_surface.
# ----------------------------------------------------------------------
class CacheTiles:
    """Cache the subsurfaces extracted from the atlas to avoid cutting them again."""

    def __init__(self, data):
        self.data = data
        self._cache = {}

    def get(self, gid):
        """Return the 32x32 pygame.Surface matching the gid, or None if empty."""
        if gid <= 0 or self.data['tileset'] is None:
            return None
        if gid in self._cache:
            return self._cache[gid]
        d = self.data
        idx = gid - d['tileset_firstgid']
        if idx < 0:
            self._cache[gid] = None
            return None
        col = idx % d['tileset_columns']
        row = idx // d['tileset_columns']
        x = d['tileset_margin'] + col * (d['tileset_size'] + d['tileset_spacing'])
        y = d['tileset_margin'] + row * (d['tileset_size'] + d['tileset_spacing'])
        ts_w, ts_h = d['tileset'].get_size()
        if x + d['tileset_size'] > ts_w or y + d['tileset_size'] > ts_h:
            self._cache[gid] = None
            return None
        surf = d['tileset'].subsurface(
            pygame.Rect(x, y, d['tileset_size'], d['tileset_size'])
        )
        self._cache[gid] = surf
        return surf
