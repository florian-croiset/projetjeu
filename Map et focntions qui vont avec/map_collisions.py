import pygame
from pytmx.util_pygame import load_pygame

class TiledMap:
    def __init__(self, filename):
        self.tmx_data = load_pygame(filename)
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight
        self.width = self.tmx_data.width * self.tile_width
        self.height = self.tmx_data.height * self.tile_height
        self.walls = self._load_collisions(["Sol.1","Wall.1"])

    def _load_collisions(self, layer_names):
        walls = []

        for layer in self.tmx_data.visible_layers:
            print(f"Debug: layer='{layer.name}', tiles={hasattr(layer, 'tiles')}")
            if hasattr(layer, "tiles") and (layer.name in layer_names):
                for x, y, tile in layer.tiles():
                    if tile:
                        rect = pygame.Rect(
                            x * self.tile_width,
                            y * self.tile_height,
                            self.tile_width,
                            self.tile_height
                        )
                        walls.append(rect)

        print("Total collisions chargées:", len(walls))
        return walls

    def draw(self, surface, camera):
        for layer in self.tmx_data.visible_layers:
            if hasattr(layer, "tiles"):
                for x, y, tile in layer.tiles():
                    if tile:
                        surface.blit(
                            tile,
                            camera.apply_pos(
                                x * self.tile_width,
                                y * self.tile_height
                            )
                        )

    def get_spawn(self, name):
        for obj in self.tmx_data.objects:
            if obj.name == name:
                return int(obj.x), int(obj.y)
        return None