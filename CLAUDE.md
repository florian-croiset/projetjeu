# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Écho** is a cooperative multiplayer 2D action-platformer in Python/Pygame where players perceive their environment exclusively through echolocation (raycasting). Metroidvania-style progression with unlockable abilities and a Dark Souls-inspired death mechanic. Student project (Cycle Préparatoire S1 & S2, team of 5).

## Commands

```bash
# Run the game
python3 main.py
make all

# Install dependencies
pip install -r requirements.txt

# Run the TCP relay server (for WAN play without port forwarding)
python3 -m reseau.relay_server [port]   # default port: 7777
```

No build step, no test suite — this is a pure Python/Pygame project.

## Architecture

The client-server architecture splits authority: **the server owns all game logic** (physics, AI, combat, collisions), and **the client owns rendering, input, and display**.

### Entry Point & Client

`main.py` → instantiates `Client` (`client.py`) → calls `lancer_application()`.

`Client` is composed of three mixins:
- **`BoucleJeuMixin`** (`boucle_jeu.py`): in-game loop — sends inputs to server via TCP, receives authoritative state, renders the world. Also handles connection setup, hosting (starts server thread + optional relay thread).
- **`MenusMixin`** (`ui/menus.py`): all menu screens (main, parameters, save slots, join via IP or room code)
- **`HudMixin`** (`ui/hud.py`): in-game HUD (health bar, boss indicator, death/respawn screen)

### Server

`reseau/serveur.py` — runs in a separate thread (started from `BoucleJeuMixin` when hosting). Handles:
- Player physics (gravity, AABB collisions, movement, dash, jump) at 60 Hz
- Enemy AI (patrol, void detection, respawn timers)
- Combat resolution (melee attacks, boss fights)
- Game objects: `Porte` (interactive doors), `OrbeCapacite` (ability orbs), `Cle` (keys), `AmePerdue`/`AmeLibre`/`AmeLoot` (soul/loot drops)
- Checkpoint detection and save triggers
- Broadcasting authoritative world state to all clients at `TICK_RATE_RESEAU` Hz (10 Hz)

### Network Module (`reseau/`)

| File | Role |
|------|------|
| `protocole.py` | Shared TCP helpers — `send_complet` / `recv_complet` (4-byte length prefix + pickle), IP detection (`obtenir_ip_locale`, `obtenir_ip_vpn` for Tailscale/Hamachi) |
| `serveur.py` | Authoritative game server (TCP, threaded per-client) |
| `relay_server.py` | Standalone TCP relay server for room-code-based WAN play without port forwarding |
| `relay_client.py` | Client-side helpers to create/join relay rooms |

### Network Protocol

**TCP** on port `5555` (configurable via `PORT_SERVEUR` in `parametres.py`).

**Wire format**: 4-byte big-endian length prefix + pickle-serialized Python object. Implemented in `protocole.py` (`send_complet` / `recv_complet`). Max payload: 10 MB safety limit.

**Client → Server**: input dicts (keys pressed, actions)
**Server → Client**: full authoritative game state (players, enemies, souls, boss, keys, doors, orbs, visibility maps)

### WAN Connectivity

Two connection modes available in the "Rejoindre" menu:

1. **Direct IP**: Enter the host's IP address. Requires port `5555/TCP` to be forwarded on the host's router (or both players on the same LAN / VPN like Tailscale).
2. **Room Code (TCP Relay)**: The host creates a room on a relay server and shares a 6-character code. The client enters the code. The relay server forwards TCP traffic between peers. Requires a relay server running on a public VPS (`python3 -m reseau.relay_server`). Configure `RELAY_HOST`/`RELAY_PORT` in `parametres.py`.

### Echolocation System (`core/carte.py`)

The core visual mechanic. Two modes:
- **Radial echo** (`E` key): 360 rays, 150px range, 2.5s cooldown
- **Directional echo** (unlockable): cone ±25°, 300px range, 4s cooldown

Rays are cast pixel-by-pixel from the player position. Revealed tiles are stored in a 2D boolean `vis_map` (persisted in save files). The camera applies a halo mask (`ui/camera.py` → `creer_masque_halo`) so only echoed/nearby areas are visible. Pre-baked map surface (`_carte_prebake`) is rebuilt only when `vis_map` changes.

### Map Format

TMX file (`assets/MapS2.tmx`) loaded via `core/carte.py` (XML parsing). Layers named `Wall.*` and `Sol.*` produce solid tiles (type 1); everything else is empty (type 0). Fallback: `map.json` flat grid.

### Save System

3 save slots → `slot_1.json`, `slot_2.json`, `slot_3.json`. JSON format, managed by `sauvegarde/gestion_sauvegarde.py`. Saved at checkpoints (tile type 3). Fields: last checkpoint ID, `vis_map`, collected items, unlocked abilities (`double_saut`, `dash`, `echo_dir`).

### Configuration & i18n

- `parametres.py` — all gameplay constants (gravity, speed, jump force, tile size 32px, screen 1920×1080, network ports, tick rates, colors, debug flags)
- `parametres.json` — user settings (language FR/EN, fullscreen, resolution, keybindings, VSync). Loaded/saved by `sauvegarde/gestion_parametres.py`
- `utils/langue.py` — bilingual text dictionaries (`FR` / `EN`), used throughout menus and HUD

### Debug Flags (in `parametres.py`)

- `MODE_DEV = True` — enables FPS counter, debug overlay, and log capture
- `REVELATION = False` — if True, reveals the entire map (skips echolocation)
- `ASSOMBRISSEMENT = True` — if False, disables darkness/halo (full visibility)
- `HALOS_MENU` / `FOND_MENU` — toggle animated menu background effects

## Default Controls

| Action | Key |
|--------|-----|
| Move | Q / D |
| Jump / Double jump | Space |
| Dash | C |
| Echo | E |
| Attack | K |
| Pause | Escape |

## Dependencies

- `pygame>=2.1.0` — game framework
- `numpy>=2.4.4` — used for halo mask generation

All networking uses Python stdlib (`socket`, `pickle`, `struct`). No external networking libraries.
