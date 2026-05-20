# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Écho** is a cooperative multiplayer 2D action-platformer in Python/Pygame where players perceive their environment exclusively through echolocation (raycasting). Metroidvania-style progression with unlockable abilities and a Dark Souls-inspired death mechanic. Student project (Cycle Préparatoire S1 & S2, Team Nightberry, 5 developers).

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

`main.py` → instantiates `Client` (`client.py`, 299 lines) → calls `lancer_application()`.

`Client` is composed of three mixins:
- **`BoucleJeuMixin`** (`boucle_jeu.py`, ~1 278 lines): in-game loop — sends inputs to server via TCP/UDP, receives authoritative state, renders the world. Also handles connection setup and hosting (starts server thread + optional relay thread).
- **`MenusMixin`** (`ui/menus.py`, ~1 263 lines): all menu screens (main, parameters, save slots, join via IP or room code, pause menu)
- **`HudMixin`** (`ui/hud.py`, ~466 lines): in-game HUD (health bar, boss indicator, death/respawn screen, echo cooldown indicator, FPS in `MODE_DEV`)

### Server

`reseau/serveur.py` (~1 157 lines) — runs in a separate thread (started from `BoucleJeuMixin` when hosting). Handles:
- Player physics (gravity, AABB collisions, movement, dash, jump) at 60 Hz
- Enemy AI — four types defined in `core/ennemi.py`: `patrouilleur` (1 PV), `garde` (2 PV), `gardien` (3 PV), `traqueur` (2 PV, listens for echoes via `RAYON_AUDITION_TRAQUEUR` 400px, A* pathfinding via `core/astar.py`)
- Combat resolution (melee attacks, boss fights via `core/demon_slime_boss.py` + `core/boss_room.py`)
- Game objects: `Porte` (doors), `OrbeCapacite` (ability orbs), `Cle` (keys), `AmePerdue`/`AmeLibre`/`AmeLoot` (souls), `Torche` (interactive lights — passive halo + echo trigger at 600px), `PancarteLore` (lore signs unlocked by spending souls), `Potion` (healing items)
- Checkpoint detection and save triggers (host only)
- Broadcasting authoritative state — see Network Protocol below

### Core Game Objects

| Class | File | Purpose |
|-------|------|---------|
| `Joueur` | `core/joueur.py` | Player: physics, combat, abilities, interpolation |
| `Ennemi` | `core/ennemi.py` | Enemy AI with FSM (PATROUILLE / ALERTE / CHASSE) |
| `Carte` | `core/carte.py` | Tilemap loading, collision, echolocation vis_map |
| `DemonSlimeBoss` | `core/demon_slime_boss.py` | Boss FSM + Aseprite animator |
| `BossRoom` | `core/boss_room.py` | Boss arena manager (collision, damage, target) |
| `AStar` | `core/astar.py` | A* on tilemap (gravity-aware edge costs) |
| `PathfindingService` | `core/pathfinding.py` | Async threadpool wrapper for A* |
| `AmePerdue` | `core/ame_perdue.py` | Soul dropped on player death |
| `AmeLibre` | `core/ame_libre.py` | Free collectible soul (value 5) |
| `AmeLoot` | `core/ame_loot.py` | Enemy-dropped soul with burst physics |
| `OrbeCapacite` | `core/orbe_capacite.py` | Ability unlock orb (double_saut / dash) |
| `Cle` | `core/cle.py` | Key item — grants `joueur.have_key` |
| `Porte` | `core/porte.py` | Interactive door — 64×96px, requires key |
| `Torche` | `core/torche.py` | Light source — toggleable, triggers Traqueur |
| `PancarteLore` | `core/pancarte_lore.py` | Lore signs — 30 âmes to unlock |
| `Potion` | `core/potion.py` | Healing items (Small: 1 HP / Large: 5 HP) |
| `BossAnimator` | `core/demon_slime_boss.py` | Aseprite JSON/PNG loader, shared by boss & enemies |

### Network Module (`reseau/`)

The netcode is **hybrid TCP+UDP**: TCP for handshake & fallback, UDP for real-time gameplay. Full reference in `RESEAU.md`.

| File | Role |
|------|------|
| `protocole.py` | TCP helpers — `send_complet` / `recv_complet` (4-byte length prefix + zlib-compressed pickle, 10 MB cap), IP detection (`obtenir_ip_locale`, `obtenir_ip_vpn` for Tailscale/Hamachi) |
| `serveur.py` | Authoritative server. Binds TCP `:5555` and UDP `:5556`. Threaded per TCP client; UDP routed by `(ip, port)`. Methods: `_udp_pomper`, `_udp_diffuser_snapshot`, `_udp_diffuser_etat_discret`, `_udp_tick` |
| `udp_protocole.py` | Binary header (`!IIHBB` — seq/ack/ack_bits/channel/type), snapshot struct format, channel & type constants |
| `udp_endpoint.py` | Non-blocking UDP socket wrapper with `pomper()` (drain loop) |
| `udp_connexion.py` | Per-peer reliability layer — seq/ack with Glenn-Fiedler bitfield, retransmission, RTT EWMA, heartbeat. Also hosts `_UnpicklerSecurise` (restricted unpickler for security) |
| `relay_server.py` | Standalone TCP relay for room-code WAN play (no UDP — relay sessions stay TCP-only). Default port 7777 |
| `relay_client.py` | Client helpers for relay rooms |

### Network Protocol

Two transports run side-by-side, gated by `USE_UDP` in `parametres.py` (set to `False` to force the legacy pure-TCP path).

**TCP `:5555`** — handshake, session params (returns `{id, udp_token, udp_port}` to the client), keepalive every 5 s, and full fallback if UDP fails.

**UDP `:5556`** — all in-game traffic when active:
- **Channel 0 UNRELIABLE** — snapshots (server→client, 60 Hz) + continuous inputs (client→server, 60 Hz)
- **Channel 1 RELIABLE** — `etat_discret` (server→client, 10 Hz, pickup/boss/door state) + one-shot inputs (`echo`, `echo_dir`, `torche`, `interagir`)
- **Channel 2 CONTROL** — handshake / heartbeat / disconnect

**Snapshot binary format** (`!IIHBB` header + body):
- Per player: id(int8) | x,y(float32×2) | vx,vy(float32×2) | flags(uint8)
- Flags player: `JFLAG_EN_DASH`(1), `EN_ATTAQUE`(2), `EST_MORT`(4), `DIRECTION_DROITE`(8)
- Per enemy: id(uint16) | x,y(float32×2) | flags(uint8)
- Flags enemy: `EFLAG_EST_MORT`(1), `CLIGNOTE`(2)

**Wire formats**: TCP uses pickle behind a 4-byte length prefix + zlib compression. UDP snapshots use a fixed `struct` layout (positions + flags); reliable-channel payloads still use pickle but go through the restricted unpickler. See `RESEAU.md` §3–4 for the full type table.

**Client interpolation**: remote players & enemies are rendered `INTERP_DELAY_MS` (100 ms) in the past via lerp between buffered snapshots. The local player skips interp. Logic lives in `pousser_snapshot_interp` / `mettre_a_jour_interp` (`core/joueur.py`, `core/ennemi.py`).

### WAN Connectivity

Two connection modes available in the "Rejoindre" menu:

1. **Direct IP**: Enter the host's IP. Requires `5555/TCP` and `5556/UDP` open on the host (or both players on LAN / Tailscale-style VPN). If UDP is blocked, the client logs `"UDP handshake échoué"` and falls back to pure TCP automatically.
2. **Room Code (TCP Relay)**: 6-char code via a public relay (`python3 -m reseau.relay_server`). Configure `RELAY_HOST`/`RELAY_PORT` in `parametres.py`. **Relay sessions are TCP-only** — no UDP path through the relay.

### Echolocation System (`core/carte.py`)

The core visual mechanic. Two modes:
- **Radial echo** (`E` key): 360 rays, 150px range, 2.5s cooldown
- **Directional echo** (`Y` key, unlockable): cone ±25°, 300px range, 4s cooldown

Rays are cast pixel-by-pixel from the player position. Revealed tiles are stored in a 2D boolean `vis_map` (persisted in save files). The camera applies a halo mask (`ui/camera.py` → `creer_masque_halo`, numpy-accelerated) so only echoed/nearby areas are visible. Pre-baked map surface (`_carte_prebake`) is rebuilt only when `vis_map` changes. Pre-computed ray direction vectors are cached in `utils/cache.py` (`DIRECTIONS_ECHO_RADIAL`, `DIRECTIONS_ECHO_DROITE`, `DIRECTIONS_GAUCHE`).

**Torche interaction**: `Torche` at (551, 1025) is toggled with `E` at 60px range. It triggers Traqueur hearing at 600px and provides a 220px halo.

### Enemy AI (`core/ennemi.py`)

Four enemy types, each using `BossAnimator` for sprite sheets:

| Type | PV | Speed | Size | Special |
|------|----|-------|------|---------|
| Patrouilleur | 1 | 2.0 | 20×24px | Fast, agile |
| Garde | 2 | 1.5 | 24×28px | Standard |
| Gardien | 3 | 1.0 | 32×40px | Tanky |
| Traqueur | 2 | 1.5 | 24×28px | Hears echoes, A* pathfinding |

FSM states: `PATROUILLE` → `ALERTE` (echo heard) → `CHASSE` (10s active chase) → back to `PATROUILLE`.
Attack: range 48px horiz / 64px vert, cooldown 1500ms, damage 1.
Respawn after 180s (if enabled).

### Boss Fight (`core/demon_slime_boss.py` + `core/boss_room.py`)

- **DemonSlimeBoss**: FSM states IDLE / WALK / CLEAVE / TAKE_HIT / DEATH. 25 HP default. Targets nearest alive player.
- **BossRoom**: Confines boss to arena rect, handles collision vs tilemap, damage (1 per swing, no double-hit per swing).
- **BossAnimator**: Aseprite JSON/PNG loader — supports Hash and Array frame formats, extracts tags and durations. Also used for player skins and all enemy types.

### Map Format

TMX file (`assets/MapS2.tmx`) loaded via `core/carte.py` (XML parsing). Layers named `Wall.*` and `Sol.*` produce solid tiles (type 1); everything else is empty (type 0). Tile type 3 = checkpoint. Fallback: `map.json` flat grid. Map is ~94×35 tiles.

### Save System

3 save slots → `slot_1.json`, `slot_2.json`, `slot_3.json`. JSON format, managed by `sauvegarde/gestion_sauvegarde.py`. Platform-specific path (AppData / ~/.local/share / ~/Library). Saved at checkpoints (tile type 3).

Save fields: `id_dernier_checkpoint`, `vis_map`, `items`, `argent` (soul currency), `ameliorations` (`double_saut`, `dash`, `echo_dir`).

Start checkpoint: `"32_12"` → pixel (1024, 384).

### Soul Economy

| Source | Value |
|--------|-------|
| AmeLibre (free soul) | 5 âmes |
| Enemy kill | ~8–15 âmes (type-dependent) |
| Ability orb: double jump | costs 30 âmes |
| Ability orb: dash | costs 50 âmes |
| PancarteLore unlock | costs 30 âmes |

On death: currency is stored in `AmePerdue` at death location. Retrievable by touching it.

### UI Modules

| File | Purpose |
|------|---------|
| `ui/menus.py` | All menus: main, join, settings, save slots, pause, confirmation |
| `ui/hud.py` | Health bar, boss bar, death screen, echo cooldown, FPS (dev) |
| `ui/camera.py` | Camera centering + `creer_masque_halo()` (numpy gradient) |
| `ui/bouton.py` | Styled buttons (normal, danger, confirm, disabled, ghost) with hover glow |
| `ui/slider.py` | Brightness / resolution slider |
| `ui/splash_screen.py` | Startup logo fade |
| `ui/tutoriel.py` | On-screen tutorial, skippable, persisted via `tutoriel_vu` flag |
| `ui/effets_visuels.py` | Echo distortion effect (radial displacement) |

### Performance Optimizations

- `utils/cache.py`: memoized `flip_h()` (512 entries), `render_text()` (256 entries), font objects; pre-computed echo ray vectors
- Collision rects pre-baked from tilemap, updated only on map load
- `_carte_prebake` surface only rebuilt when `vis_map` changes
- A* runs on a threadpool (`PathfindingService`) — non-blocking for main loop
- UDP snapshots use binary `struct`, not pickle
- Remote entity positions lerped between buffered snapshots

### Configuration & i18n

- `parametres.py` — all gameplay constants (gravity, speed, jump force, tile size 32px, screen 1920×1080, zoom 2.5×, colors). Also network: `PORT_SERVEUR=5555`, `PORT_UDP=5556`, `USE_UDP`, `TICK_RATE_SNAPSHOT_UDP=60`, `TICK_RATE_ETAT_DISCRET_UDP=10`, `INTERP_DELAY_MS=100`, `UDP_HANDSHAKE_TIMEOUT_MS=3000`
- `parametres.json` — user settings (language FR/EN, fullscreen, resolution, brightness `luminosite` 0–1, keybindings, SFX/music volume, `tutoriel_vu`, player skin 0–2). Loaded/saved by `sauvegarde/gestion_parametres.py`
- `utils/langue.py` — bilingual text dictionaries (`FR` / `EN`, ~80+ keys), used throughout menus and HUD
- `utils/music.py` — playlist management, fade in/out, volume control

### Debug Flags (in `parametres.py`)

- `MODE_DEV = True` — enables FPS counter, debug overlay, log capture (HTTP POST via `utils/envoyer_logs.py`), and **auto-unlocks all ability orbs** (disable before exposing the server publicly)
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
| Echo (radial) | E |
| Echo (directional, unlockable) | Y |
| Attack | K |
| Interact (torche, lore) | E (in range) |
| Pause | Escape |

## Key Constants (parametres.py)

| Constant | Value |
|----------|-------|
| Tile size | 32 px |
| Screen | 1920×1080, zoom 2.5× (virtual 768×432) |
| Player speed | 5 px/tick |
| Jump force | 13, gravity 0.6 |
| Max PV | 5 |
| Invulnerability | 1000ms post-damage |
| Attack duration / cooldown | 200ms / 800ms, range 40px, damage 1 |
| Dash distance / duration / cooldown | 128px / 150ms / 600ms (max 1 air use) |
| Double jump force | 10 |
| Echo radial | 360 rays, 150px, 2500ms cooldown |
| Echo directional | ±25°, 300px, 4000ms cooldown |
| Traqueur hearing | 400px radius |
| Chase duration | 10s |
| Snapshot rate | 60 Hz |
| Discrete state rate | 10 Hz |
| Interp delay | 100ms |

## File Structure

```
projetjeu/
├── main.py                          # Entry point (18 lines)
├── client.py                        # Client class (mixins, 299 lines)
├── boucle_jeu.py                    # Game loop mixin (~1278 lines)
├── parametres.py                    # Constants & config (~232 lines)
│
├── core/
│   ├── joueur.py                    # Player class (~665 lines)
│   ├── ennemi.py                    # Enemy AI (~827 lines)
│   ├── carte.py                     # Tilemap & visibility (~561 lines)
│   ├── demon_slime_boss.py          # Boss animator & FSM (~507 lines)
│   ├── boss_room.py                 # Boss arena manager (~145 lines)
│   ├── astar.py                     # A* pathfinding (~135 lines)
│   ├── pathfinding.py               # Async A* wrapper (~107 lines)
│   ├── ame_perdue.py                # Death soul (~95 lines)
│   ├── ame_libre.py                 # Free collectible soul (~132 lines)
│   ├── ame_loot.py                  # Enemy-dropped soul (~301 lines)
│   ├── orbe_capacite.py             # Ability unlock orbs (~183 lines)
│   ├── cle.py                       # Key object (~87 lines)
│   ├── porte.py                     # Interactive door (~201 lines)
│   ├── torche.py                    # Light source (~94 lines)
│   ├── pancarte_lore.py             # Lore signs (~545 lines)
│   ├── potion.py                    # Healing items (~180 lines)
│   └── map.py                       # Legacy map loader
│
├── reseau/
│   ├── protocole.py                 # TCP helpers (~93 lines)
│   ├── serveur.py                   # Authoritative server (~1157 lines)
│   ├── udp_protocole.py             # UDP binary format (~150 lines)
│   ├── udp_connexion.py             # Per-peer reliability (~300+ lines)
│   ├── udp_endpoint.py              # UDP socket wrapper (~80 lines)
│   ├── relay_server.py              # WAN room relay (~384 lines)
│   └── relay_client.py              # Relay helpers (~168 lines)
│
├── ui/
│   ├── menus.py                     # MenusMixin (~1263 lines)
│   ├── hud.py                       # HudMixin (~466 lines)
│   ├── camera.py                    # Camera & halo (~70 lines)
│   ├── bouton.py                    # Button widget (~129 lines)
│   ├── slider.py                    # Slider widget (~120 lines)
│   ├── splash_screen.py             # Startup splash (~61 lines)
│   ├── tutoriel.py                  # Tutorial system (~800 lines)
│   └── effets_visuels.py            # Visual effects (~200 lines)
│
├── sauvegarde/
│   ├── gestion_sauvegarde.py        # Save/load slots (~105 lines)
│   ├── gestion_parametres.py        # Config JSON (~104 lines)
│   └── points_sauvegarde.py         # Checkpoint system (~44 lines)
│
├── utils/
│   ├── cache.py                     # Caches & ray constants (~250 lines)
│   ├── langue.py                    # i18n FR/EN (~177 lines)
│   ├── music.py                     # Audio management (~300 lines)
│   └── envoyer_logs.py              # Debug HTTP log sender (~424 lines)
│
├── assets/                          # Sprites, fonts, audio
│   └── MapS2.tmx                    # Tiled tilemap (primary)
├── parametres.json                  # User settings (runtime)
├── slot_1.json, slot_2.json, slot_3.json  # Save files
├── map.json                         # Legacy tilemap fallback
├── demon_slime.json                 # Boss Aseprite animation data
└── README.md, RESEAU.md, CLAUDE.md  # Documentation
```

## Dependencies

- `pygame>=2.1.0` — game framework
- `numpy>=2.4.4` — used for halo mask generation (`ui/camera.py`)

All networking uses Python stdlib (`socket`, `pickle`, `struct`, `zlib`). No external networking libraries.
