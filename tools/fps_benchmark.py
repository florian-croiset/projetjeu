#!/usr/bin/env python3
"""Whole-client FPS benchmark: real ``Client`` + embedded server, headless, frame rate uncapped.

A scripted bot plays in worst-case conditions (extra enemies around the spawn, echoes as soon as the
cooldown allows). Reports the average FPS, the 1 % / 0.1 % lows and frame-time percentiles. The same
scenario was run on the pre-refactor code, see the "Optimisations" section of the README.

Usage:
    python tools/fps_benchmark.py                 # 20 s, 25 extra enemies
    python tools/fps_benchmark.py --duration 60 --extra-enemies 60
    python tools/fps_benchmark.py --cap-fps       # keep the normal 60 FPS cap
"""

import argparse
import os
import random
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

parser = argparse.ArgumentParser(description="Echo client FPS benchmark")
parser.add_argument("--duration", type=float, default=20.0, help="measured seconds")
parser.add_argument("--warmup", type=float, default=2.0)
parser.add_argument("--extra-enemies", type=int, default=25)
parser.add_argument("--cap-fps", action="store_true")
parser.add_argument("--seed", type=int, default=42)
args = parser.parse_args()

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import settings  # noqa: E402

settings.DEV_MODE = True            # all abilities unlocked so the bot can use them
if not args.cap_fps:
    settings.FPS = 100000

import pygame  # noqa: E402

import client.app as app  # noqa: E402
from client.game_loop import GameLoopMixin  # noqa: E402
from core.enemy import Enemy  # noqa: E402
from net import protocol as P  # noqa: E402
from storage import saves, settings_io  # noqa: E402
from utils import music  # noqa: E402

tmp = tempfile.mkdtemp(prefix="echo_bench_")
saves.get_folder_save = lambda: tmp
settings_io.get_path_absolute_settings = lambda: os.path.join(tmp, "user_settings.json")
app.show_splash_screen = lambda *a, **k: None
for name in ("start", "pause", "resume", "play_sfx", "torch_loop_start", "torch_loop_stop"):
    if hasattr(music, name):
        setattr(music, name, lambda *a, **k: None)

rng = random.Random(args.seed)
bot = {"t0": None, "dir": 1, "flip": 1.5, "jump": 0.7, "jump_until": 0.0, "attack": 0.3,
       "dash": 0.6, "echo": 0.0, "echo_dir": 1.0}
state = {"start": None, "done": False, "client": None}
frame_times = []


def bot_events(self):
    """Replaces ``GameLoopMixin.handle_game_events`` with scripted input."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            self.running = False
    now = time.perf_counter()
    if bot["t0"] is None:
        bot["t0"] = now
    t = now - bot["t0"]
    held, actions = (P.IN_RIGHT if bot["dir"] > 0 else P.IN_LEFT), []
    if t >= bot["flip"]:
        bot["dir"] *= -1
        bot["flip"] = t + 1.5 + rng.uniform(-0.2, 0.4)
    if t >= bot["jump"]:
        bot["jump_until"] = t + 0.25
        bot["jump"] = t + 1.9 + rng.uniform(-0.3, 0.3)
    if t < bot["jump_until"]:
        held |= P.IN_JUMP
    if t >= bot["attack"]:
        self._latched_bits |= P.IN_ATTACK
        bot["attack"] = t + 0.85 + rng.uniform(-0.1, 0.2)
    if t >= bot["dash"]:
        self._latched_bits |= P.IN_DASH
        bot["dash"] = t + 1.2 + rng.uniform(-0.1, 0.4)
    for key_name, action, interval in (("echo", "echo", 2.6), ("echo_dir", "echo_dir", 4.1)):
        if t >= bot[key_name]:
            actions.append({"a": action})
            bot[key_name] = t + interval
            me = self.local_players.get(self.my_id)
            if me is not None:
                radius = settings.ECHO_RANGE * (2 if action == "echo_dir" else 1)
                if not hasattr(self, "_distortions_echo"):
                    self._distortions_echo = []
                self._distortions_echo.append({
                    "start_ms": pygame.time.get_ticks(), "wx": me.rect.centerx, "wy": me.rect.centery,
                    "radius_max": radius,
                    "duration_ms": int(radius / settings.ECHO_RANGE * settings.ECHO_REVEAL_DURATION)})
    return held, actions


GameLoopMixin.handle_game_events = bot_events

real_flip = pygame.display.flip


def measured_flip(*a, **kw):
    result = real_flip(*a, **kw)
    now = time.perf_counter()
    if state["start"] is None:
        state["start"] = now
    elapsed = now - state["start"]
    if elapsed >= args.warmup:
        frame_times.append(now)
    if elapsed >= args.warmup + args.duration and not state["done"]:
        state["done"] = True
        state["client"].game_state = "MENU_MAIN"
    return result


pygame.display.flip = measured_flip


def main():
    client = app.Client()
    state["client"] = client
    client.launch_local_game(0, True)
    if client.game_state != "IN_GAME":
        raise SystemExit(f"cannot host: {client.message_error_connection}")
    world = client._server_instance.world
    next_id = max(world.enemies, default=-1) + 1
    for i in range(args.extra_enemies):
        hp = 2 if rng.random() < 0.6 else 3
        x, y = 1024 + rng.randint(-200, 200), 384 + rng.randint(-50, 50)
        world.enemies[next_id + i] = Enemy(x, y, next_id + i, max_hp=hp)
    print(f"[BENCH] {len(world.enemies)} enemies in the world")
    client.network_game_loop()
    client.cleanup_connection()

    deltas = sorted(b - a for a, b in zip(frame_times, frame_times[1:]))
    n = len(deltas)
    if n < 10:
        raise SystemExit("not enough frames measured")
    total = sum(deltas)
    low = lambda frac: 1.0 / (sum(deltas[-max(1, int(n * frac)):]) / max(1, int(n * frac)))  # noqa: E731
    print(f"frames {n + 1}, average {n / total:.1f} FPS, 1% low {low(0.01):.1f} FPS, "
          f"0.1% low {low(0.001):.1f} FPS")
    print(f"frame time: avg {statistics.mean(deltas) * 1000:.2f} ms, "
          f"p99 {deltas[int(n * 0.99) - 1] * 1000:.2f} ms, max {deltas[-1] * 1000:.2f} ms")


if __name__ == "__main__":
    main()
