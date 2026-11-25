"""Connecting to / hosting a game, and tearing it down again.

``ClientConnectionMixin`` is mixed into ``Client``. Everything that exists only
while a game session is running is (re)initialised by ``_reset_session_state``.
"""

import threading
import time

import pygame
from utils.paths import asset_path

from core.door import Door
from core.game_map import GameMap
from core.lore_sign import (AbilityNotification, LoreBubble, PaymentPopup, UpgradeShopPopup)
from core.potion import PotionManager
from net.client import ConnectError, NetClient
from net.server import Server
from settings import RELAY_HOST, RELAY_PORT, TCP_PORT, TILE_SIZE, USE_UDP
from ui.quest import QuestJournal, QuestWidget
from utils import i18n, music


class ClientConnectionMixin:
    # ------------------------------------------------------------------
    #  Session state
    # ------------------------------------------------------------------

    def _reset_session_state(self):
        """Put every per-session attribute back to its "no game running" value."""
        self.net = None
        self.my_id = -1
        self.game_map = None
        self.vis_map_local = None
        self._fade_surface = None
        self.echo_fade_times = {}
        self.local_players = {}
        self.local_enemies = {}
        self.local_lost_souls = {}
        self.local_free_souls = {}
        self.local_loot_souls = {}
        self.local_ability_orbs = {}
        self.local_lore_signs = {}
        self.local_doors = {}
        self.local_levers = {}
        self.passage_open = False
        self.local_paid_wall = None
        self.paid_wall_unlocked = False
        self.key_wall_destroyed = False
        self.local_key_item = None
        self.boss_local = None
        self.potions = None
        self._enemies_killed_total = 0
        self._enemies_dead_counted = set()
        self._souls_harvested_total = 0
        self._money_player_previous = None
        self._doors_were_opening = {}
        self._boss_state_previous = None
        self._boss_frame_previous = 0
        self._last_data_boss = None
        self._end_message_since = None
        self._sequence_end_triggered = False
        self._sign_active_id = None
        self._shop_item_in_waiting = None
        self._purchase_in_waiting = None
        self.bubble_lore = None
        self.popup_payment = None
        self.popup_shop_upgrades = None
        self.widget_quest = None
        self.journal_quest = None
        self.notif_ability = None
        self.inner_game_state = "GAME"
        self._reset_net_state()

    def _finalize_connection(self):
        """Load the local copy of the level and build the in-game UI."""
        self._reset_session_state_keep_net()
        self.game_map = GameMap(asset_path("MapS2.tmx"))
        Door.load_assets(asset_path("door_sheet.png"))
        self.vis_map_local = self.game_map.create_blank_visibility_map()
        size = (self.game_map.width_map * TILE_SIZE, self.game_map.height_map * TILE_SIZE)
        self._fade_surface = pygame.Surface(size, pygame.SRCALPHA)
        self._fade_surface.fill((0, 0, 0, 255))
        self.potions = PotionManager()
        w, h = self.width_screen, self.height_screen
        self.bubble_lore = LoreBubble(w, h)
        self.popup_payment = PaymentPopup(w, h)
        self.popup_shop_upgrades = UpgradeShopPopup(w, h)
        self.widget_quest = QuestWidget(self.font_button, self.font_small)
        self.journal_quest = QuestJournal(w, h, self.font_title, self.font_text, self.font_small)
        self.notif_ability = AbilityNotification(w, h)

    def _reset_session_state_keep_net(self):
        net, my_id = self.net, self.my_id
        self._reset_session_state()
        self.net, self.my_id = net, my_id

    @property
    def room_code(self):
        """Relay room code of the game we host (None if not hosting / no relay)."""
        server = getattr(self, '_server_instance', None)
        return server.room_code if server is not None else None

    # ------------------------------------------------------------------
    #  Joining
    # ------------------------------------------------------------------

    def _profile(self):
        profile = self.settings.get('profile', {})
        return profile.get('nickname', 'Player'), profile.get('skin', 0)

    def _connect_error_text(self, err, host):
        key = {'timeout': 'net_error_timeout', 'refused': 'net_error_refused',
               'address': 'net_error_address', 'full': 'net_error_full',
               'version': 'net_error_version'}.get(err.code, 'net_error_network')
        return i18n.get_text(key).format(host=f"{host}:{TCP_PORT}", detail=err.detail)

    def connect(self, host):
        """Join the server at ``host``. Returns True on success."""
        nickname, skin = self._profile()
        net = NetClient()
        try:
            print(f"[CLIENT] connecting to {host}:{TCP_PORT} ...")
            net.connect(host, TCP_PORT, nickname, skin, want_udp=USE_UDP)
        except ConnectError as err:
            net.close()
            self.message_error_connection = self._connect_error_text(err, host)
            return False
        print(f"[CLIENT] connected as player {net.my_id} "
              f"({'UDP' if net.udp_active else 'TCP'})")
        self.message_error_connection = None
        self.net, self.my_id = net, net.my_id
        self._finalize_connection()
        return True

    def connect_relay(self, room_code, relay_host=None, relay_port=None):
        """Join through a relay server using a 6-letter room code."""
        from net import relay_client
        host = relay_host or RELAY_HOST
        port = relay_port or RELAY_PORT
        nickname, skin = self._profile()
        net = NetClient()
        try:
            print(f"[CLIENT] relay {host}:{port}, room '{room_code}' ...")
            sock = relay_client.relay_join(host, port, room_code)
            net.adopt_socket(sock, nickname, skin, want_udp=False)
        except ConnectError as err:
            net.close()
            self.message_error_connection = self._connect_error_text(err, host)
            return False
        except (ConnectionError, OSError) as exc:
            net.close()
            self.message_error_connection = i18n.get_text("net_error_relay").format(
                detail=str(exc).replace("Relay: ", ""))
            return False
        self.message_error_connection = None
        self.net, self.my_id = net, net.my_id
        self._finalize_connection()
        return True

    # ------------------------------------------------------------------
    #  Hosting
    # ------------------------------------------------------------------

    def launch_local_game(self, id_slot, is_new_game=False):
        """Start a server in this process and join it."""
        self._server_instance = None
        result = {}

        def build_server():
            try:
                server = Server(id_slot, is_new_game, relay_host=RELAY_HOST, relay_port=RELAY_PORT)
                server.start()
                result['server'] = server
            except Exception as exc:                      # noqa: BLE001 - reported to the UI
                result['error'] = exc

        thread = threading.Thread(target=build_server, name="server-boot", daemon=True)
        thread.start()
        deadline = time.monotonic() + 30
        while thread.is_alive() and time.monotonic() < deadline:
            pygame.event.pump()                           # keep the window responsive
            time.sleep(0.02)
        server = result.get('server')
        if server is None:
            print(f"[CLIENT] could not start the server: {result.get('error')}")
            self.message_error_connection = i18n.get_text("net_error_network").format(
                host="localhost")
            self.game_state = "MENU_MAIN"
            return
        self._server_instance = server
        if self.connect("127.0.0.1"):
            self.game_state = "IN_GAME"
        else:
            self.cleanup_connection()
            self.game_state = "MENU_MAIN"

    # ------------------------------------------------------------------
    #  Teardown
    # ------------------------------------------------------------------

    def cleanup_connection(self):
        pygame.mouse.set_visible(True)
        if self.net is not None:
            self.net.close()
        server = getattr(self, '_server_instance', None)
        if server is not None:
            server.stop()
        self._server_instance = None
        music.torch_loop_stop()
        if getattr(self, 'torch', None):
            self.torch.lit = False
        self._reset_session_state()
