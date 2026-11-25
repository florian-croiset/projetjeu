"""Static level layout, shared by the server (World) and the client.

Everything that used to be hard-coded in several places (server setup,
client-side mirror of destroyed walls, torch position...) lives here once.
Coordinates are in pixels unless a name ends with ``_TILES``.
"""

from settings import TILE_SIZE

TILE = TILE_SIZE

TORCH_POS = (551, 1025)

# (x, y, capability)
ORBS = [
    (21 * TILE, 61 * TILE, 'double_jump'),
]

# (x, y)
DOORS = [
    (85 * TILE, 65 * TILE),            # main exit door
]

# Tile coordinates of the two co-op levers
LEVERS_TILES = [(30, 14), (94, 53)]

# (x, y, kind) - kind: lore_levier | shop_dash | lettre | shop_upgrades
SIGNS = [
    (81 * TILE, 39 * TILE, 'lore_lever'),
    (29 * TILE, 48 * TILE, 'shop_dash'),
    (2983, 1382, 'letter'),
    (33 * TILE, 31 * TILE, 'shop_upgrades'),
]
SIGNS_ALWAYS_UNLOCKED = ('letter', 'shop_upgrades')

# Walls that open when both levers are hit within the co-op window
SECRET_PASSAGE_TILES = [(68, 49), (69, 49), (70, 49), (68, 50), (69, 50), (70, 50)]

# Wall opened by paying souls (tile of the sign + cost + message)
PAID_WALL_SIGN_TILE = (85, 10)
PAID_WALL_COST = 25
PAID_WALL_MESSAGE = "25 ames pour acceder"
PAID_WALL_TILES = [(x, 11) for x in range(82, 91)]

# Wall broken with the boss key
KEY_WALL_TILES = [(93, 18), (93, 19), (93, 20)]

# Boss arena (x, y, w, h in pixels), boss spawn and where a dead player's soul
# is dropped when dying during the boss fight.
BOSS_ROOM_RECT = (72 * TILE, 13 * TILE, (93 - 72) * TILE, (20 - 13) * TILE)
BOSS_SPAWN = (87 * TILE, 19 * TILE)
BOSS_FIGHT_SOUL_POS = (2555, 294)

# Wall layer edited when a wall is destroyed (visual mirror on the client)
DESTRUCTIBLE_LAYER = 'Wall.1'
