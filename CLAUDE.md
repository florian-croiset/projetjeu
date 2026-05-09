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

## Companion docs

- **`RESEAU.md`** — authoritative reference for the hybrid TCP+UDP netcode. Read it before touching anything in `reseau/` or the snapshot/interp logic in `core/joueur.py` & `core/ennemi.py`. It documents the binary header, ack-bitfield, handshake, security model, and diagnostic checklists.
- **`README.md`** — player-facing docs (gameplay mechanics, controls, team).

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
- Enemy AI — four types defined in `core/ennemi.py`: `patrouilleur` (1 PV), `garde` (2 PV), `gardien` (3 PV), `traqueur` (2 PV, listens for echoes via `RAYON_AUDITION_TRAQUEUR`, A* pathfinding via `core/astar.py`)
- Combat resolution (melee attacks, boss fights via `core/demon_slime_boss.py` + `core/boss_room.py`)
- Game objects: `Porte` (doors), `OrbeCapacite` (ability orbs), `Cle` (keys), `AmePerdue`/`AmeLibre`/`AmeLoot` (souls), `Torche` (interactive lights — passive halo + echo trigger), `PancarteLore` (lore signs unlocked by spending souls)
- Checkpoint detection and save triggers (host only)
- Broadcasting authoritative state — see Network Protocol below

### Network Module (`reseau/`)

The netcode is **hybrid TCP+UDP**: TCP for handshake & fallback, UDP for real-time gameplay. Full reference in `RESEAU.md`.

| File | Role |
|------|------|
| `protocole.py` | TCP helpers — `send_complet` / `recv_complet` (4-byte length prefix + pickle, 10 MB cap), IP detection (`obtenir_ip_locale`, `obtenir_ip_vpn` for Tailscale/Hamachi) |
| `serveur.py` | Authoritative server. Binds TCP `:5555` and UDP `:5556`. Threaded per TCP client; UDP routed by `(ip, port)`. Methods of interest: `_udp_pomper`, `_udp_diffuser_snapshot`, `_udp_diffuser_etat_discret`, `_udp_tick` |
| `udp_protocole.py` | Binary header (`!IIHBB` — seq/ack/ack_bits/channel/type), snapshot struct format, channel & type constants |
| `udp_endpoint.py` | Non-blocking UDP socket wrapper with `pomper()` (drain loop) |
| `udp_connexion.py` | Per-peer reliability layer — seq/ack with Glenn-Fiedler bitfield, retransmission, RTT EWMA, heartbeat. Also hosts `_pickle_charger_securise` (restricted unpickler for security) |
| `relay_server.py` | Standalone TCP relay for room-code WAN play (no UDP support — relay sessions stay TCP-only) |
| `relay_client.py` | Client helpers for relay rooms |

### Network Protocol

Two transports run side-by-side, gated by `USE_UDP` in `parametres.py` (set to `False` to force the legacy pure-TCP path).

**TCP `:5555`** — handshake, session params (returns `{id, udp_token, udp_port}` to the client), keepalive every 5 s, and full fallback if UDP fails.

**UDP `:5556`** — all in-game traffic when active:
- **Channel 0 UNRELIABLE** — snapshots (server→client, 60 Hz, ~180 B for 2 players + 10 enemies) + continuous inputs (client→server, 60 Hz)
- **Channel 1 RELIABLE** — `etat_discret` (server→client, 10 Hz, pickup/boss/door state) + one-shot inputs (`echo`, `echo_dir`, `torche`, `interagir`)
- **Channel 2 CONTROL** — handshake / heartbeat / disconnect

**Wire formats**: TCP uses pickle behind a 4-byte length prefix. UDP snapshots use a fixed `struct` layout (positions + flags); reliable-channel payloads still use pickle but go through the restricted unpickler. See `RESEAU.md` §3–4 for the full type table.

**Client interpolation**: remote players & enemies are rendered `INTERP_DELAY_MS` (100 ms) in the past via lerp between buffered snapshots. The local player skips interp to keep input snappy. Logic lives in `pousser_snapshot_interp` / `mettre_a_jour_interp` (`core/joueur.py`, `core/ennemi.py`).

### WAN Connectivity

Two connection modes available in the "Rejoindre" menu:

1. **Direct IP**: Enter the host's IP. Requires `5555/TCP` and `5556/UDP` open on the host (or both players on LAN / Tailscale-style VPN). If UDP is blocked, the client logs `"UDP handshake échoué"` and falls back to pure TCP automatically.
2. **Room Code (TCP Relay)**: 6-char code via a public relay (`python3 -m reseau.relay_server`). Configure `RELAY_HOST`/`RELAY_PORT` in `parametres.py`. **Relay sessions are TCP-only** — no UDP path through the relay.

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

- `parametres.py` — all gameplay constants (gravity, speed, jump force, tile size 32px, screen 1920×1080, colors). Also network: `PORT_SERVEUR=5555`, `PORT_UDP=5556`, `USE_UDP`, `TICK_RATE_RESEAU=30`, `TICK_RATE_SNAPSHOT_UDP=60`, `TICK_RATE_ETAT_DISCRET_UDP=10`, `INTERP_DELAY_MS=100`, `UDP_HANDSHAKE_TIMEOUT_MS=3000`
- `parametres.json` — user settings (language FR/EN, fullscreen, resolution, keybindings, VSync). Loaded/saved by `sauvegarde/gestion_parametres.py`
- `utils/langue.py` — bilingual text dictionaries (`FR` / `EN`), used throughout menus and HUD

### Debug Flags (in `parametres.py`)

- `MODE_DEV = True` — enables FPS counter, debug overlay, log capture, and **auto-unlocks all ability orbs** (disable before exposing the server publicly)
- `REVELATION = False` — if True, reveals the entire map (skips echolocation)
- `ASSOMBRISSEMENT = True` — if False, disables darkness/halo (full visibility)
- `USE_UDP = True` — set to False to force the legacy pure-TCP transport (useful when debugging UDP-related issues)
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
