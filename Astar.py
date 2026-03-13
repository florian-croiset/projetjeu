import pygame
import random
import math
from collections import deque

# Initialisation de Pygame
pygame.init()

# Constantes
WIDTH, HEIGHT = 800, 600
GRID_SIZE = 20
GRID_WIDTH = WIDTH // GRID_SIZE
GRID_HEIGHT = HEIGHT // GRID_SIZE

# Couleurs
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GRAY = (128, 128, 128)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)

# Création de la fenêtre
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("IA avec A* - Trouver et ramasser l'objet")
clock = pygame.time.Clock()

class Node:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.g = float('inf')  # Coût depuis le départ
        self.h = 0  # Heuristique (distance vers la cible)
        self.f = float('inf')  # Coût total (g + h)
        self.parent = None
        self.walkable = True

class Game:
    def __init__(self):
        self.reset_game()
        
    def reset_game(self):
        # Création de la grille
        self.grid = [[Node(x, y) for y in range(GRID_HEIGHT)] for x in range(GRID_WIDTH)]
        
        # Position du joueur (en bas à gauche)
        self.player_pos = (0, GRID_HEIGHT - 1)
        self.grid[0][GRID_HEIGHT - 1].walkable = False
        
        # Position de l'objet à ramasser
        self.object_pos = self.generate_object_position()
        
        # Ajout d'obstacles après avoir défini player_pos et object_pos
        self.add_obstacles()
        
        # Variables pour l'IA
        self.path = []
        self.current_path_index = 0
        self.target_reached = False
        
        # Statistiques
        self.steps = 0
        self.search_time = 0
        
    def add_obstacles(self):
        # Ajout d'obstacles aléatoires
        for _ in range(GRID_WIDTH * GRID_HEIGHT // 8):
            x = random.randint(0, GRID_WIDTH - 1)
            y = random.randint(0, GRID_HEIGHT - 1)
            if (x, y) != self.player_pos and (x, y) != self.object_pos:
                self.grid[x][y].walkable = False
                
    def generate_object_position(self):
        # Génère une position aléatoire pour l'objet
        while True:
            x = random.randint(0, GRID_WIDTH - 1)
            y = random.randint(0, GRID_HEIGHT - 1)
            if self.grid[x][y].walkable and (x, y) != self.player_pos:
                return (x, y)
                
    def heuristic(self, a, b):
        # Distance de Manhattan
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
    def get_neighbors(self, node):
        neighbors = []
        x, y = node.x, node.y
        
        # Voisins (haut, bas, gauche, droite)
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                if self.grid[nx][ny].walkable:
                    neighbors.append(self.grid[nx][ny])
                    
        return neighbors
        
    def a_star_search(self, start, goal):
        # Initialisation des structures de données
        open_set = []
        closed_set = set()
        
        # Réinitialiser les coûts des nœuds
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                self.grid[x][y].g = float('inf')
                self.grid[x][y].h = 0
                self.grid[x][y].f = float('inf')
                self.grid[x][y].parent = None
                
        # Initialisation du nœud de départ
        start_node = self.grid[start[0]][start[1]]
        start_node.g = 0
        start_node.h = self.heuristic(start, goal)
        start_node.f = start_node.g + start_node.h
        
        open_set.append(start_node)
        
        # Temps de recherche
        import time
        start_time = time.time()
        
        while open_set:
            # Trouver le nœud avec le plus petit f
            current_node = min(open_set, key=lambda node: node.f)
            
            # Si on atteint la cible
            if (current_node.x, current_node.y) == goal:
                self.search_time = time.time() - start_time
                path = []
                while current_node is not None:
                    path.append((current_node.x, current_node.y))
                    current_node = current_node.parent
                return path[::-1]  # Retourner le chemin dans l'ordre correct
                
            # Déplacer le nœud actuel de open_set à closed_set
            open_set.remove(current_node)
            closed_set.add((current_node.x, current_node.y))
            
            # Explorer les voisins
            for neighbor in self.get_neighbors(current_node):
                if (neighbor.x, neighbor.y) in closed_set:
                    continue
                    
                tentative_g = current_node.g + 1
                
                if tentative_g < neighbor.g:
                    neighbor.parent = current_node
                    neighbor.g = tentative_g
                    neighbor.h = self.heuristic((neighbor.x, neighbor.y), goal)
                    neighbor.f = neighbor.g + neighbor.h
                    
                    if neighbor not in open_set:
                        open_set.append(neighbor)
                        
        return []  # Aucun chemin trouvé
        
    def update(self):
        if not self.target_reached and len(self.path) == 0:
            # Trouver le chemin avec A*
            self.path = self.a_star_search(self.player_pos, self.object_pos)
            self.current_path_index = 0
            
        elif not self.target_reached and self.current_path_index < len(self.path):
            # Déplacer le joueur vers la prochaine position du chemin
            next_pos = self.path[self.current_path_index]
            self.player_pos = next_pos
            self.current_path_index += 1
            self.steps += 1
            
            # Vérifier si l'object est atteint
            if self.player_pos == self.object_pos:
                self.target_reached = True
                
        elif self.target_reached:
            # Objet ramassé, générer un nouveau
            self.object_pos = self.generate_object_position()
            self.path = []
            self.current_path_index = 0
            self.target_reached = False
            
    def draw(self):
        screen.fill(BLACK)
        
        # Dessiner la grille
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                rect = pygame.Rect(x * GRID_SIZE, y * GRID_SIZE, GRID_SIZE, GRID_SIZE)
                if not self.grid[x][y].walkable:
                    pygame.draw.rect(screen, GRAY, rect)
                else:
                    pygame.draw.rect(screen, WHITE, rect, 1)
                    
        # Dessiner l'objet à ramasser
        obj_rect = pygame.Rect(
            self.object_pos[0] * GRID_SIZE + 2,
            self.object_pos[1] * GRID_SIZE + 2,
            GRID_SIZE - 4,
            GRID_SIZE - 4
        )
        pygame.draw.rect(screen, YELLOW, obj_rect)
        
        # Dessiner le joueur
        player_rect = pygame.Rect(
            self.player_pos[0] * GRID_SIZE + 2,
            self.player_pos[1] * GRID_SIZE + 2,
            GRID_SIZE - 4,
            GRID_SIZE - 4
        )
        pygame.draw.rect(screen, GREEN, player_rect)
        
        # Dessiner le chemin (si existant)
        if len(self.path) > 0:
            for i in range(len(self.path)):
                pos = self.path[i]
                rect = pygame.Rect(
                    pos[0] * GRID_SIZE + 4,
                    pos[1] * GRID_SIZE + 4,
                    GRID_SIZE - 8,
                    GRID_SIZE - 8
                )
                if i < self.current_path_index:
                    pygame.draw.rect(screen, ORANGE, rect)  # Chemin déjà parcouru
                else:
                    pygame.draw.rect(screen, BLUE, rect)   # Chemin à suivre
                    
        # Afficher les statistiques
        font = pygame.font.SysFont(None, 24)
        stats = [
            f"Étapes: {self.steps}",
            f"Temps de recherche: {self.search_time:.3f}s",
            f"Longueur du chemin: {len(self.path)}",
            "Objectif: Trouver et ramasser l'objet"
        ]
        
        for i, text in enumerate(stats):
            text_surface = font.render(text, True, WHITE)
            screen.blit(text_surface, (10, 10 + i * 30))
            
        # Afficher message
        if self.target_reached:
            msg = "Object ramassé ! Nouvel object en cours..."
            msg_surface = font.render(msg, True, RED)
            screen.blit(msg_surface, (WIDTH // 2 - 150, HEIGHT - 40))

# Création du jeu
game = Game()

# Boucle principale
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:  # Réinitialiser le jeu
                game.reset_game()
                
    # Mettre à jour le jeu
    game.update()
    
    # Dessiner le jeu
    game.draw()
    
    # Rafraîchir l'écran
    pygame.display.flip()
    
    # Contrôler la vitesse de la boucle
    clock.tick(10)  # Ajustez cette valeur pour contrôler la vitesse

pygame.quit()