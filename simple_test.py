# EchoVerse.py
import pygame
import sys
import json
import os
import math
# =============== CONFIGURATION ===============
WIDTH, HEIGHT = 960, 640
FPS = 60

WHITE = (255,255,255)
BLACK = (0,0,0)
BG_COLOR = (18,18,30)
PLAYER_COLOR = (100,200,255)
ENEMY_COLOR = (255,100,100)
SHARD_COLOR = (200,180,255)
EXIT_COLOR = (150,255,150)
HIGHLIGHT = (120,180,255)

SAVE_FILE = "save_slots.json"
CTRL_FILE = "controls.json"
MAX_SLOTS = 3

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("EchoVerse — Premier aperçu")
clock = pygame.time.Clock()

font = pygame.font.SysFont("arial", 26)
big_font = pygame.font.SysFont("arial", 60, bold=True)
small_font = pygame.font.SysFont("arial", 20)

# =============== SAUVEGARDES & COMMANDES ===============
default_controls = {"up": pygame.K_z, "down": pygame.K_s, "left": pygame.K_q, "right": pygame.K_d}

def load_saves():
    if not os.path.exists(SAVE_FILE):
        saves = [{"exists": False, "progress": 0} for _ in range(MAX_SLOTS)]
        with open(SAVE_FILE, "w") as f: json.dump(saves, f)
    else:
        with open(SAVE_FILE, "r") as f: saves = json.load(f)
    return saves

def save_saves(saves):
    with open(SAVE_FILE, "w") as f: json.dump(saves, f, indent=2)

def load_controls():
    if os.path.exists(CTRL_FILE):
        with open(CTRL_FILE, "r") as f: return json.load(f)
    else:
        return default_controls.copy()

def save_controls(c):
    with open(CTRL_FILE, "w") as f: json.dump(c, f, indent=2)

controls = load_controls()

# =============== ENTITÉS ===============
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.size = 30
        self.image = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, PLAYER_COLOR, [(0,self.size),(self.size/2,0),(self.size,self.size)])
        self.rect = self.image.get_rect(center=(x,y))
        self.speed = 4
        self.collected_shard = False
        self.discovered = False

    def update(self, keys, ctrl):
        dx = dy = 0
        if keys[ctrl["left"]]: dx = -self.speed
        if keys[ctrl["right"]]: dx = self.speed
        if keys[ctrl["up"]]: dy = -self.speed
        if keys[ctrl["down"]]: dy = self.speed
        self.rect.x += dx; self.rect.y += dy
        self.rect.clamp_ip(screen.get_rect())

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, target):
        super().__init__()
        self.size = 28
        self.image = pygame.Surface((self.size,self.size), pygame.SRCALPHA)
        pygame.draw.circle(self.image, ENEMY_COLOR, (self.size//2,self.size//2), self.size//2)
        self.rect = self.image.get_rect(center=(x,y))
        self.speed = 2.2
        self.target = target
        self.aware = False

    def update(self):
        dx = self.target.rect.centerx - self.rect.centerx
        dy = self.target.rect.centery - self.rect.centery
        dist2 = dx*dx + dy*dy
        if dist2 < 250**2:
            self.aware = True
        if self.aware:
            dist = max(1,(dist2**0.5))
            self.rect.x += int(self.speed*dx/dist)
            self.rect.y += int(self.speed*dy/dist)
        self.rect.clamp_ip(screen.get_rect())

class Shard(pygame.sprite.Sprite):
    def __init__(self,x,y):
        super().__init__()
        self.radius = 10
        self.image = pygame.Surface((self.radius*2,self.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, SHARD_COLOR, (self.radius,self.radius), self.radius)
        self.rect = self.image.get_rect(center=(x,y))
        self.pulse = 0

    def update(self):
        self.pulse = (self.pulse + 0.08) % (2*math.pi)
        s = 1 + 0.08*(1+math.sin(self.pulse))
        r = int(self.radius*s)
        self.image = pygame.Surface((r*2,r*2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, SHARD_COLOR, (r,r), r)
        self.rect = self.image.get_rect(center=self.rect.center)

class ExitZone(pygame.sprite.Sprite):
    def __init__(self,x,y,w,h): self.rect = pygame.Rect(x,y,w,h)
    def draw(self,surface): pygame.draw.rect(surface, EXIT_COLOR, self.rect, width=3)

# =============== SCÈNES DE JEU ===============
def show_text_block(lines, wait=0):
    t0 = pygame.time.get_ticks()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and (wait==0 or e.key==pygame.K_RETURN): return
        screen.fill(BG_COLOR)
        y = HEIGHT//2 - len(lines)*18
        for i,l in enumerate(lines):
            surf = font.render(l, True, WHITE)
            screen.blit(surf,(WIDTH//2-surf.get_width()//2,y+i*30))
        pygame.display.flip()
        if wait>0 and pygame.time.get_ticks()-t0>wait*1000: return
        clock.tick(FPS)

def run_level(slot_index):
    player = Player(WIDTH//4, HEIGHT//2)
    enemy = Enemy(WIDTH-120, HEIGHT//2, player)
    shard = Shard(WIDTH//2+100, HEIGHT//2-120)
    exit_zone = ExitZone(WIDTH-120, HEIGHT//2-60, 100,120)
    all_sprites = pygame.sprite.Group(player, enemy, shard)

    while True:
        keys = pygame.key.get_pressed()
        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: return "quit"
        player.update(keys, controls)
        enemy.update(); shard.update()

        if pygame.sprite.collide_rect(player, enemy):
            player.rect.center = (WIDTH//4, HEIGHT//2)
            show_text_block(["L'ombre t'a touché..."], wait=1)

        if not player.collected_shard and player.rect.colliderect(shard.rect):
            player.collected_shard = True
            all_sprites.remove(shard)
            show_text_block(["Tu as trouvé un fragment de mémoire.","Une image floue te traverse l'esprit..."], wait=2)

        if player.rect.colliderect(exit_zone.rect):
            return "true" if player.collected_shard else "base"

        screen.fill(BG_COLOR)
        exit_zone.draw(screen)
        for s in all_sprites: screen.blit(s.image, s.rect)
        hud = small_font.render(f"Fragment: {'oui' if player.collected_shard else 'non'}", True, WHITE)
        screen.blit(hud, (10,10))
        pygame.display.flip()
        clock.tick(FPS)

def base_ending(): show_text_block(["Fin de base.","Tu t'éloignes... l'écho reste incomplet."], wait=3)
def true_ending(): show_text_block(["Vraie fin.","Tu te découvres enfin..."], wait=3)

# =============== MENUS ===============
def draw_text_center(text,font,color,y):
    surf = font.render(text,True,color)
    screen.blit(surf,(WIDTH//2-surf.get_width()//2,y))

def show_message(lines):
    while True:
        screen.fill(BG_COLOR)
        for i,l in enumerate(lines):
            surf = font.render(l,True,WHITE)
            screen.blit(surf,(WIDTH//2-surf.get_width()//2,HEIGHT//2+i*40-20))
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type==pygame.KEYDOWN or e.type==pygame.QUIT: return
        clock.tick(FPS)

def control_menu():
    global controls
    actions = list(controls.keys())
    index = 0
    waiting = None
    while True:
        screen.fill(BG_COLOR)
        draw_text_center("Commandes", big_font, WHITE, 80)
        for i,a in enumerate(actions):
            color = HIGHLIGHT if i==index else WHITE
            keyname = pygame.key.name(controls[a])
            draw_text_center(f"{a.capitalize()} : {keyname}", font, color, 220+i*50)
        draw_text_center("Entrée = changer | Échap = retour", small_font, WHITE, HEIGHT-40)

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if waiting:
                if e.type==pygame.KEYDOWN:
                    controls[waiting]=e.key
                    save_controls(controls)
                    waiting=None
            else:
                if e.type==pygame.KEYDOWN:
                    if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(actions)
                    if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(actions)
                    if e.key==pygame.K_RETURN: waiting=actions[index]
                    if e.key==pygame.K_ESCAPE: return
        if waiting: draw_text_center("Appuyez sur une touche...", small_font, HIGHLIGHT, HEIGHT-80)
        pygame.display.flip(); clock.tick(FPS)

def settings_menu():
    index = 0
    options = ["Commandes","Retour"]
    while True:
        screen.fill(BG_COLOR)
        draw_text_center("Réglages", big_font, WHITE, 100)
        for i,opt in enumerate(options):
            color = HIGHLIGHT if i==index else WHITE
            draw_text_center(opt,font,color,250+i*60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(options)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(options)
                if e.key==pygame.K_RETURN:
                    if index==0: control_menu()
                    else: return
                if e.key==pygame.K_ESCAPE: return
        pygame.display.flip(); clock.tick(FPS)

def start_game(slot):
    show_text_block(["Tu te réveilles dans une pièce d'échos.","Ton nom est un trou blanc..."], wait=2)
    result = run_level(slot)
    saves = load_saves()
    if result=="true":
        true_ending()
        saves[slot]["progress"]=100
    elif result=="base":
        base_ending()
        saves[slot]["progress"]=50
    save_saves(saves)

def new_game_menu():
    saves = load_saves(); index=0
    while True:
        screen.fill(BG_COLOR)
        draw_text_center("Nouvelle Partie", big_font, WHITE, 100)
        for i,slot in enumerate(saves):
            txt = f"Slot {i+1}: {'VIDE' if not slot['exists'] else f'Progression {slot['progress']}%'}"
            color = HIGHLIGHT if i==index else WHITE
            draw_text_center(txt,font,color,240+i*60)
        draw_text_center("Entrée = jouer | Échap = retour", small_font, WHITE, HEIGHT-40)

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%MAX_SLOTS
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%MAX_SLOTS
                if e.key==pygame.K_ESCAPE: return
                if e.key==pygame.K_RETURN:
                    saves[index]={"exists":True,"progress":0}
                    save_saves(saves)
                    start_game(index); return
        pygame.display.flip(); clock.tick(FPS)

def continue_menu():
    saves = load_saves()
    available = [i for i,s in enumerate(saves) if s["exists"]]
    if not available:
        show_message(["Aucune sauvegarde disponible.","Appuyez sur une touche pour revenir."])
        return
    index=0
    while True:
        screen.fill(BG_COLOR)
        draw_text_center("Continuer", big_font, WHITE, 100)
        for i,slot in enumerate(available):
            s=saves[slot]
            color = HIGHLIGHT if i==index else WHITE
            draw_text_center(f"Slot {slot+1}: progression {s['progress']}%", font, color, 240+i*60)
        draw_text_center("Entrée = charger | Échap = retour", small_font, WHITE, HEIGHT-40)

        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(available)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(available)
                if e.key==pygame.K_ESCAPE: return
                if e.key==pygame.K_RETURN:
                    start_game(available[index]); return
        pygame.display.flip(); clock.tick(FPS)

def main_menu():
    options = ["Nouvelle Partie","Continuer","Réglages","Quitter"]
    index=0
    while True:
        screen.fill(BG_COLOR)
        draw_text_center("ECHOVERSE", big_font, WHITE, 120)
        for i,opt in enumerate(options):
            color = HIGHLIGHT if i==index else WHITE
            draw_text_center(opt,font,color,260+i*60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(options)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(options)
                if e.key==pygame.K_RETURN:
                    if index==0: new_game_menu()
                    elif index==1: continue_menu()
                    elif index==2: settings_menu()
                    elif index==3: pygame.quit(); sys.exit()
        pygame.display.flip(); clock.tick(FPS)

# =============== LANCEMENT ===============
if __name__ == "__main__":
    main_menu()
