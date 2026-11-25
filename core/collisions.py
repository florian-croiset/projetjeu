"""Collision helpers shared by the server simulation and client-side prediction."""

from settings import TILE_SIZE


def collision_rects_for(game_map, doors, rect):
    """Solid rects around ``rect``: map walls plus closed doors.

    The server and the client prediction must resolve collisions from exactly
    the same set of rects, so both call this function."""
    rects = game_map.get_nearby_rects(rect)
    margin = TILE_SIZE * 2
    for door in doors:
        if door.is_open:
            continue
        door_rect = door.rect_collision
        if (door_rect.width > 0 and door_rect.height > 0
                and rect.colliderect(door_rect.inflate(margin * 2, margin * 2))):
            rects = rects + [door_rect]
    return rects
