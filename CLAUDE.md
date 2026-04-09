# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

```bash
python main.py        # Launch client (entry point)
python client.py      # Alternative entry point
make                  # Runs python3 client.py
```

The game is a multiplayer metroidvania. Hosting starts an embedded server on port 5555; joining requires the host's IP.

## Architecture

**Client-Server model over TCP with pickle serialization.** The server is authoritative for all game state (physics, combat, AI). Clients only handle input and rendering.

### Key files

- `client.py` — Main client class, inherits from 3 mixins: `MenusMixin` (ui/menus.py), `HudMixin` (ui/hud.py), `BoucleJeuMixin` (boucle_jeu.py)
- `boucle_jeu.py` — Client game loop: input, network send/receive, rendering, entity sync
- `reseau/serveur.py` — Server: game loop, physics, AI, combat, save triggers, state broadcast
- `reseau/protocole.py` — Network functions: 4-byte length prefix + pickle payload
- `parametres.py` — All game constants (physics, combat, timers, colors, network)
- `core/carte.py` — Tilemap (TMX), raycasting echolocation, visibility maps, collision rects

### Entity pattern

Every game entity follows the same pattern:
- Server creates and owns the entity, stored in a dict (`self.ennemis`, `self.ames_libres`, etc.)
- `get_etat()` serializes to dict for network broadcast
- `set_etat(data)` deserializes on client side
- `dessiner(surface, camera_offset, temps_ms)` renders on client
- `mettre_a_jour(...)` runs server-side logic each frame

Entities: `Joueur`, `Ennemi`, `AmeLibre`, `AmeLoot`, `AmePerdue`, `Cle`, `Torche`, `DemonSlimeBoss`

### Server game loop order (serveur.py `boucle_jeu_serveur`)

1. Echo reveal progression (raycasting)
2. Free souls + loot orbs: physics/animation + player pickup
3. Key: animation + pickup
4. Enemies: AI patrol + physics + respawn
5. Boss room update
6. Per-player: physics, attack collision, damage, death/respawn, checkpoint save
7. Broadcast state to all clients at `TICK_RATE_RESEAU` (60 Hz)

### Client network sync (boucle_jeu.py)

Client sends input dict each frame, receives full game state, then syncs local entity dicts by ID (create/update/delete pattern). Rendering happens on `surface_virtuelle` with camera offset, then scaled to screen.

### Threading

- Server main thread: `boucle_jeu_serveur()` at 60 FPS
- One handler thread per client: `gerer_client()`
- `self.lock` protects shared game state; `self._broadcast_lock` protects broadcast buffer

### Save system

3 JSON slots (`slot_1.json` to `slot_3.json`). Saves checkpoint ID, visibility map, abilities, money. Only the host (player 0) can save. Checkpoints are tile type 3 on the map.

## Code conventions

- All code and comments are in **French**
- Constants in `parametres.py` use UPPER_SNAKE_CASE
- Tile size is 32px (`TAILLE_TUILE`), zoom is 2.5x (`ZOOM_CAMERA`)
- Physics: custom gravity (0.6/frame), AABB collision resolved X then Y separately
- Echolocation: 360-ray raycasting from player position, per-player boolean visibility grid
- Darkness overlay with player halo (80px) and optional torch light (120px)

## Dependencies

- Python 3.8+
- pygame (only external dependency)
- No tests, no linter, no CI configured
