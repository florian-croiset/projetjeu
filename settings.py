# parametres.py
# Global game constants and settings.
# Colors follow the Echo art direction (Team Nightberry).

# -- Window --
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WINDOW_TITLE = "Écho - Team Nightberry"
FPS = 60


# -- Saves --
NUM_SAVE_SLOTS = 3

# -- Map (tilemap) --
TILE_SIZE = 32  # Each tile is 32x32 pixels

# =====================================================================
# PALETTE DE COULEURS — CHARTE GRAPHIQUE ECHO (Team Nightberry)
# =====================================================================
# Background & neutrals
COLOR_BLACK          = (0, 0, 0)
COLOR_WHITE         = (255, 255, 255)
COLOR_BACKGROUND          = (8, 8, 20)          # Noir-bleu profond
COLOR_BACKGROUND_ALT      = (12, 12, 28)        # Slightly lighter
COLOR_PANEL_BACKGROUND    = (14, 10, 35)        # UI panel background

# Neon cyan (Echo primary color)
COLOR_CYAN          = (0, 208, 198)       # #00d4ff - main neon
COLOR_CYAN_LIGHT    = (96, 244, 215)     # Survol / highlight
COLOR_CYAN_DARK   = (3, 119, 120)       # Bordure / ombre

# Violet (couleur secondaire Echo)
COLOR_VIOLET        = (123, 47, 255)      # #7b2fff  — accent violet
COLOR_VIOLET_LIGHT  = (160, 100, 255)     # Survol violet
COLOR_VIOLET_DARK = (60, 20, 120)       # Ombre violette

# Gameplay colors (kept)
COLOR_PLAYER        = (50, 150, 255)
COLOR_OTHER_PLAYER  = (255, 100, 50)
COLOR_ENEMY        = (200, 50, 50)
COLOR_WALL_VISIBLE   = (40, 40, 80)        # Walls in the Echo mood
COLOR_GUIDE         = (20, 20, 40)
COLOR_SAVE_POINT    = (0, 212, 255)       # Checkpoints en cyan Echo
COLOR_LOST_SOUL    = (160, 100, 255)     # Souls in Echo violet
COLOR_ATTACK       = (255, 255, 200)

# -- UI colors - Echo palette --
COLOR_TITLE         = (0, 208, 198)       # Titles in neon cyan
COLOR_TEXT         = (200, 220, 235)     # Light text, slightly bluish
COLOR_TEXT_DARK  = (120, 140, 160)     # Secondary / disabled text

# Normal buttons: dark background with cyan border
COLOR_BUTTON        = (14, 10, 35)        # Dark background (very dark violet)
COLOR_BUTTON_HOVER = (25, 15, 60)        # Hover: slightly lighter

# Input
COLOR_INPUT_BOX     = (10, 8, 25)
COLOR_INPUT_ACTIVE   = (0, 212, 255)

# Pause / overlay
COLOR_PAUSE_BACKGROUND    = (4, 4, 15, 200)     # Semi-transparent, very dark

# HUD
COLOR_HP            = (0, 212, 255)       # PV en cyan Echo
COLOR_HP_LOST      = (30, 20, 60)        # Lost HP in very dark violet

# =====================================================================

# -- Player --
PLAYER_SPEED = 5
JUMP_FORCE = 15
GRAVITY = 0.6
PLAYER_MAX_HP = 5
INVINCIBILITY_TIME_MS = 1000
STARTING_MONEY = 0

# -- Game feel: assisted jumps --
COYOTE_TIME_MS     = 100    # Window after leaving the ground during which a jump is still allowed
JUMP_BUFFER_MS     = 100    # Window before landing during which a jump press is remembered
JUMP_CUT_FACTOR = 0.5    # If Space is released while rising: vel_y *= this factor (variable jump height)

# -- Game feel: knockback on damage --
RECOIL_VX        = 4.0       # Horizontal velocity applied to the hit player
RECOIL_VY        = -5.0      # Small vertical hop on knockback
RECOIL_DURATION_MS  = 200       # Duration during which horizontal input is ignored


# -- Combat --
ATTACK_DURATION = 200
ATTACK_COOLDOWN = 800
ATTACK_RANGE = 40
PLAYER_DAMAGE = 1

# -- Tracker (AI that listens for echoes) --
TRACKER_HEARING_RADIUS = 400     # px: hearing radius (larger than ECHO_RANGE)
TORCH_ECHO_RANGE = 600
TRACKER_ALERT_DURATION   = 10000    # ms: how long a chase lasts before going back to patrol
TRACKER_CHASE_SPEED = 1.0     # px/tick en chasse
TRACKER_JUMP_FORCE     = 9       # initial jump velocity (about 2 tiles high)

# -- Enemy --
ENEMY_SPEED = 1.5
MONEY_PER_ENEMY = 10
ENEMY_RESPAWN_TIME_MS = 180000  # 3 minutes en ms

# -- Enemy sprites (max_hp -> asset prefix) --
ENEMY_SPRITE_BY_HP = {1: 'e1', 2: 'e2', 3: 'e3'}

# -- Enemy attack --
ENEMY_ATTACK_RANGE       = 48     # horizontal px to trigger an attack
ENEMY_ATTACK_RANGE_VERTICAL  = 64     # vertical px tolerance
ENEMY_ATTACK_COOLDOWN     = 1500   # ms between two attacks
ENEMY_ATTACK_DAMAGE       = 1

# Animation durations (computed from the Aseprite JSON files)
ENEMY_ATTACK_DURATION_E1    = 1575   # 9  × 175 ms
ENEMY_ATTACK_DURATION_E2    = 1650   # 11 × 150 ms
ENEMY_ATTACK_DURATION_E3_A1 = 2100   # 14 × 150 ms
ENEMY_ATTACK_DURATION_E3_A2 = 1800   # 12 × 150 ms

# Frame windows during which the attack hitbox is ACTIVE (0-based, inclusive)
HITBOX_FRAMES_E1     = (4, 6)    # out of 9 frames
HITBOX_FRAMES_E2     = (5, 7)    # out of 11
HITBOX_FRAMES_E3_A1  = (7, 10)   # out of 14
HITBOX_FRAMES_E3_A2  = (5, 8)    # out of 12

# -- Abilities --
DASH_DISTANCE = TILE_SIZE * 4
DASH_DURATION = 150
COOLDOWN_DASH = 600
MAX_AIR_DASHES = 1
DOUBLE_JUMP_FORCE = 10

# -- Echo (raycasting) --
ECHO_RANGE = 150
ECHO_RAY_COUNT = 360
COOLDOWN_ECHO = 2500            # 2.5 s between two echoes
ECHO_REVEAL_DURATION = 600         # Progressive reveal duration (ms)
ECHO_FADE_DURATION   = 120000      # Time (ms) before a revealed tile fades back to black
LEVER_COOP_WINDOW = 3000        # Window (ms) to hit both levers

# -- Directional echo --
ECHO_DIR_RANGE = ECHO_RANGE * 2   # 300 px (double range)
COOLDOWN_ECHO_DIR = 4000            # 4 s independent cooldown
ECHO_DIR_HALF_ANGLE = 25           # +-25 degrees around the facing direction

# -- Echo visual distortion (client only) --
ECHO_DISTORTION_ENABLED       = True   # False = disable the effect (performance or preference)
ECHO_DISTORTION_AMPLITUDE_PX = 5      # Maximum radial pixel displacement at the crest peak
ECHO_DISTORTION_THICKNESS_PX = 40     # Width of the distorted ring (pixels)

# -- Free souls --
FREE_SOUL_MONEY = 5
COLOR_FREE_SOUL = (0, 220, 180)  # Turquoise

# -- Loot souls (enemy drops) --
COLOR_LOOT_SOUL = (0, 200, 160)
LOOT_BURST_SPEED = 4.0           # Maximum initial scatter velocity
LOOT_BOUNCE_DAMPING = 0.2         # Bounce factor on walls/ground
LOOT_REST_THRESHOLD = 0.5             # Velocity below which the orb settles
LOOT_MAX_DISPERSION_TIME = 3000        # ms, forces rest after this delay
LOOT_LIFETIME = 30000         # ms, despawn delay once at rest


# -- Network --
TCP_PORT = 5555

# -- Relay (room-code connection) --
RELAY_HOST = ""         # Empty = relay disabled. E.g. "relay.example.com" or "1.2.3.4"
RELAY_PORT = 7777

# -- UDP layer (real-time netcode) --
USE_UDP = True                     # Master switch: set to False to force plain TCP.
UDP_PORT = 5556                    # Server UDP port (next to TCP 5555).
INTERP_DELAY_MS = 60              # Remote entities are rendered this many ms in the past (raised automatically when the connection is jittery)

# -- Camera --
CAMERA_ZOOM = 2.5

# All usual resolutions, smallest to largest
AVAILABLE_RESOLUTIONS = [
    (800, 600),    # SVGA
    (1024, 600),   # WSVGA
    (1280, 720),   # HD
    (1024, 768),   # XGA
    (1280, 768),   # WXGA
    (1366, 768),   # HD (laptop)
    (1280, 800),   # WXGA
    (1152, 864),   # XGA+
    (1536, 864),   # Chromebook
    (1440, 900),   # WXGA+
    (1600, 900),   # HD+
    (1280, 960),   # SXGA-
    (1280, 1024),  # SXGA
    (1600, 1024),  # —
    (1400, 1050),  # SXGA+
    (1680, 1050),  # WSXGA+
    (1920, 1080),  # Full HD
    (2048, 1080),  # 2K DCI
    (2560, 1080),  # Ultra-Wide FHD
    (1920, 1200),  # WUXGA
    (2560, 1440),  # 2K QHD
    (3440, 1440),  # Ultra-Wide QHD
    (2560, 1600),  # WQXGA
    (3840, 2160),  # 4K UHD
]

def get_compatible_resolutions(resolution_native):
    """Resolutions that fit within the screen's native resolution."""
    width_max, top_max = resolution_native
    return [r for r in AVAILABLE_RESOLUTIONS if r[0] <= width_max and r[1] <= top_max]

# -- Torche --
COLOR_TORCH = (255, 140, 30)
TORCH_LIGHT_RADIUS = 220
TORCH_ECHO_DISTANCE = 30
TORCH_INTERACTION_RANGE = 180   # px: maximum player-to-torch distance to toggle it

# -- Enemy visibility --
ENEMY_DETECTION_DISTANCE = 120  # pixels, an enemy is visible when the player is this close
ENEMY_ECHO_FLASH_DURATION = 1500   # ms, how long an enemy stays visible after an echo

# -- Player halo --
PLAYER_HALO_RADIUS    = 80   # Total halo radius in pixels
HALO_GRADIENT_WIDTH = 20   # Width of the gradient zone (= radius -> gradient over the whole radius)
HALO_LEVEL_COUNT      = 0    # 0 = exact pixel-by-pixel (numpy), integer > 0 = discrete layers

# -- Debug --
DEV_MODE = False  # Set to True to enable the FPS counter, debug overlay and unlock all abilities
MENU_HALOS = False  # Set to False to disable the animated menu halos
MENU_BACKGROUND = False  # Set to False for a plain black background
REVEAL_ALL = False
DARKNESS_ENABLED = True  # False = everything lit, no halo | True = darkness with a halo around the player

