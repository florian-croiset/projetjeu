"""Parité des textes FR / EN et résolution de toutes les clés utilisées dans le code."""

import re
from pathlib import Path

import pytest

from utils import i18n

ROOT = Path(__file__).resolve().parent.parent
IGNORED_DIRS = {".venv", "build", "dist", "tests", "__pycache__"}


@pytest.fixture(autouse=True)
def _restore_language():
    yield
    i18n.set_language("fr")


def test_fr_and_en_have_the_same_keys():
    assert set(i18n.FR) == set(i18n.EN)


def test_fr_and_en_values_have_the_same_shape():
    for key, fr in i18n.FR.items():
        en = i18n.EN[key]
        assert type(fr) is type(en), key
        if isinstance(fr, list):
            assert len(fr) == len(en), key
            for a, b in zip(fr, en):
                assert type(a) is type(b), key


def test_get_text_follows_language():
    i18n.set_language("en")
    assert i18n.get_text("menu_quit") == "Quit"
    i18n.set_language("fr")
    assert i18n.get_text("menu_quit") == "Quitter"


def test_every_key_used_in_code_exists():
    used = set()
    for path in ROOT.rglob("*.py"):
        if IGNORED_DIRS & set(path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'get_text\(\s*"([a-z0-9_]+)"', text))
    missing = used - set(i18n.FR)
    assert not missing, f"clés absentes de utils/i18n.py : {sorted(missing)}"
