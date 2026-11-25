"""Checkpoint ids and spawn points.

A checkpoint id is the tile coordinate of the checkpoint as ``"x_y"``.
"""

from settings import TILE_SIZE
from utils import i18n

START_CHECKPOINT = "42_22"

# Checkpoints that have a display name (text lives in utils/i18n.py: "checkpoint_<id>")
_NAMED_CHECKPOINTS = ("10_46", "1_12", "80_10")


def get_start_point():
    """``(id, (x, y))`` of the very first spawn point."""
    x_tile, y_tile = map(int, START_CHECKPOINT.split('_'))
    return START_CHECKPOINT, (x_tile * TILE_SIZE, y_tile * TILE_SIZE)


def get_coords_per_id(id_point):
    """Pixel coordinates of a checkpoint from its id (e.g. ``"3_21"``).

    Falls back to the start point if the id is malformed."""
    try:
        x_tile, y_tile = map(int, id_point.split('_'))
        return x_tile * TILE_SIZE, y_tile * TILE_SIZE
    except (AttributeError, ValueError):
        print(f"[CHECKPOINTS] invalid checkpoint id {id_point!r}, using the start point")
        return get_start_point()[1]


def get_name_per_id(id_point):
    """Human readable name of a checkpoint (used by the save-slot menus)."""
    if id_point in _NAMED_CHECKPOINTS:
        return i18n.get_text(f"checkpoint_{id_point}")
    return i18n.get_text("checkpoint_zone").format(id=id_point)
