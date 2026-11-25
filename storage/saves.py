"""Save slots (``slot_1.json`` ... ``slot_N.json``).

Format (version 2)::

    {
      "version": 2,
      "id_last_checkpoint": "42_22",
      "vis_map": {"w": 100, "h": 70, "bits": "<base64 of a bit-packed row-major grid>"},
      "items": [],
      "money": 0,
      "upgrades": {"double_jump": false, "dash": false, "echo_dir": false}
    }

Older files (French keys, ``vis_map`` as a list of lists of booleans) are still
readable: :func:`load_game` migrates them on the fly.

Writes are atomic (temporary file + ``os.replace``), so a crash in the middle of
a save can never leave a truncated slot behind.
"""

import base64
import json
import os
import sys
import tempfile

from settings import NUM_SAVE_SLOTS
from storage import checkpoints
from utils import i18n

SAVE_VERSION = 2

# Keys of the previous (French) save format -> current keys
_LEGACY_KEYS = {
    'id_dernier_checkpoint': 'id_last_checkpoint',
    'argent': 'money',
    'ameliorations': 'upgrades',
}
_LEGACY_UPGRADES = {'double_saut': 'double_jump'}


def get_folder_save():
    """Persistent folder for the save files (created if missing)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller build: per-user data folder
        if sys.platform == 'win32':
            base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        elif sys.platform == 'darwin':
            base = os.path.expanduser('~/Library/Application Support')
        else:
            base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        folder = os.path.join(base, 'Echo')
    else:
        folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(folder, exist_ok=True)
    return folder


def get_path_absolute_slot(id_slot):
    return os.path.join(get_folder_save(), f"slot_{id_slot + 1}.json")


# ---------------------------------------------------------------------------
#  Visibility map (de)serialisation
# ---------------------------------------------------------------------------

def encode_vis_map(grid):
    """``list[list[bool]]`` -> compact JSON-friendly dict."""
    height = len(grid)
    width = len(grid[0]) if height else 0
    bits = bytearray((width * height + 7) // 8)
    i = 0
    for row in grid:
        for visible in row:
            if visible:
                bits[i >> 3] |= 1 << (i & 7)
            i += 1
    return {'w': width, 'h': height, 'bits': base64.b64encode(bytes(bits)).decode('ascii')}


def decode_vis_map(data, width, height):
    """Inverse of :func:`encode_vis_map`; also accepts the legacy list-of-lists.

    Returns ``None`` when the data is missing or does not match the level size."""
    if not data:
        return None
    if isinstance(data, list):                       # legacy format
        if len(data) == height and all(len(r) == width for r in data):
            return [[bool(v) for v in row] for row in data]
        return None
    try:
        if data['w'] != width or data['h'] != height:
            return None
        bits = base64.b64decode(data['bits'])
        if len(bits) < (width * height + 7) // 8:
            return None
        return [[bool(bits[(y * width + x) >> 3] & (1 << ((y * width + x) & 7)))
                 for x in range(width)] for y in range(height)]
    except (KeyError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
#  Load / save
# ---------------------------------------------------------------------------

def create_save_blank():
    """Data of a brand new game."""
    start_id, _ = checkpoints.get_start_point()
    return {
        'version': SAVE_VERSION,
        'id_last_checkpoint': start_id,
        'vis_map': None,
        'items': [],
        'money': 0,
        'upgrades': {'double_jump': False, 'dash': False, 'echo_dir': False},
    }


def _migrate(data):
    """Bring a save of any previous version to the current layout."""
    for old, new in _LEGACY_KEYS.items():
        if old in data and new not in data:
            data[new] = data.pop(old)
    upgrades = data.setdefault('upgrades', {})
    for old, new in _LEGACY_UPGRADES.items():
        if old in upgrades:
            upgrades[new] = upgrades.pop(old)
    for name in ('double_jump', 'dash', 'echo_dir'):
        upgrades.setdefault(name, False)
    data.setdefault('id_last_checkpoint', checkpoints.get_start_point()[0])
    data.setdefault('money', 0)
    data.setdefault('items', [])
    data.setdefault('vis_map', None)
    data['version'] = SAVE_VERSION
    return data


def save_game(id_slot, data):
    """Atomically write ``data`` to its slot file."""
    path = get_path_absolute_slot(id_slot)
    folder = os.path.dirname(path)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=folder, prefix=".slot_", suffix=".tmp")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))
        os.replace(tmp_path, path)
        print(f"[SAVE] game saved to {path}")
    except OSError as exc:
        print(f"[SAVE] cannot write {path}: {exc}")


def load_game(id_slot):
    """Load a slot. Returns ``None`` if it is empty or corrupted."""
    path = get_path_absolute_slot(id_slot)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[SAVE] cannot read {path}: {exc}")
        return None
    if not isinstance(data, dict):
        return None
    return _migrate(data)


def get_info_slots():
    """One dict per slot for the load/new-game menus: ``name``, ``description``, ``is_empty``."""
    infos = []
    for i in range(NUM_SAVE_SLOTS):
        data = load_game(i)
        name = f"Slot {i + 1}"
        if data:
            place = checkpoints.get_name_per_id(data['id_last_checkpoint'])
            infos.append({'name': name, 'is_empty': False,
                          'description': i18n.get_text("slot_checkpoint").format(name=place)})
        else:
            infos.append({'name': name, 'is_empty': True,
                          'description': i18n.get_text("slot_empty")})
    return infos
