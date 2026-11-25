# client.py
# Client: entry point of the game on the player's machine.
# Composed of mixins, each with one responsibility:
#   - MenusMixin            (ui/menus.py)          all menus
#   - HudMixin              (ui/hud.py)            in-game HUD (health, boss, death, debug)
#   - GameLoopMixin         (client/game_loop.py)         main loop, input, prediction ticks, rendering
#   - ClientStateMixin      (client/state.py)      applying server data to local entities
#   - ClientConnectionMixin (client/connection.py) joining / hosting / teardown


import pygame
from utils import clipboard
from utils.paths import asset_path

from core import level
from core.torch import Torch
from settings import *
from storage import settings_io
from ui.camera import create_mask_halo
from ui.hud import HudMixin
from ui.menus import MenusMixin
from ui.splash_screen import show_splash_screen
from utils import i18n, music
from client.connection import ClientConnectionMixin
from client.state import ClientStateMixin
from client.game_loop import GameLoopMixin


class Client(MenusMixin, HudMixin, GameLoopMixin, ClientStateMixin, ClientConnectionMixin):
    """Main client class of the game."""

    def __init__(self):
        pygame.init()

        # Settings and language (loaded early to know the target screen)
        self.settings = settings_io.load_settings()
        i18n.set_language(self.settings['gameplay']['language'])
        music.init(self.settings)

        # Native resolution of the target screen (according to display_index)
        try:
            self._desktop_sizes = pygame.display.get_desktop_sizes()
        except Exception:
            _info = pygame.display.Info()
            self._desktop_sizes = [(_info.current_w, _info.current_h)]

        idx = self.settings['video'].get('display_index', 0)
        if idx < 0 or idx >= len(self._desktop_sizes):
            idx = 0
            self.settings['video']['display_index'] = 0
        self.resolution_native = self._desktop_sizes[idx]

        # Precompute the halo masks
        self._mask_halo_player = create_mask_halo(PLAYER_HALO_RADIUS, HALO_GRADIENT_WIDTH)
        self._mask_halo_torch = create_mask_halo(TORCH_LIGHT_RADIUS, HALO_GRADIENT_WIDTH)
        zoom = CAMERA_ZOOM
        self._surface_virtual = pygame.Surface((int(SCREEN_WIDTH / zoom), int(SCREEN_HEIGHT / zoom)))

        # Icon
        try:
            icon = pygame.image.load(asset_path('favicon.png'))
            pygame.display.set_icon(icon)
        except Exception as e:
            print(f"[CLIENT] cannot load the window icon: {e}")

        # Screen - the resolution and the effective zoom are computed by apply_settings_video
        self.width_screen = SCREEN_WIDTH
        self.height_screen = SCREEN_HEIGHT
        self.zoom_effective = CAMERA_ZOOM
        self.apply_settings_video(first_time=True)
        pygame.display.set_caption(i18n.get_text("title_game"))
        self.clock = pygame.time.Clock()

        # Animation time
        self.time_anim = 0

        # Splash screen
        show_splash_screen(self.screen, duration=3000)

        # State machine
        self.game_state = "MENU_MAIN"
        self.previous_game_state = "MENU_MAIN"
        self.inner_game_state = "GAME"
        self.running = True

        # Per-session state: network client, entities, in-game UI
        self._server_instance = None
        self._reset_session_state()
        self.torch = Torch(x=level.TORCH_POS[0], y=level.TORCH_POS[1])

        # Per-session state: network client, entities, in-game UI
        h = self.height_screen
        self.font_title = pygame.font.Font(None, max(96, h // 7))
        self.font_button = pygame.font.Font(None, max(30, h // 28))
        self.font_text  = pygame.font.Font(None, max(24, h // 36))
        self.font_small  = pygame.font.Font(None, max(18, h // 48))

        # Fonts
        self.settings_temp = {}
        self.key_to_modify = None
        self.id_slot_to_overwrite = None
        self.scroll_y_params = 0
        self.message_error_connection = None

        # Temporary menu state
        try:
            pygame.scrap.init()
        except Exception:
            pass

        # Clipboard
        self.create_widgets_menu_main()
        self.create_widgets_menu_join()
        self.create_widgets_menu_settings()
        self.create_widgets_menu_brightness()
        self.create_widgets_menu_pause()
        self.create_widgets_menu_slots()
        self.create_widgets_menu_confirmation()

        self._dead_since = None
        self._codes_keys = {}
        self._recompute_codes_keys()

    # Create every menu widget
    # ------------------------------------------------------------------
    # CONTROLS

    def _recompute_codes_keys(self):
        ctrl = self.settings.get('controls', {})
        self._codes_keys = {}
        self._codes_mouse  = {}
        for name, val in ctrl.items():
            if isinstance(val, str) and val.startswith("mouse_"):
                try:
                    self._codes_mouse[name] = int(val.split("_")[1])
                except (ValueError, IndexError):
                    pass
            else:
                try:
                    self._codes_keys[name] = pygame.key.key_code(val)
                except Exception:
                    self._codes_keys[name] = None

    # ------------------------------------------------------------------
    # LAYOUT PROPERTIES
    # ------------------------------------------------------------------

    @property
    def cx(self):
        return self.width_screen // 2

    @property
    def cy(self):
        return self.height_screen // 2

    def _ui_scale(self):
        # UI scale factor: 1.0 at 1080p, 2.0 at 2160p (4K), etc.
        return self.height_screen / SCREEN_HEIGHT

    def _scale(self, value):
        # Convert a value in reference pixels (1080p) to the current resolution.
        return max(1, int(round(value * self._ui_scale())))

    def _width_button(self):
        return max(260, self._scale(420))

    def _height_button(self):
        return max(40, self._scale(54))

    def _spacing_button(self):
        return max(10, self._scale(18))

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def refresh_languages_widgets(self):
        i18n.set_language(self.settings['gameplay']['language'])
        pygame.display.set_caption(i18n.get_text("title_game"))
        self.btn_new_game.text = i18n.get_text("menu_new_game")
        self.btn_continue.text       = i18n.get_text("menu_continue")
        self.btn_join.text       = i18n.get_text("menu_join")
        self.btn_settings.text      = i18n.get_text("menu_settings")
        self.btn_quit.text         = i18n.get_text("menu_quit")
        self.btn_connect.text       = i18n.get_text("join_connect")
        self.btn_back_join.text = i18n.get_text("join_back")
        self.btn_apply_params.text = i18n.get_text("param_apply")
        self.btn_back_params.text   = i18n.get_text("param_back")
        if hasattr(self, 'btn_apply_brightness'):
            self.btn_apply_brightness.text = i18n.get_text("param_apply")
            self.btn_back_brightness.text    = i18n.get_text("param_back")
        self.btn_pause_resume.text = i18n.get_text("pause_resume")
        self.btn_pause_settings.text = i18n.get_text("pause_settings")
        self.btn_popup_yes.text       = i18n.get_text("popup_yes")
        self.btn_popup_not.text       = i18n.get_text("popup_not")

    def copy_in_clipboard(self, text):
        return clipboard.copy_text(text)

    def apply_settings_video(self, first_time=False):
        idx = self.settings['video'].get('display_index', 0)
        if idx < 0 or idx >= len(getattr(self, '_desktop_sizes', [(0, 0)])):
            idx = 0
            self.settings['video']['display_index'] = 0
        self.resolution_native = self._desktop_sizes[idx]

        if self.settings['video']['fullscreen']:
            new_w, new_h = self.resolution_native
            flags = pygame.SCALED | pygame.FULLSCREEN
        else:
            res = self.settings['video'].get('resolution', [SCREEN_WIDTH, SCREEN_HEIGHT])
            new_w, new_h = res[0], res[1]
            flags = pygame.SCALED

        self.zoom_effective = CAMERA_ZOOM * (new_w / SCREEN_WIDTH)

        # Changing the screen (display_index) can NOT be applied live:
        # the SCALED renderer of pygame/SDL2 becomes unstable and crashes a few
        # seconds later. So the currently active display_index is used for
        # set_mode, and the new choice is kept in memory for the next launch.
        cur_display_active = getattr(self, '_display_index_active', idx)
        idx_for_set_mode = idx if first_time else cur_display_active

        # Recompute the resolution if the active screen must be used instead of the chosen one
        if not first_time and idx_for_set_mode != idx:
            self.resolution_native = self._desktop_sizes[idx_for_set_mode]
            if self.settings['video']['fullscreen']:
                new_w, new_h = self.resolution_native
                self.zoom_effective = CAMERA_ZOOM * (new_w / SCREEN_WIDTH)

        needs_mode_change = first_time
        if not first_time:
            surf = pygame.display.get_surface()
            if surf:
                cur_flags = surf.get_flags()
                cur_size  = surf.get_size()
                needs_mode_change = (
                    (cur_size != (new_w, new_h)) or
                    (bool(cur_flags & pygame.FULLSCREEN) != bool(flags & pygame.FULLSCREEN))
                )

        if needs_mode_change:
            try:
                self.screen = pygame.display.set_mode((new_w, new_h), flags, display=idx_for_set_mode)
            except TypeError:
                self.screen = pygame.display.set_mode((new_w, new_h), flags)
            self._display_index_active = idx_for_set_mode

        self.width_screen = new_w
        self.height_screen = new_h

        if not first_time and needs_mode_change:
            h = self.height_screen
            self.font_title  = pygame.font.Font(None, max(96, h // 7))
            self.font_button = pygame.font.Font(None, max(30, h // 28))
            self.font_text  = pygame.font.Font(None, max(24, h // 36))
            self.font_small  = pygame.font.Font(None, max(18, h // 48))
            self.create_widgets_menu_main()
            self.create_widgets_menu_join()
            self.create_widgets_menu_settings()
            self.create_widgets_menu_brightness()
            self.create_widgets_menu_pause()
            self.create_widgets_menu_slots()
            self.create_widgets_menu_confirmation()


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    client_game = Client()
    client_game.launch_application()
