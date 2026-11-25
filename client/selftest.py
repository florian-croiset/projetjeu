"""Self-test of a built executable: ``Echo.exe --selftest <result_file>``.

Hosts a throw-away game, plays a few seconds with the right key held, then writes ``OK`` or the
error to ``<result_file>``. Saves and settings go to a temporary folder, never to the user's own.
Used to check that a PyInstaller bundle really contains everything it needs.
"""

import os
import sys
import tempfile
import traceback

import pygame


class _FakeKeys:
    def __init__(self, pressed):
        self.pressed = set(pressed)

    def __getitem__(self, key):
        return key in self.pressed


def _run_frames(client, frames, held_keys=()):
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
    pygame.key.get_pressed = lambda: _FakeKeys(held_keys)
    client.game_state = "IN_GAME"
    client.network_game_loop()


def _check_settings_menu(client):
    """Open the settings menu, scroll to the bottom and click the "copy IP" button."""
    import copy
    from net.framing import local_ip
    client.settings_temp = copy.deepcopy(client.settings)
    client.previous_game_state = "MENU_MAIN"
    client._ip_local_cache = local_ip()
    client.game_state = "MENU_SETTINGS"
    for _ in range(30):
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": -1, "flipped": False}))
        client.handle_menu_settings(pygame.mouse.get_pos())
        client.draw_menu_settings()
    pos = client.btn_copy_ip_local.rect.center
    pygame.mouse.get_pos = lambda: pos
    client.handle_menu_settings(pos)
    if not client.btn_copy_ip_local.is_hovered:
        raise RuntimeError("the copy-IP button has no hover state")
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0), "buttons": (0, 0, 0)}))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": pos, "button": 1}))
    client.handle_menu_settings(pos)
    client.draw_menu_settings()
    client.game_state = "MENU_MAIN"


def _check():
    from storage import saves, settings_io
    tmp = tempfile.mkdtemp(prefix="echo_selftest_")
    saves.get_folder_save = lambda: tmp
    settings_io.get_path_absolute_settings = lambda: os.path.join(tmp, "user_settings.json")

    import client.app as app
    app.show_splash_screen = lambda *a, **k: None
    client = app.Client()
    _check_settings_menu(client)
    client.launch_local_game(0, True)
    if client.game_state != "IN_GAME":
        raise RuntimeError(f"could not host a game: {client.message_error_connection}")
    _run_frames(client, 40)
    me = client.local_players.get(client.my_id)
    if me is None or client.predictor is None:
        raise RuntimeError("the world never reached the client")
    x0 = me.rect.x
    _run_frames(client, 90, held_keys=[client._codes_keys['right']])
    if me.rect.x <= x0 + 30:
        raise RuntimeError("the local player did not move")
    client.cleanup_connection()


def run(result_path):
    try:
        _check()
        message = "OK"
    except BaseException:
        message = "FAILED\n" + traceback.format_exc()
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(message)
    pygame.quit()
    sys.exit(0 if message == "OK" else 1)
