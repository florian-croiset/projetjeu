#!/usr/bin/env python3
"""Server-side benchmark of the Echo simulation.

Runs the headless ``World`` with several scripted players and extra enemies, as
fast as possible (no sleeping), and reports how much of the 16.7 ms tick budget
one simulation step + the network serialisation uses.

Usage:
    python tools/benchmark.py                  # 10 s of simulated time, 2 players, 25 extra enemies
    python tools/benchmark.py --seconds 30 --players 3 --extra-enemies 60
"""

import argparse
import os
import random
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from core.enemy import Enemy  # noqa: E402
from core.world import World  # noqa: E402
from net import codec, protocol as P  # noqa: E402
from settings import TILE_SIZE  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Echo simulation benchmark")
    parser.add_argument("--seconds", type=float, default=10.0, help="simulated seconds")
    parser.add_argument("--players", type=int, default=2)
    parser.add_argument("--extra-enemies", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def add_extra_enemies(world, count, rnd):
    """Drop ``count`` enemies on random floor tiles."""
    game_map = world.game_map
    placed = 0
    while placed < count:
        tx = rnd.randrange(2, game_map.width_map - 2)
        ty = rnd.randrange(2, game_map.height_map - 2)
        if (game_map.map_data[ty][tx] == 0 and game_map.map_data[ty + 1][tx] == 1):
            eid = max(world.enemies, default=-1) + 1
            world.enemies[eid] = Enemy(tx * TILE_SIZE, ty * TILE_SIZE, eid, max_hp=rnd.choice((1, 2, 3)))
            placed += 1


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def main():
    args = parse_args()
    rnd = random.Random(args.seed)
    pygame.init()
    pygame.display.set_mode((64, 64))
    world = World(ROOT, 0, True, save_enabled=False)
    for pid in range(args.players):
        world.add_player(pid)
    add_extra_enemies(world, args.extra_enemies, rnd)

    ticks = int(args.seconds * P.TICK_RATE)
    seqs = [0] * args.players
    bits = [0] * args.players
    step_ms, net_ms = [], []
    for _ in range(ticks):
        for pid in range(args.players):
            if rnd.random() < 0.05:
                bits[pid] = rnd.choice([0, P.IN_LEFT, P.IN_RIGHT, P.IN_RIGHT | P.IN_JUMP, P.IN_JUMP])
            seqs[pid] += 1
            world.push_inputs(pid, [(seqs[pid], bits[pid] | (P.IN_ATTACK if rnd.random() < 0.02 else 0))])
            if rnd.random() < 0.01:
                world.handle_action(pid, {'a': 'echo'})
        t0 = time.perf_counter()
        world.step()
        t1 = time.perf_counter()
        for pid in range(args.players):
            world.snapshot_for(pid)
        if world.tick % 3 == 0:
            codec.encode(world.state_players())
            codec.encode(world.state_enemies())
            codec.encode(world.state_world())
        for pid in range(args.players):
            world.pop_vis_delta(pid)
        world.pop_events()
        t2 = time.perf_counter()
        step_ms.append((t1 - t0) * 1000)
        net_ms.append((t2 - t1) * 1000)
    world.close()

    budget = 1000.0 / P.TICK_RATE
    total = [a + b for a, b in zip(step_ms, net_ms)]
    print(f"{ticks} ticks, {args.players} players, {len(world.enemies)} enemies "
          f"(budget {budget:.2f} ms per tick)")
    for name, series in (("simulation step", step_ms), ("serialisation", net_ms), ("total", total)):
        print(f"  {name:16s} avg {statistics.mean(series):6.3f} ms   p99 {percentile(series, 0.99):6.3f} ms"
              f"   max {max(series):6.3f} ms")
    print(f"  budget used (avg): {statistics.mean(total) / budget * 100:.1f} %")
    print(f"  snapshot size: {len(world.snapshot_for(0))} bytes")


if __name__ == "__main__":
    main()
