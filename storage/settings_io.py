"""User settings file (language, video, controls, sound, profile).

Stored as JSON next to the game (or in the per-user data folder for a packaged
build). Missing keys are filled from the defaults on load, and the previous
French-keyed ``parametres.json`` is migrated automatically.
"""

import copy
import json
import os
import random
import sys
import tempfile

FILE_NAME = "user_settings.json"
LEGACY_FILE_NAME = "parametres.json"

_DEFAULT_NICKNAMES = ["Éclaireur", "Specter", "Nox", "Lumen", "Ombra", "Dusk", "Vex", "Ravn"]

# Previous French layout -> current layout (section names, then key names)
_LEGACY_SECTIONS = {'jouabilite': 'gameplay', 'controles': 'controls', 'sons': 'sounds',
                    'profil': 'profile'}
_LEGACY_KEYS = {
    'langue': 'language', 'sensibilite_souris': 'mouse_sensitivity',
    'plein_ecran': 'fullscreen', 'luminosite': 'brightness', 'musique': 'music',
    'gauche': 'left', 'droite': 'right', 'saut': 'jump', 'attaque': 'attack',
    'interagir': 'interact', 'torche': 'torch', 'activer_sfx': 'enable_sfx',
    'tutoriel_vu': 'tutorial_seen', 'pseudo': 'nickname',
}


def _folder():
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        elif sys.platform == 'darwin':
            base = os.path.expanduser('~/Library/Application Support')
        else:
            base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        folder = os.path.join(base, 'Echo')
        os.makedirs(folder, exist_ok=True)
        return folder
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_path_absolute_settings():
    return os.path.join(_folder(), FILE_NAME)


def create_default_settings():
    return {
        "gameplay": {"language": "fr", "mouse_sensitivity": 0.5},
        "video": {
            "fullscreen": True, "vsync": False, "music": True,
            "resolution": [1920, 1080], "brightness": 0.3, "display_index": 0,
        },
        "controls": {
            "left": "q", "right": "d", "jump": "space", "echo": "e", "attack": "k",
            "dash": "c", "echo_dir": "y", "interact": "f", "torch": "l", "journal": "i",
        },
        "sounds": {"volume_sfx": 0.8, "volume_music": 0.5, "enable_sfx": True},
        "meta": {"tutorial_seen": False},
        "profile": {"nickname": random.choice(_DEFAULT_NICKNAMES), "skin": 0},
    }


def _migrate_legacy(data):
    """Translate a French-keyed settings dict to the current layout."""
    out = {}
    for section, content in data.items():
        section = _LEGACY_SECTIONS.get(section, section)
        if isinstance(content, dict):
            content = {_LEGACY_KEYS.get(k, k): v for k, v in content.items()}
        out[section] = content
    return out


def _merge_defaults(settings, defaults):
    """Fill missing sections/keys (and wrong-typed values) from ``defaults``.

    Returns True if ``settings`` was modified."""
    changed = False
    for section, default_section in defaults.items():
        current = settings.get(section)
        if not isinstance(current, dict):
            settings[section] = copy.deepcopy(default_section)
            changed = True
            continue
        for key, default_value in default_section.items():
            if key not in current or type(current[key]) is not type(default_value) \
                    and not (isinstance(default_value, float) and isinstance(current[key], int)):
                current[key] = copy.deepcopy(default_value)
                changed = True
    return changed


def load_settings():
    path = get_path_absolute_settings()
    legacy_path = os.path.join(os.path.dirname(path), LEGACY_FILE_NAME)
    source = path if os.path.exists(path) else (legacy_path if os.path.exists(legacy_path) else None)
    defaults = create_default_settings()
    if source is None:
        save_settings(defaults)
        return defaults
    try:
        with open(source, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        if not isinstance(settings, dict):
            raise ValueError("settings root must be an object")
    except (OSError, ValueError) as exc:
        print(f"[SETTINGS] cannot read {source} ({exc}); using defaults")
        save_settings(defaults)
        return defaults
    if source == legacy_path:
        settings = _migrate_legacy(settings)
    if _merge_defaults(settings, defaults) or source == legacy_path:
        save_settings(settings)
    return settings


def save_settings(settings):
    path = get_path_absolute_settings()
    try:
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".settings_", suffix=".tmp")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
    except OSError as exc:
        print(f"[SETTINGS] cannot write {path}: {exc}")
