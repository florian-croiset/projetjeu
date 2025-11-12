import pygame
import json
import os
from enum import Enum

class GameState(Enum):
    MENU = 0
    SETTINGS = 1
    GAMEPLAY = 2

class SettingsManager:
    """Manages game settings including FPS, vsync, fullscreen options, and key bindings."""
    
    def __init__(self):
        self.default_settings = {
            "fps": 60,
            "vsync": True,
            "fullscreen": False,
            "windowed_mode": True,
            "keys": {
                "up": pygame.K_UP,
                "down": pygame.K_DOWN,
                "left": pygame.K_LEFT,
                "right": pygame.K_RIGHT,
                "jump": pygame.K_SPACE,
                "attack": pygame.K_x,
                "pause": pygame.K_ESCAPE
            }
        }
        self.current_settings = self.default_settings.copy()
        self.settings_file = "settings.json"
        
    def load_settings(self):
        """Load settings from file if exists."""
        try:
            with open(self.settings_file, 'r') as f:
                self.current_settings = json.load(f)
        except FileNotFoundError:
            # If no settings file exists, use defaults
            pass
    
    def save_settings(self):
        """Save current settings to file."""
        with open(self.settings_file, 'w') as f:
            json.dump(self.current_settings, f)
    
    def get_fps(self):
        """Get current FPS setting."""
        return self.current_settings["fps"]
    
    def get_vsync(self):
        """Get current vsync setting."""
        return self.current_settings["vsync"]
    
    def get_fullscreen(self):
        """Get current fullscreen setting."""
        return self.current_settings["fullscreen"]
    
    def get_windowed_mode(self):
        """Get current windowed mode setting."""
        return self.current_settings["windowed_mode"]
    
    def get_key_binding(self, key_name):
        """Get key binding for a specific action."""
        return self.current_settings["keys"].get(key_name, self.default_settings["keys"][key_name])
    
    def set_fps(self, fps):
        """Set FPS value."""
        self.current_settings["fps"] = fps
    
    def set_vsync(self, vsync):
        """Set vsync value."""
        self.current_settings["vsync"] = vsync
    
    def set_fullscreen(self, fullscreen):
        """Set fullscreen value."""
        self.current_settings["fullscreen"] = fullscreen
    
    def set_windowed_mode(self, windowed_mode):
        """Set windowed mode value."""
        self.current_settings["windowed_mode"] = windowed_mode
    
    def set_key_binding(self, key_name, key_value):
        """Set key binding for a specific action."""
        self.current_settings["keys"][key_name] = key_value

class Menu:
    """Main menu system with navigation options."""
    
    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font = pygame.font.SysFont(None, 36)
        self.options = ["Start Game", "Settings", "Exit"]
        self.selected_option = 0
        
    def draw(self):
        """Draw menu options."""
        self.screen.fill((0, 0, 0))
        title_text = self.font.render("Metroidvania Menu", True, (255, 255, 255))
        self.screen.blit(title_text, (self.screen.get_width() // 2 - title_text.get_width() // 2, 100))
        
        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_option else (100, 100, 100)
            text = self.font.render(option, True, color)
            self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, 200 + i * 50))
    
    def handle_input(self, event):
        """Handle menu input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_option = (self.selected_option - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_option = (self.selected_option + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.selected_option
        return None

class SettingsWindow:
    """Settings window with FPS, vsync, fullscreen options."""
    
    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font = pygame.font.SysFont(None, 36)
        self.small_font = pygame.font.SysFont(None, 24)
        
        # Settings options
        self.options = [
            "FPS: " + str(self.settings_manager.get_fps()),
            "VSync: " + ("ON" if self.settings_manager.get_vsync() else "OFF"),
            "Fullscreen: " + ("ON" if self.settings_manager.get_fullscreen() else "OFF"),
            "Windowed Mode: " + ("ON" if self.settings_manager.get_windowed_mode() else "OFF"),
            "Key Settings",
            "Back"
        ]
        self.selected_option = 0
        self.key_change_mode = False
        self.current_key = None
        
    def draw(self):
        """Draw settings window."""
        self.screen.fill((30, 30, 30))
        
        title_text = self.font.render("Settings", True, (255, 255, 255))
        self.screen.blit(title_text, (self.screen.get_width() // 2 - title_text.get_width() // 2, 50))
        
        # Draw settings options
        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_option else (150, 150, 150)
            text = self.font.render(option, True, color)
            self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, 150 + i * 40))
        
        # Draw key change mode info
        if self.key_change_mode:
            key_text = self.small_font.render("Press a key to change " + self.current_key, True, (255, 255, 255))
            self.screen.blit(key_text, (self.screen.get_width() // 2 - key_text.get_width() // 2, 400))
    
    def handle_input(self, event):
        """Handle settings input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_option = (self.selected_option - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_option = (self.selected_option + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                if self.selected_option == 4:  # Key Settings
                    self.key_change_mode = True
                    self.current_key = "up"
                elif self.selected_option == 5:  # Back
                    return "back"
                else:
                    # Handle setting change
                    if self.selected_option == 0:  # FPS
                        self.settings_manager.set_fps(60)
                        self.options[0] = "FPS: " + str(self.settings_manager.get_fps())
                    elif self.selected_option == 1:  # VSync
                        self.settings_manager.set_vsync(not self.settings_manager.get_vsync())
                        self.options[1] = "VSync: " + ("ON" if self.settings_manager.get_vsync() else "OFF")
                    elif self.selected_option == 2:  # Fullscreen
                        self.settings_manager.set_fullscreen(not self.settings_manager.get_fullscreen())
                        self.options[2] = "Fullscreen: " + ("ON" if self.settings_manager.get_fullscreen() else "OFF")
                    elif self.selected_option == 3:  # Windowed Mode
                        self.settings_manager.set_windowed_mode(not self.settings_manager.get_windowed_mode())
                        self.options[3] = "Windowed Mode: " + ("ON" if self.settings_manager.get_windowed_mode() else "OFF")
            elif event.key == pygame.K_ESCAPE:
                if self.key_change_mode:
                    self.key_change_mode = False
                    self.current_key = None
        return None
    
    def handle_key_input(self, event):
        """Handle key input when changing keys."""
        if self.key_change_mode and event.type == pygame.KEYDOWN:
            if self.current_key:
                # Set the new key binding
                self.settings_manager.set_key_binding(self.current_key, event.key)
                self.key_change_mode = False
                self.current_key = None
                
                # Update options to reflect changes
                self.options[4] = "Key Settings"
                return True
        return False

class KeySettingsWindow:
    """Key settings window for changing key bindings."""
    
    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font = pygame.font.SysFont(None, 36)
        self.small_font = pygame.font.SysFont(None, 24)
        
        self.keys = [
            ("Up", "up"),
            ("Down", "down"),
            ("Left", "left"),
            ("Right", "right"),
            ("Jump", "jump"),
            ("Attack", "attack"),
            ("Pause", "pause")
        ]
        self.selected_key = 0
        
    def draw(self):
        """Draw key settings window."""
        self.screen.fill((40, 40, 40))
        
        title_text = self.font.render("Key Settings", True, (255, 255, 255))
        self.screen.blit(title_text, (self.screen.get_width() // 2 - title_text.get_width() // 2, 50))
        
        # Draw key options
        for i, (name, key_name) in enumerate(self.keys):
            color = (255, 255, 255) if i == self.selected_key else (150, 150, 150)
            text = self.font.render(name + ": " + pygame.key.name(self.settings_manager.get_key_binding(key_name)), True, color)
            self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, 150 + i * 40))
    
    def handle_input(self, event):
        """Handle key settings input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_key = (self.selected_key - 1) % len(self.keys)
            elif event.key == pygame.K_DOWN:
                self.selected_key = (self.selected_key + 1) % len(self.keys)
            elif event.key == pygame.K_RETURN:
                # Start changing this key
                return self.keys[self.selected_key][1]
        return None

class GamePlayer:
    """Main game player with movement using dt for FPS handling."""
    
    def __init__(self, screen, settings_manager):
        self.screen = screen
        self.settings_manager = settings_manager
        self.font = pygame.font.SysFont(None, 36)
        
        # Player state
        self.x = 100
        self.y = 100
        self.velocity_x = 0
        self.velocity_y = 0
        self.speed = 5
        
        # Game state
        self.running = True
        
    def update(self, dt):
        """Update player position with delta time."""
        # Apply velocity to position
        self.x += self.velocity_x * dt * self.speed
        self.y += self.velocity_y * dt * self.speed
        
        # Keep player in screen bounds
        self.x = max(0, min(self.screen.get_width() - 20, self.x))
        self.y = max(0, min(self.screen.get_height() - 20, self.y))
        
    def draw(self):
        """Draw player."""
        pygame.draw.rect(self.screen, (255, 0, 0), (self.x, self.y, 20, 20))
        
    def handle_input(self, event):
        """Handle input events for player movement."""
        if event.type == pygame.KEYDOWN:
            key = self.settings_manager.get_key_binding("up")
            if event.key == key:
                self.velocity_y -= 1
            key = self.settings_manager.get_key_binding("down")
            if event.key == key:
                self.velocity_y += 1
            key = self.settings_manager.get_key_binding("left")
            if event.key == key:
                self.velocity_x -= 1
            key = self.settings_manager.get_key_binding("right")
            if event.key == key:
                self.velocity_x += 1
        elif event.type == pygame.KEYUP:
            key = self.settings_manager.get_key_binding("up")
            if event.key == key:
                self.velocity_y += 1
            key = self.settings_manager.get_key_binding("down")
            if event.key == key:
                self.velocity_y -= 1
            key = self.settings_manager.get_key_binding("left")
            if event.key == key:
                self.velocity_x += 1
            key = self.settings_manager.get_key_binding("right")
            if event.key == key:
                self.velocity_x -= 1

class MetroidvaniaGame:
    """Main game class with menu, settings and gameplay."""
    
    def __init__(self):
        pygame.init()
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        self.settings_manager.load_settings()
        
        # Initialize screen
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Metroidvania Game")
        
        # Game state
        self.game_state = GameState.MENU
        
        # Initialize components
        self.menu = Menu(self.screen, self.settings_manager)
        self.settings_window = SettingsWindow(self.screen, self.settings_manager)
        self.key_settings_window = KeySettingsWindow(self.screen, self.settings_manager)
        self.player = GamePlayer(self.screen, self.settings_manager)
        
        # FPS handling
        self.clock = pygame.time.Clock()
        self.dt = 0
        
    def run(self):
        """Main game loop."""
        running = True
        
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # Handle input based on current state
                if self.game_state == GameState.MENU:
                    result = self.menu.handle_input(event)
                    if result is not None:
                        if result == 0:  # Start Game
                            self.game_state = GameState.GAMEPLAY
                        elif result == 1:  # Settings
                            self.game_state = GameState.SETTINGS
                        elif result == 2:  # Exit
                            running = False
                
                elif self.game_state == GameState.SETTINGS:
                    result = self.settings_window.handle_input(event)
                    if result == "back":
                        self.game_state = GameState.MENU
                    elif result is not None and result != "back":
                        # Handle key change mode
                        if self.settings_window.key_change_mode:
                            self.settings_window.handle_key_input(event)
                
                elif self.game_state == GameState.GAMEPLAY:
                    self.player.handle_input(event)
            
            # Update based on current state
            if self.game_state == GameState.MENU:
                self.menu.draw()
            elif self.game_state == GameState.SETTINGS:
                self.settings_window.draw()
            elif self.game_state == GameState.GAMEPLAY:
                self.player.update(self.dt)
                self.player.draw()
                
                # Draw FPS counter
                fps_text = self.player.font.render("FPS: " + str(int(1/self.dt)), True, (255, 255, 255))
                self.screen.blit(fps_text, (10, 10))
            
            # Update FPS and dt
            self.dt = self.clock.tick(self.settings_manager.get_fps()) / 1000.0
            
            pygame.display.flip()
        
        # Save settings before exit
        self.settings_manager.save_settings()
        pygame.quit()

# Main execution
if __name__ == "__main__":
    game = MetroidvaniaGame()
    game.run()
