import win32api
import win32con
import sys
import pygame
default_settings = {"Nscreen": 0}
def get_screen_refresh_rate_windows_fixed():
    if sys.platform != "win32":
        print("Cette fonction n'est compatible qu'avec Windows.")
        return 0.0
    
    try:
        # 1. Obtenir les informations du périphérique d'affichage (Moniteur principal : index 0)
        device = win32api.EnumDisplayDevices(None, 0)
        
        # 2. Obtenir les paramètres d'affichage actuels
        #    -> La constante ENUM_CURRENT_SETTINGS est dans win32con
        settings = win32api.EnumDisplaySettings(device.DeviceName, win32con.ENUM_CURRENT_SETTINGS)
        
        # 3. Le taux de rafraîchissement est dans l'attribut DisplayFrequency
        refresh_rate = settings.DisplayFrequency
        
        # win32api retourne un int pour la fréquence (ex: 60, 144)
        return float(refresh_rate)
        
    except Exception as e:
        print(f"Erreur API Windows lors de la récupération du taux de rafraîchissement : {e}")
        return 0.0
default_controls = {"up": pygame.K_z, "down": pygame.K_s, "left": pygame.K_q, "right": pygame.K_d}
default_settings = {
    # Récupérer le taux de rafraîchissement dans une variable
    "fps" : get_screen_refresh_rate_windows_fixed(),
    "vsync": True,
    "display_mode": "fullscreen",  # windowed | borderless | fullscreen
    
}
big_font = pygame.font.SysFont("arial", 60, bold=True)