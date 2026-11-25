# NETWORK.md - Echo netcode

Reference for everything under `net/` plus the parts of `core/` and the client that
depend on it. Read it before touching networking, `core/world.py` (snapshots / inputs),
`core/prediction.py` or `client/state.py`.

## 1. Goals and design

* **Low perceived latency.** The local player is *predicted*: the client runs the same
  physics as the server and applies its own inputs immediately (zero input lag whatever
  the RTT). The server stays authoritative and corrects the client when they disagree.
* **LAN play unchanged.** A host runs the server in-process; friends type the host's IP
  (TCP `5555` + UDP `5556`). VPNs (Tailscale, Hamachi) work because the server binds to
  all interfaces.
* **Robust.** UDP failure falls back to TCP automatically (also mid-game). Relay (room
  code) sessions are TCP-only.
* **Safe.** No `pickle` anywhere (see section 9). All input is bounded and validated.

```
 CLIENT                                         SERVER
 client/game_loop.py   ->  net/client.py  == TCP ==  net/server.py -> core/world.py
 client/state.py <-  (NetClient)    == UDP ==  (Server)         (World: simulation only)
 core/prediction.py
```

## 2. Simulation clock

Server and client prediction both advance **one fixed tick** of `TICK_MS = 16.667 ms`
(`TICK_RATE = 60`). `World.time_ms` is the simulation clock; `pygame.time.get_ticks()` must
never be used in simulation code. Timers that matter to prediction (coyote time, dash
cooldown, jump buffer, knockback) are exchanged as *tick counts*, converted with a
half-tick margin (`Player.export_physics` / `import_physics`) so that both sides take
identical decisions without rounding ties.

## 3. Transports

### 3.1 TCP (`net/framing.py`)

`[uint32 length][uint8 flags][body]`, flags bit 0 = zlib (only when the body >= 512 B).
Body = `net.codec` encoding of `[message_type, payload_bytes]`. Max frame 4 MiB (64 KiB for
client -> server). Decompression is bounded (zip-bomb safe).

TCP carries the handshake and is the fallback for every message. Server -> client
snapshots over TCP are coalesced: if the client is slow only the freshest snapshot is kept.

### 3.2 UDP (`net/udp.py`)

14-byte header `!IIIBB`: `seq`, `ack`, `ack_bits` (32), `channel`, `type`.

| Channel | Behaviour |
|---------|-----------|
| 0 unreliable | Dropped if older than the newest of its type |
| 1 reliable | Retransmitted until acknowledged, delivered at most once, **not ordered** |
| 2 control | Handshake, heartbeat (1 s), disconnect |

Reliable messages may carry a **key**: only the newest version of a key is ever delivered
(stale retransmissions are dropped on both sides). Messages larger than 1000 B are
fragmented (max 64 fragments) and reassembled. RTT is measured from first-try
acknowledgements (Karn).

## 4. Message types (`net/protocol.py`)

| Type | Direction | Channel | Content |
|------|-----------|---------|---------|
| `T_SNAPSHOT` | S -> C | unreliable | Binary, 60 Hz (section 5) |
| `T_STATE` | S -> C | reliable, keyed | `codec` dict, only when changed (section 6) |
| `T_EVENTS` | S -> C | reliable | `codec` list of events (sounds, visibility, rewards) |
| `T_INPUT` | C -> S | unreliable | Last <= 8 inputs, redundant (section 7) |
| `T_ACTION` | C -> S | reliable | `codec` dict: `hello`, `profile`, `echo`, `echo_dir`, `torch`, `interact` |
| `T_PING` / `T_PONG` | both | unreliable | RTT measurement |
| `T_HANDSHAKE` / `_ACK` / `T_HEARTBEAT` / `T_DISCONNECT` | both | control | UDP session management |

## 5. Snapshot (server -> client, 60 Hz, ~60-300 bytes)

```
uint32 t_ms (simulation time) | uint8 n_players
  n x [int8 id | int16 x | int16 y | uint8 flags]        flags: dash, attack, dead, facing, on_ground, moving
uint16 n_enemies
  n x [uint16 id | int16 x | int16 y | uint8 flags]      only enemies within 900 px of the receiver
[uint8 boss_present | int16 x | int16 y]
OWNER BLOCK (physics of the receiving player, ~70 B):
  uint32 ack_seq | int32 x | int32 y | float64 vel_y | flags | dash dir | air dashes |
  float64 dash distance | float64 recoil vx | abilities | 5 timers (ticks)
```

`ack_seq` is the last input the server simulated for this player. Positions are `int16`
(the map is 3200 x 2240 px). Enemy *details* (hp, animation state) are not in the snapshot.

## 6. State streams and events

`T_STATE` payload is `{"k": key, ...}` with key = `KEY_PLAYERS` (nickname, hp, money,
abilities, cooldown ages), `KEY_ENEMIES` (hp, anim state, attack timing) or `KEY_WORLD`
(souls, orbs, signs, doors, levers, key, torch, destroyed walls, boss state, potions).
The server builds each stream at 20 Hz, compares the encoded bytes with what each client
last received, and sends only on change (or every 500 ms as a refresh). Ages are capped
and quantised so an idle stream stops changing.

`T_EVENTS` entries (`{"e": kind, ...}`): `sound` (name, source player, position - the
client ignores far sounds and sounds it already predicted), `vis_full` (bit-packed
visibility map, once at join), `vis` (newly revealed tile indices), `quest_reward`.

## 7. Inputs, prediction and reconciliation

Input byte: `IN_LEFT | IN_RIGHT | IN_JUMP | IN_ATTACK | IN_DASH`. The client produces **one
input per tick** (fixed-step accumulator, up to 6 catch-up ticks per frame) numbered
`seq`, applies it locally (`core/prediction.py`) and sends the last 8 inputs in every
packet, so single lost packets cost nothing.

Server (`World._consume_inputs`): per-player queue, one input consumed per tick, at most 3
queued (older ones dropped to catch up), starvation repeats the held keys. Attack presses
are buffered 120 ms.

Reconciliation (`Predictor.reconcile`): compare the predicted state after input `ack_seq`
with the server's. Equal -> nothing. Different -> adopt the server state, replay the inputs
after `ack_seq`, count a correction. Dead players are not simulated. Tests show **zero
corrections** over 1500 ticks of random play with 0/3/12 ticks of latency, and convergence
after packet loss.

## 8. Remote entities, clock and interpolation

`ServerClock` keeps the minimum of `local_arrival - server_time` over ~3 s (best estimate
of the clock offset). Remote players, enemies and the boss are rendered at
`server_now - delay` by interpolating a `PositionBuffer` (1 s of history, <= 100 ms
extrapolation). `delay = max(INTERP_DELAY_MS = 60, 2 x jitter + 20)` capped at 200 ms.

## 9. Security

* `net/codec.py` replaces pickle: only `None/bool/int/float/str/bytes/list/tuple/dict`,
  bounded depth/length/size, any malformed input raises `CodecError`. Fuzz-tested.
* TCP: bounded frame size, bounded decompression, 5 s handshake timeout, per-session
  message rate limit (1500/s), garbage disconnects only the offender.
* UDP: a one-time 256-bit token (received over TCP) must be presented to register an
  address; handshake attempts are rate-limited per IP; unknown addresses cannot send
  anything else; datagrams from a registered address are processed by its session only.
* Relay: bounded command lines, per-IP connection limits, failed-join rate limit, rooms
  expire when the host goes silent.
* Not provided: encryption / authentication of the peer after the handshake (use a VPN
  for untrusted networks); the host is trusted (cooperative game).

## 10. Handshake and fallback

1. TCP connect. Server sends `{proto, id, udp_token, udp_port}` (or `{error: SERVER_FULL}`);
   the client refuses a different `proto`.
2. Client replies with a `hello` action (nickname, skin). The server creates the player.
3. If a token was offered the client sends `T_HANDSHAKE{token}` over UDP every 200 ms for
   3 s. On `T_HANDSHAKE_ACK` gameplay traffic moves to UDP, else it stays on TCP.
4. If UDP times out later (4 s without datagrams) both sides switch back to TCP.
5. A session silent for 10 s (TCP and UDP) is dropped; the player id is recycled.

## 11. Relay (`net/relay_server.py`, `relay_client.py`)

Room-code play without port forwarding. Host -> `host` command, receives a 6-letter code,
keeps the control socket open (keep-alive byte every 30 s). Joiner -> `join` + code; the relay
asks the host to open a data socket for the new slot and then copies bytes both ways. The
game protocol runs unchanged on top, over TCP only.

## 12. Dedicated server

`python -m net.dedicated [--slot N] [--new] [--tcp-port P] [--udp-port P] [--relay-host H]`
runs the same `Server` without a window (SDL dummy driver). The first player to connect gets
id 0 and owns the save slot.

## 13. Tests and diagnostics

| Test file | Covers |
|-----------|--------|
| `tests/test_codec.py` | codec round trips, fuzzing, malicious pickle, bounds |
| `tests/test_framing.py` | TCP frames, fragmentation, zip bombs, oversized frames |
| `tests/test_udp.py` | reliability under loss/duplication/reordering, keyed streams, fragments, binary layouts |
| `tests/test_prediction.py` | determinism of prediction vs server, latency, loss, teleports |
| `tests/test_net_integration.py` | real server + clients over loopback (UDP and TCP), abuse cases |
| `tests/test_relay.py` | room-code play through a real relay |
| `tests/test_client_smoke.py` | whole `Client` hosting and playing headless |

| Symptom | Where to look |
|---------|---------------|
| Rubber-banding of the local player | `Predictor.corrections` (should stay ~0); a mismatch means client and server physics diverged (different map state, door state, or non-deterministic code in `Player.apply_physics`) |
| Remote players jitter | `ServerClock.jitter_ms()`, snapshot loss; raise `INTERP_DELAY_MS` |
| Stuck on TCP | log `UDP handshake failed`: open UDP `5556` on the host |
| Dropped after 10 s | firewall blocking both transports, or a frozen client |
| `version` error on join | different `PROTOCOL_VERSION`: update both machines |
| Server tick over budget | `python tools/benchmark.py` (budget 16.7 ms/tick, ~1 ms measured) |
