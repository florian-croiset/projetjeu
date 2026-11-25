"""Save slots and user settings: formats, migration of the old French files, atomic writes."""
import json

import pytest

from storage import saves, settings_io


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(saves, "get_folder_save", lambda: str(tmp_path))
    monkeypatch.setattr(settings_io, "_folder", lambda: str(tmp_path))
    return tmp_path


LEGACY_SAVE = {
    "id_dernier_checkpoint": "32_12",
    "vis_map": [[False, True], [True, False]],
    "items": [],
    "argent": 42,
    "ameliorations": {"double_saut": True, "dash": False, "echo_dir": False},
}

LEGACY_SETTINGS = {
    "jouabilite": {"langue": "en", "sensibilite_souris": 0.5},
    "video": {"plein_ecran": False, "vsync": False, "musique": True,
              "resolution": [1280, 720], "luminosite": 0.6, "display_index": 0},
    "controles": {"gauche": "a", "droite": "e", "saut": "space", "echo": "z", "attaque": "k",
                  "dash": "c", "echo_dir": "y", "interagir": "f", "torche": "l", "journal": "i"},
    "sons": {"volume_sfx": 0.1, "volume_musique": 0.2, "activer_sfx": False},
    "meta": {"tutoriel_vu": True},
    "profil": {"pseudo": "Zed", "skin": 1},
}


def test_blank_save_round_trip(folder):
    data = saves.create_save_blank()
    saves.save_game(0, data)
    assert saves.load_game(0) == data
    assert saves.load_game(1) is None


def test_legacy_save_is_migrated(folder):
    (folder / "slot_1.json").write_text(json.dumps(LEGACY_SAVE), encoding="utf-8")
    data = saves.load_game(0)
    assert data["id_last_checkpoint"] == "32_12"
    assert data["money"] == 42
    assert data["upgrades"] == {"double_jump": True, "dash": False, "echo_dir": False}
    assert "argent" not in data and "ameliorations" not in data


def test_corrupted_save_is_ignored(folder):
    (folder / "slot_1.json").write_text("{not json", encoding="utf-8")
    assert saves.load_game(0) is None
    (folder / "slot_2.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert saves.load_game(1) is None


def test_vis_map_encoding_round_trip_and_legacy():
    grid = [[(x * y) % 3 == 0 for x in range(100)] for y in range(70)]
    encoded = saves.encode_vis_map(grid)
    assert len(json.dumps(encoded)) < 2500                 # was ~140 KB as a list of lists
    assert saves.decode_vis_map(encoded, 100, 70) == grid
    assert saves.decode_vis_map(encoded, 99, 70) is None   # level size mismatch
    assert saves.decode_vis_map(LEGACY_SAVE["vis_map"], 2, 2) == LEGACY_SAVE["vis_map"]
    assert saves.decode_vis_map(None, 2, 2) is None
    assert saves.decode_vis_map({"w": 2, "h": 2, "bits": "!!!"}, 2, 2) is None


def test_save_is_atomic_and_leaves_no_temp_files(folder):
    for i in range(5):
        saves.save_game(0, {"n": i})
    assert [p.name for p in folder.iterdir()] == ["slot_1.json"]


def test_slot_infos(folder):
    saves.save_game(1, saves.create_save_blank())
    infos = saves.get_info_slots()
    assert [i["is_empty"] for i in infos] == [True, False, True]


def test_settings_defaults_created_and_persisted(folder):
    s = settings_io.load_settings()
    assert s["gameplay"]["language"] == "fr"
    assert (folder / settings_io.FILE_NAME).exists()
    assert settings_io.load_settings() == s


def test_legacy_settings_are_migrated(folder):
    (folder / settings_io.LEGACY_FILE_NAME).write_text(json.dumps(LEGACY_SETTINGS), encoding="utf-8")
    s = settings_io.load_settings()
    assert s["gameplay"]["language"] == "en"
    assert s["controls"]["left"] == "a" and s["controls"]["torch"] == "l"
    assert s["video"]["fullscreen"] is False and s["video"]["brightness"] == 0.6
    assert s["sounds"]["enable_sfx"] is False
    assert s["meta"]["tutorial_seen"] is True
    assert s["profile"]["nickname"] == "Zed"


def test_missing_and_wrong_typed_settings_are_repaired(folder):
    (folder / settings_io.FILE_NAME).write_text(json.dumps({
        "gameplay": {"language": 12},                      # wrong type
        "video": "oops",                                   # wrong section type
    }), encoding="utf-8")
    s = settings_io.load_settings()
    assert s["gameplay"]["language"] == "fr"
    assert isinstance(s["video"], dict) and "fullscreen" in s["video"]
    assert "controls" in s
