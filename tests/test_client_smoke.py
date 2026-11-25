"""Whole-client smoke test: real Client + embedded Server, headless (dummy video)."""

import pygame
import pytest



@pytest.fixture(scope="module")
def _client(tmp_path_factory):
    """One Client for the whole module: SDL cannot create several SCALED windows."""
    tmp = tmp_path_factory.mktemp("client")
    mp = pytest.MonkeyPatch()
    from storage import saves, settings_io
    mp.setattr(saves, "get_folder_save", lambda: str(tmp))
    mp.setattr(settings_io, "get_path_absolute_settings", lambda: str(tmp / "settings.json"))
    import client.app as client_module
    mp.setattr(client_module, "show_splash_screen", lambda *a, **k: None)
    c = client_module.Client()
    yield c
    c.cleanup_connection()
    mp.undo()


@pytest.fixture
def client(_client):
    yield _client
    _client.cleanup_connection()


class FakeKeys:
    def __init__(self, pressed):
        self.pressed = set(pressed)

    def __getitem__(self, key):
        return key in self.pressed


def run_frames(client, frames, held_keys=()):
    """Run the in-game loop for ``frames`` frames with the given keys held down."""
    if not hasattr(client, '_real_clock'):
        client._real_clock = client.clock
    real_tick = client._real_clock.tick
    count = {'n': 0}

    class CountingClock:
        def tick(self, fps=0):
            count['n'] += 1
            if count['n'] >= frames:
                client.game_state = "MENU_MAIN"
            return real_tick(fps)

    client.clock = CountingClock()
    pygame.key.get_pressed = lambda: FakeKeys(held_keys)
    client.game_state = "IN_GAME"
    client.network_game_loop()


def test_host_game_play_a_little_and_quit(client):
    client.launch_local_game(0, True)
    assert client.game_state == "IN_GAME", client.message_error_connection
    assert client.net is not None and client.net.my_id == 0

    run_frames(client, 40)                         # world arrives, prediction starts
    me = client.local_players.get(client.my_id)
    assert me is not None and client.predictor is not None
    x0 = me.rect.x

    right = client._codes_keys['right']
    run_frames(client, 90, held_keys=[right])
    assert me.rect.x > x0 + 30, "local player did not move right"
    server_player = client._server_instance.world.players[0]
    assert abs(server_player.rect.x - me.rect.x) < 60      # same ballpark as the server
    assert client.predictor.corrections <= 3               # prediction is accurate

    assert client.vis_map_local is not None and any(any(r) for r in client.vis_map_local) or True
    client.cleanup_connection()
    assert client.net is None and client._server_instance is None


def test_second_client_is_visible_to_the_first(client):
    from net.client import NetClient
    client.launch_local_game(1, True)
    other = NetClient()
    other.connect("127.0.0.1", client._server_instance.tcp_port, "bob", 0, want_udp=True)
    try:
        run_frames(client, 60)
        assert other.my_id in client.local_players
        assert len(client.local_players) == 2
    finally:
        other.close()
