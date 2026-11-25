# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project overview

**Écho** is a cooperative multiplayer 2D action-platformer in Python/Pygame. Players perceive the level only through echolocation (raycasting). Metroidvania progression (unlockable abilities), Dark Souls-style death mechanic (lost souls). Student project (Team Nightberry).

## Conventions

* **Code, identifiers, comments, docstrings, log messages: English.** No French identifiers.
* **Player-facing text**: French is the default language; UI strings that exist in both languages live in `utils/i18n.py` (`FR` / `EN` dictionaries). Lore, tutorial, quest, HUD, notification, menu and end-of-game texts are all in `utils/i18n.py` (`lore_*`, `tuto_*`, `quest_*`, `hud_*`, `notif_*`, `menu_*` keys). `tests/test_i18n.py` checks that FR and EN have the same keys and that every key used in code exists. Remaining French literals are intentional: default nicknames (saved as player data) and the level editor.
* Simulation code must be deterministic and never read the wall clock: it takes the simulation time (`now` / `World.time_ms`) as a parameter. The server and the client prediction run the *same* `Player.apply_physics`.
* Network messages never use `pickle`; use `net/codec.py`.
* Shared level layout (torch, orbs, doors, levers, signs, boss room) is in `core/level.py`.

## Commands

```bash
pip install -r requirements.txt          # runtime: pygame, numpy
pip install -r requirements-dev.txt      # + pytest, ruff

python3 main.py                          # run the game (make run)
python -m pytest tests -q                # test suite, headless (make test)
python -m ruff check .                   # lint (make lint)
python tools/benchmark.py                # headless server-tick benchmark (make bench)
python tools/fps_benchmark.py            # whole-client FPS benchmark with a scripted bot (make fps)

python -m net.dedicated --slot 0 [--new] # headless dedicated server
python -m net.relay_server [port]        # room-code relay, default 7777
python3 tools/level_editor.py          # map editor
```

Tests run without a display (`tests/conftest.py` sets the SDL dummy drivers).

## Docs

* **`docs/NETWORK.md`**: authoritative netcode reference (transports, snapshot layout, prediction, security, diagnostics). Read it before touching `net/`, `core/world.py` snapshots/inputs, `core/prediction.py` or `client/state.py`.
* **`docs/BUILD.md`**: building an executable with PyInstaller.
* **`README.md`**: player-facing documentation (French).

## Architecture

The **server is authoritative** (physics, AI, combat, saves); clients render, read input, and *predict* their own player.

```
main.py -> Client (client/app.py)
             |- MenusMixin            ui/menus.py
             |- HudMixin              ui/hud.py
             |- GameLoopMixin         client/game_loop.py   input -> prediction ticks -> render
             |- ClientStateMixin      client/state.py       applies snapshots / state / events
             \- ClientConnectionMixin client/connection.py  join, host, relay, cleanup

net/server.py (Server)  sockets + fixed 60 Hz game thread
core/world.py (World)   the whole simulation, no sockets, unit-testable
```

When hosting, the `Server` runs in-process on a background thread; `python -m net.dedicated` runs the same `Server` with no window.

### `core/` (simulation)

| Module | Content |
|--------|---------|
| `world.py` | `World`: players, enemies, boss, objects, tick `step()`, snapshots (`snapshot_for`), state streams (`state_players/enemies/world`), events, saves |
| `player.py` | `Player`: physics (`apply_physics(now)`), combat, abilities, `export_physics`/`import_physics` for reconciliation |
| `prediction.py` | `Predictor`: client-side prediction + reconciliation |
| `collisions.py` | `collision_rects_for`: collision rects shared by server and prediction |
| `enemy.py` | `Enemy` FSM (PATROL / ALERT / CHASE), four types in `assets/enemies.json` |
| `game_map.py` | `GameMap`: TMX loading, tiles, echo raycasting, `vis_map` |
| `demon_slime_boss.py`, `boss_room.py` | Boss FSM + `BossAnimator` (Aseprite loader, also used by enemies/players), arena |
| `astar.py`, `pathfinding.py` | A* on the tilemap + async thread-pool wrapper |
| `lost_soul.py`, `free_soul.py`, `loot_soul.py` | `LostSoul` (dropped on death), `FreeSoul` (value 5), `LootSoul` (enemy drop) |
| `ability_orb.py`, `key_item.py`, `door.py`, `lever.py`, `paid_wall.py`, `torch.py`, `lore_sign.py`, `potion.py` | World objects |
| `level.py` | Shared level layout constants |
| `save_writer.py` | Background latest-wins save thread |

### `net/`

| Module | Content |
|--------|---------|
| `codec.py` | Safe bounded binary serialisation (replaces pickle), `CodecError` |
| `framing.py` | TCP frames `[u32 len][u8 flags][body]`, zlib above 512 B, bounded decompression |
| `udp.py` | `UdpEndpoint` + `UdpConnection`: reliable / unreliable / control channels, keyed latest-state streams, fragmentation, RTT |
| `protocol.py` | Constants, message types, input bits, snapshot pack/unpack |
| `server.py` | `Session` (per-client TCP/UDP I/O) and `Server` (handshake, game loop, broadcast) |
| `client.py` | `NetClient`: connect, UDP handshake, automatic TCP fallback, `poll()` |
| `sync.py` | `ServerClock`, `PositionBuffer` (interpolation of remote entities) |
| `relay_server.py`, `relay_client.py` | Room-code relay (TCP only) |
| `dedicated.py` | Headless server CLI |

Key facts: fixed tick `TICK_MS = 16.667` (60 Hz); `PROTOCOL_VERSION = 2`; TCP `5555`, UDP `5556`; server binds `0.0.0.0` (VPN-friendly); snapshot ~60-300 B with interest management (enemies within 900 px); the snapshot includes an *owner block* with the receiver's physics state for reconciliation.

### Other packages

* `storage/`: `saves.py` (slots `slot_1..3.json`, atomic writes, bit-packed `vis_map`, legacy migration), `checkpoints.py`, `settings_io.py` (`user_settings.json`, migrates `parametres.json`). Save location: project folder, or `%LOCALAPPDATA%\Echo` / `~/.local/share/Echo` for a frozen executable.
* `ui/`: menus, HUD, camera (`create_mask_halo`, numpy), button/slider widgets, splash, tutorial, quests, visual effects.
* `tools/`: `level_editor.py` (TMX level editor, code in `tools/editor/`) and `benchmark.py`.
* `packaging/`: PyInstaller build scripts. `docs/`: `NETWORK.md`, `BUILD.md`.
* `utils/paths.py`: `asset_path()`, resolves files in `assets/` in development and in a PyInstaller bundle. Always use it instead of `__file__` / `sys._MEIPASS`.
* `utils/`: `clipboard.py` (Win32 clipboard, no subprocess), `crash_report.py` (crash.log + message box, installed by `main.py`), `cache.py` (memoised text/flip, precomputed echo rays), `i18n.py`, `music.py`.
* `client/end_crystal_sequence.py`: end-of-game cutscene. `client/selftest.py`: `Echo --selftest <file>` check used to validate a built executable.

### Echolocation

Radial echo (`E`): 360 rays, 150 px, 2.5 s cooldown. Directional echo (`Y`, unlockable): ±25°, 300 px, 4 s cooldown. Revealed tiles go to a boolean `vis_map` (saved). The camera masks everything outside the revealed/near area; the pre-baked map surface is rebuilt only when `vis_map` changes. Pathfinding enemies of type "tracker" react to echoes within a hearing radius.

### Map

`assets/MapS2.tmx` (Tiled). Layers `Wall.*` and `Sol.*` produce solid tiles (type 1), tile type 3 is a checkpoint. Tile size 32 px. Start checkpoint `"32_12"`.

## Gameplay constants (`settings.py`)

| Constant | Value |
|----------|-------|
| `TILE_SIZE` | 32 px |
| Screen / zoom | 1920x1080, zoom 2.5x |
| `PLAYER_SPEED`, `JUMP_FORCE`, `GRAVITY` | 5, 15, 0.6 |
| Attack | 200 ms duration, 800 ms cooldown, range 40 |
| Dash | 128 px, 150 ms |
| Echo | 150 px radial, 300 px directional |
| Orb costs | double jump 30 souls, dash 50 souls |
| Lore sign | 30 souls |

Debug flags: `DEV_MODE` (FPS overlay, all abilities unlocked; **disable before exposing a server**), `REVEAL_ALL`, `DARKNESS_ENABLED`, `USE_UDP` (False forces TCP). Network: `TCP_PORT`, `UDP_PORT`, `RELAY_HOST`/`RELAY_PORT` (empty host = relay disabled), `INTERP_DELAY_MS`.

## Default controls

Move Q/D, jump Space, dash C, echo E, directional echo Y, attack K, interact E (in range), pause Escape. Rebindable in the settings menu.

## Tests

`tests/`: `test_codec` (round trips, fuzzing), `test_framing`, `test_udp` (loss/duplication/reordering), `test_prediction` (client vs server determinism), `test_net_integration` (real server + clients over loopback), `test_relay`, `test_client_smoke` (whole headless `Client`), `test_storage` (saves, migration). Run them after any change to physics, protocol or storage: prediction tests fail if client and server physics diverge.
