"""Client prediction must reproduce the server simulation exactly."""
import random

import pygame
import pytest

from core.game_map import GameMap
from core.player import Player
from core.prediction import Predictor
from core.world import World
from net import protocol as P

BASE = "."


@pytest.fixture(scope="module")
def pg():
    pygame.init()
    pygame.display.set_mode((64, 64))


@pytest.fixture
def rig(pg):
    world = World(BASE, 0, True, enable_pathfinding=False, save_enabled=False)
    server_player = world.add_player(0)
    server_player.can_double_jump = True
    server_player.can_dash = True
    game_map = GameMap("assets/MapS2.tmx", graphics=False)
    client_player = Player(0, 0, 0)
    predictor = Predictor(client_player, game_map, lambda: [])
    # first snapshot gives the spawn position
    predictor.reconcile(P.unpack_snapshot(world.snapshot_common() + world.owner_block(0))[4])
    return world, predictor, client_player, server_player


def random_inputs(rnd, n):
    bits, out = 0, []
    for _ in range(n):
        if rnd.random() < 0.08:
            bits = rnd.choice([0, P.IN_LEFT, P.IN_RIGHT, P.IN_RIGHT | P.IN_JUMP,
                               P.IN_LEFT | P.IN_JUMP, P.IN_JUMP])
        extra = P.IN_DASH if rnd.random() < 0.03 else 0
        out.append(bits | extra)
    return out


def owner_of(world):
    return P.unpack_snapshot(world.snapshot_common() + world.owner_block(0))[4]


@pytest.mark.parametrize("latency_ticks", [0, 3, 12])
def test_prediction_matches_server_without_corrections(rig, latency_ticks):
    world, predictor, client_player, server_player = rig
    rnd = random.Random(42)
    in_flight = []                                  # owner blocks travelling to the client
    for bits in random_inputs(rnd, 1500):
        seq = predictor.step(bits)
        world.push_inputs(0, [(seq, bits)])
        world.step()
        in_flight.append(owner_of(world))
        if len(in_flight) > latency_ticks:
            predictor.reconcile(in_flight.pop(0))
    assert predictor.corrections == 0
    # the client is `latency_ticks` ahead of the last block it received: flush them
    while in_flight:
        predictor.reconcile(in_flight.pop(0))
    assert predictor.corrections == 0
    assert (client_player.rect.x, client_player.rect.y) == (server_player.rect.x, server_player.rect.y)
    assert server_player.rect.x > 0


def test_physics_covers_jumps_and_dashes(rig):
    """Sanity check that the random scenario really exercises the interesting paths."""
    world, predictor, client_player, server_player = rig
    airborne = dashing = 0
    for bits in random_inputs(random.Random(42), 1500):
        seq = predictor.step(bits)
        world.push_inputs(0, [(seq, bits)])
        world.step()
        airborne += not server_player.on_ground
        dashing += server_player.is_dashing
    assert airborne > 100 and dashing > 5


def test_prediction_recovers_after_packet_loss_and_server_starvation(rig):
    """Inputs lost/late on the way to the server cause corrections, then it converges."""
    world, predictor, client_player, server_player = rig
    rnd = random.Random(7)
    for bits in random_inputs(rnd, 800):
        seq = predictor.step(bits)
        if rnd.random() > 0.1:                      # 10 % of inputs never reach the server
            world.push_inputs(0, [(seq, bits)])
        world.step()
        predictor.reconcile(owner_of(world))
    assert predictor.corrections > 0
    # now stop pressing keys: both sides must settle on the same position
    for _ in range(200):
        seq = predictor.step(0)
        world.push_inputs(0, [(seq, 0)])
        world.step()
        predictor.reconcile(owner_of(world))
    assert (client_player.rect.x, client_player.rect.y) == (server_player.rect.x, server_player.rect.y)


def test_server_side_teleport_resyncs_client(rig):
    world, predictor, client_player, server_player = rig
    for _ in range(30):
        seq = predictor.step(P.IN_RIGHT)
        world.push_inputs(0, [(seq, P.IN_RIGHT)])
        world.step()
        predictor.reconcile(owner_of(world))
    server_player.rect.topleft = (1500, 300)        # e.g. respawn / knockback
    seq = predictor.step(0)
    world.push_inputs(0, [(seq, 0)])
    world.step()
    predictor.reconcile(owner_of(world))
    assert abs(client_player.rect.x - server_player.rect.x) <= 10
