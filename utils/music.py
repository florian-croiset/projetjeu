# music.py
# Singleton module - background music and sound effects management.
# Usage:
# import music
# music.init(settings)           # once at start-up
# music.start()                  # starts the background music
# music.play_sfx('jump')         # plays a short sound
# music.torch_loop_start()       # torch flame loop
# music.torch_loop_stop()        # stops the flame loop
#
# Supported SFX formats: .mp3, .ogg, .wav (automatic detection)
# Expected SFX folder: assets/sounds/

import pygame
import os
import sys

# ======================================================================
# INTERNAL STATE (private)
# ======================================================================

_music_ok      = False
_music_played   = False
_music_activated = True
_sfx_active      = True
_volume_sfx      = 0.8
_volume_music  = 0.5

# SFX cache: { 'jump': pygame.mixer.Sound, ... }
_sounds: dict = {}

# Rotation index for the player attack sounds
_slash_player_idx = 0

# Channel dedicated to the flame loop (torch)
_channel_torch: pygame.mixer.Channel = None

# Base names of the SFX (without extension - detected automatically)
_LIST_SFX = {
    'jump':           'jump', # DONE
    'double_jump':    'double_jump', # DONE
    'dash':           'dash',
    'attack':        'Slash1',
    'slash2':         'Slash2',
    'slash3':         'Slash3',
    'door':          'door_audio',
    'slash_boss':     'SlashBoss1',
    'damage':          'damage', # DONE
    'dead':           'dead', # DONE
    'enemy_death':    'enemy_death', # DONE
    'enemy_damage':   'enemy_damage',
    'free_soul':      'free_soul',
    'lost_soul':     'lost_soul',
    'echo':           'echo',
    'echo_dir':       'echo_dir',
    'key_item':            'key_item',
    'torch_loop':       'torch_loop', # DONE
    'checkpoint':          'checkpoint',
    'gate_opening':  'gate_opening',
    'boss_gate_open': 'boss_gate_open',
    'boss_gate_break': 'boss_gate_break',
    'explosion':          'explosion',
}

_EXTENSIONS = ['.mp3', '.ogg', '.wav']

# Per-sound custom volume (0.0 -> 1.0) - if missing, _volume_sfx is used
_VOLUMES_SFX = {
    'jump':        0.2,   # too loud by default -> lowered
    'double_jump':        0.4,
}

def _get_base() -> str:
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ======================================================================
# INITIALISATION
# ======================================================================

def init(settings: dict):
    """Initialise the mixer and load the music + SFX.
    Call AFTER pygame.init() and AFTER load_settings().
    """
    global _music_ok, _music_played, _sfx_active, _volume_sfx
    global _volume_music, _music_activated, _channel_torch

    sounds_params      = settings.get('sounds', {})
    _sfx_active      = sounds_params.get('enable_sfx', True)
    _volume_sfx      = float(sounds_params.get('volume_sfx', 0.8))
    _volume_music  = float(sounds_params.get('volume_music', 0.5))
    _music_activated = settings.get('video', {}).get('music', True)

    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        # Reserve at least 8 channels (1 will be dedicated to the torch)
        pygame.mixer.set_num_channels(8)
        _channel_torch = pygame.mixer.Channel(7)  # channel 7 = torch
    except Exception as e:
        print(f'[MUSIC] cannot initialise the mixer: {e}')
        return

    _load_music()
    _load_sfx()


def _load_music():
    global _music_ok, _music_played
    try:
        path = os.path.join(_get_base(), 'assets', 'music.mp3')
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(_volume_music)
        _music_ok    = True
        _music_played = False
        print(f'[MUSIC] music loaded: {path}')
    except Exception as e:
        print(f'[MUSIC] Impossible de charger musique.mp3 : {e}')
        _music_ok = False


def _load_sfx():
    global _sounds
    base_sounds = os.path.join(_get_base(), 'assets', 'sounds')
    for name, base in _LIST_SFX.items():
        charge = False
        for ext in _EXTENSIONS:
            path = os.path.join(base_sounds, base + ext)
            if not os.path.exists(path):
                continue
            try:
                sound = pygame.mixer.Sound(path)
                sound.set_volume(_VOLUMES_SFX.get(name, _volume_sfx))
                _sounds[name] = sound
                charge = True
                break
            except Exception as e:
                print(f'[MUSIC] error loading {path}: {e}')
        if not charge:
            _sounds[name] = None


# ======================================================================
# BACKGROUND MUSIC
# ======================================================================

# ======================================================================
# BACKGROUND MUSIC
# ======================================================================

def start():
    """Start the music if enabled in the settings - called when entering the game."""
    global _music_played
    if _music_ok and _music_activated:
        if not _music_played:
            pygame.mixer.music.play(-1)
            _music_played = True
        else:
            pygame.mixer.music.unpause()


def pause():
    """Temporarily pause the game mix."""
    if _music_ok and _music_played:
        pygame.mixer.music.pause()
    if _channel_torch:
        _channel_torch.pause()


def stop():
    """Completely stop the music (back to the menu, end of the game)."""
    global _music_played
    if _music_ok:
        pygame.mixer.music.stop()
        _music_played = False
    if _channel_torch:
        _channel_torch.stop()


def resume():
    """Resume the game mix after a temporary pause."""
    if _music_ok and _music_played and _music_activated:
        pygame.mixer.music.unpause()
    if _channel_torch and _sfx_active:
        _channel_torch.unpause()


def toggle(activate: bool):
    """Applied only when clicking 'Apply' in the settings."""
    global _music_played, _music_activated
    _music_activated = activate
    if not _music_ok:
        return
    if activate:
        # Only restart if we are in game (music already initialised)
        if _music_played:
            pygame.mixer.music.unpause()
        # If it was not played yet, start() will do it when entering the game
    else:
        pygame.mixer.music.pause()
        # DO NOT set _music_played = False - keep track of the fact
        # that it was started so that it can be resumed


# ======================================================================
# TORCH - flame loop + 2D spatial audio
# ======================================================================

# Maximum distance beyond which the torch is inaudible (world pixels)
TORCH_DISTANCE_MAX = 1000

# Current volume of the torch channel (for progressive smoothing)
_volume_torch_current = 0.0


def torch_loop_start():
    """Start the flame loop at volume 0 (the volume rises through torch_update_volume)."""
    global _volume_torch_current
    if not _sfx_active:
        return
    sound = _sounds.get('torch_loop')
    if sound and _channel_torch:
        _channel_torch.set_volume(0.0)
        _channel_torch.play(sound, loops=-1)
        _volume_torch_current = 0.0


def torch_loop_stop():
    """Immediately stop the flame loop."""
    global _volume_torch_current
    if _channel_torch:
        _channel_torch.stop()
    _volume_torch_current = 0.0


def torch_update_volume(dist_pixels: float):
    """Called every frame by the client with the player <-> torch distance.
    Computes the target volume and smooths the transition progressively.

    dist_pixels: euclidean distance in pixels (world coordinates, before zoom).
    """
    global _volume_torch_current
    if not _channel_torch or not _sfx_active:
        return

    # Target volume: 1.0 at distance 0, 0.0 at the maximum distance
    # Smooth curve with clamp
    ratio = max(0.0, 1.0 - dist_pixels / TORCH_DISTANCE_MAX)
    volume_target = ratio ** 1.5 * _volume_sfx  # slightly convex curve

    # Smoothing: interpolate towards the target (~5% per frame at 60 fps)
    speed = 0.05
    _volume_torch_current += (volume_target - _volume_torch_current) * speed
    _volume_torch_current = max(0.0, min(1.0, _volume_torch_current))

    _channel_torch.set_volume(_volume_torch_current)


# ======================================================================
# GENERIC SFX
# ======================================================================

def play_sfx(name: str):
    """Play a short sound by name. Silent if SFX are disabled or the sound is missing."""
    if not _sfx_active:
        return
    sound = _sounds.get(name)
    if sound is not None:
        sound.play()


def play_sfx_slash_player():
    """Play a player attack sound in rotation: Slash1 -> Slash2 -> Slash3 -> ..."""
    global _slash_player_idx
    if not _sfx_active:
        return
    names = ['attack', 'slash2', 'slash3']
    name = names[_slash_player_idx % 3]
    _slash_player_idx += 1
    sound = _sounds.get(name)
    if sound is not None:
        sound.play()


def set_volume_sfx(volume: float):
    global _volume_sfx
    _volume_sfx = max(0.0, min(1.0, volume))
    for sound in _sounds.values():
        if sound is not None:
            sound.set_volume(_volume_sfx)
    if _channel_torch:
        _channel_torch.set_volume(_volume_sfx)


def set_volume_music(volume: float):
    global _volume_music
    _volume_music = max(0.0, min(1.0, volume))
    if _music_ok:
        pygame.mixer.music.set_volume(_volume_music)


def activate_sfx(active: bool):
    global _sfx_active
    _sfx_active = active
    # If the SFX are disabled, also cut the torch loop
    if not active and _channel_torch:
        _channel_torch.stop()
