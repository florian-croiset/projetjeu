# EchoVerse.py — Version avec paramètres vidéo complets

import install_package as ip
ip.install_package(["setuptools","pygame"])

import pygame
import sys
import json
import os

# ================= CONFIG =================
WIDTH, HEIGHT = 960, 640
DEFAULT_FPS = 60
BG_COLOR = (18,18,30)
WHITE = (255,255,255)
HIGHLIGHT = (120,180,255)

SAVE_FILE = "save_slots.json"
CTRL_FILE = "controls.json"
SET_FILE = "settings.json"
MAX_SLOTS = 3

pygame.init()

# ================= SAUVEGARDES =================
default_controls = {"up": pygame.K_z, "down": pygame.K_s, "left": pygame.K_q, "right": pygame.K_d}
default_settings = {
    "fps": 60,
    "vsync": True,
    "display_mode": "fullscreen"  # windowed | borderless | fullscreen
}

def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f: json.dump(default, f, indent=2)
        return default
    with open(file, "r") as f:
        try: return json.load(f)
        except: return default

def save_json(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=2)

def load_saves(): return load_json(SAVE_FILE, [{"exists": False, "progress": 0} for _ in range(MAX_SLOTS)])
def save_saves(saves): save_json(SAVE_FILE, saves)
def load_controls(): return load_json(CTRL_FILE, default_controls)
def save_controls(ctrls): save_json(CTRL_FILE, ctrls)
def load_settings(): return load_json(SET_FILE, default_settings)
def save_settings(s): save_json(SET_FILE, s)

controls = load_controls()
settings = load_settings()

# ================= FENÊTRE / VIDÉO =================
def apply_display_settings():
    global screen, clock
    flags = 0
    if settings["display_mode"] == "borderless":
        flags = pygame.NOFRAME
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=settings["vsync"])
    elif settings["display_mode"] == "fullscreen":
        flags = pygame.FULLSCREEN
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=settings["vsync"])
    else:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), vsync=settings["vsync"])
    clock = pygame.time.Clock()
    pygame.display.set_caption("EchoVerse — Premier aperçu")

apply_display_settings()

font = pygame.font.SysFont("arial", 26)
big_font = pygame.font.SysFont("arial", 60, bold=True)
small_font = pygame.font.SysFont("arial", 20)

# ================= ENTITÉS =================
class Player(pygame.sprite.Sprite):
    def __init__(self,x,y):
        super().__init__()
        self.size=30
        self.image=pygame.Surface((self.size,self.size),pygame.SRCALPHA)
        pygame.draw.polygon(self.image,(100,200,255),[(0,self.size),(self.size/2,0),(self.size,self.size)])
        self.rect=self.image.get_rect(center=(x,y))
        self.speed=4
        self.collected=False
    def update(self,keys,ctrl):
        dx=dy=0
        if keys[ctrl["left"]]: dx=-self.speed
        if keys[ctrl["right"]]: dx=self.speed
        if keys[ctrl["up"]]: dy=-self.speed
        if keys[ctrl["down"]]: dy=self.speed
        self.rect.x+=dx; self.rect.y+=dy
        self.rect.clamp_ip(screen.get_rect())

class Enemy(pygame.sprite.Sprite):
    def __init__(self,x,y,target):
        super().__init__()
        self.size=28
        self.image=pygame.Surface((self.size,self.size),pygame.SRCALPHA)
        pygame.draw.circle(self.image,(255,100,100),(self.size//2,self.size//2),self.size//2)
        self.rect=self.image.get_rect(center=(x,y))
        self.target=target; self.speed=2.2
    def update(self):
        dx=self.target.rect.centerx-self.rect.centerx
        dy=self.target.rect.centery-self.rect.centery
        dist=max(1,(dx*dx+dy*dy)**0.5)
        if dist<250: self.rect.x+=int(self.speed*dx/dist); self.rect.y+=int(self.speed*dy/dist)
        self.rect.clamp_ip(screen.get_rect())

class Shard(pygame.sprite.Sprite):
    def __init__(self,x,y):
        super().__init__()
        self.r=10
        self.image=pygame.Surface((self.r*2,self.r*2),pygame.SRCALPHA)
        pygame.draw.circle(self.image,(200,180,255),(self.r,self.r),self.r)
        self.rect=self.image.get_rect(center=(x,y))
        self.pulse=0
    def update(self):
        self.pulse=(self.pulse+0.08)%(2*3.1415)
        s=1+0.08*(1+pygame.math.sin(self.pulse))
        r=int(self.r*s)
        self.image=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
        pygame.draw.circle(self.image,(200,180,255),(r,r),r)
        self.rect=self.image.get_rect(center=self.rect.center)

# ================= SCÈNES =================
def show_text(lines, wait=0):
    t0=pygame.time.get_ticks()
    while True:
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and (wait==0 or e.key==pygame.K_RETURN): return
        screen.fill(BG_COLOR)
        y=HEIGHT//2-len(lines)*20
        for i,l in enumerate(lines):
            surf=font.render(l,True,WHITE)
            screen.blit(surf,(WIDTH//2-surf.get_width()//2,y+i*30))
        pygame.display.flip()
        if wait>0 and pygame.time.get_ticks()-t0>wait*1000: return
        clock.tick(settings["fps"])

def run_level(slot):
    player=Player(WIDTH//4,HEIGHT//2)
    enemy=Enemy(WIDTH-120,HEIGHT//2,player)
    shard=Shard(WIDTH//2+100,HEIGHT//2-100)
    all_sprites=pygame.sprite.Group(player,enemy,shard)
    exit_rect=pygame.Rect(WIDTH-120,HEIGHT//2-60,100,120,144,180,240,360)
    while True:
        keys=pygame.key.get_pressed()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE: return "quit"
        player.update(keys,controls); enemy.update(); shard.update()
        if pygame.sprite.collide_rect(player,enemy):
            player.rect.center=(WIDTH//4,HEIGHT//2)
            show_text(["L'ombre t'a touché..."],wait=1)
        if not player.collected and player.rect.colliderect(shard.rect):
            player.collected=True; all_sprites.remove(shard)
            show_text(["Tu as trouvé un fragment de mémoire."],wait=2)
        if player.rect.colliderect(exit_rect):
            return "true" if player.collected else "base"
        screen.fill(BG_COLOR)
        pygame.draw.rect(screen,(150,255,150),exit_rect,3)
        for s in all_sprites: screen.blit(s.image,s.rect)
        pygame.display.flip(); clock.tick(settings["fps"])

def base_end(): show_text(["Fin incomplète.","Tu t'éloignes..."],wait=3)
def true_end(): show_text(["Vraie fin.","Tu te découvres enfin..."],wait=3)

# ================= MENUS =================
def draw_center(text,font,color,y):
    surf=font.render(text,True,color)
    screen.blit(surf,(WIDTH//2-surf.get_width()//2,y))

def show_message(lines):
    while True:
        screen.fill(BG_COLOR)
        for i,l in enumerate(lines):
            surf=font.render(l,True,WHITE)
            screen.blit(surf,(WIDTH//2-surf.get_width()//2,HEIGHT//2+i*40-20))
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type==pygame.KEYDOWN or e.type==pygame.QUIT: return
        clock.tick(settings["fps"])

def control_menu():
    global controls
    actions=list(controls.keys()); index=0; waiting=None
    while True:
        screen.fill(BG_COLOR)
        draw_center("Commandes",big_font,WHITE,80)
        for i,a in enumerate(actions):
            color=HIGHLIGHT if i==index else WHITE
            keyname=pygame.key.name(controls[a])
            draw_center(f"{a.capitalize()} : {keyname}",font,color,220+i*50)
        draw_center("Entrée=changer  Échap=retour",small_font,WHITE,HEIGHT-40)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if waiting and e.type==pygame.KEYDOWN:
                controls[waiting]=e.key; save_controls(controls); waiting=None
            elif e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(actions)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(actions)
                if e.key==pygame.K_RETURN: waiting=actions[index]
                if e.key==pygame.K_ESCAPE: return
        if waiting: draw_center("Appuyez sur une touche...",small_font,HIGHLIGHT,HEIGHT-80)
        pygame.display.flip(); clock.tick(settings["fps"])

def video_menu():
    global settings
    options=["FPS","VSync","Mode d'affichage","Retour"]
    index=0
    while True:
        screen.fill(BG_COLOR)
        draw_center("Vidéo",big_font,WHITE,80)
        for i,opt in enumerate(options):
            color=HIGHLIGHT if i==index else WHITE
            value=""
            if opt=="FPS": value=str(settings["fps"])
            elif opt=="VSync": value="Activé" if settings["vsync"] else "Désactivé"
            elif opt=="Mode d'affichage":
                mode_name={"windowed":"Fenêtré","borderless":"Fenêtré plein écran","fullscreen":"Plein écran"}[settings["display_mode"]]
                value=mode_name
            draw_center(f"{opt} : {value}",font,color,220+i*60)
        draw_center("Entrée/modifier  Échap/retour",small_font,WHITE,HEIGHT-40)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(options)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(options)
                if e.key==pygame.K_ESCAPE: save_settings(settings); apply_display_settings(); return
                if e.key==pygame.K_RETURN:
                    if options[index]=="FPS":
                        settings["fps"] = 30 if settings["fps"]==60 else 60 if settings["fps"]==120 else 120
                    elif options[index]=="VSync":
                        settings["vsync"]=not settings["vsync"]
                    elif options[index]=="Mode d'affichage":
                        modes=["windowed","borderless","fullscreen"]
                        cur=modes.index(settings["display_mode"])
                        settings["display_mode"]=modes[(cur+1)%3]
                        apply_display_settings()
                    elif options[index]=="Retour":
                        save_settings(settings); apply_display_settings(); return
        pygame.display.flip(); clock.tick(settings["fps"])

def settings_menu():
    index=0; options=["Commandes","Vidéo","Retour"]
    while True:
        screen.fill(BG_COLOR)
        draw_center("Réglages",big_font,WHITE,80)
        for i,opt in enumerate(options):
            color=HIGHLIGHT if i==index else WHITE
            draw_center(opt,font,color,240+i*60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(options)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(options)
                if e.key==pygame.K_RETURN:
                    if index==0: control_menu()
                    elif index==1: video_menu()
                    else: return
                if e.key==pygame.K_ESCAPE: return
        pygame.display.flip(); clock.tick(settings["fps"])

# ================= JEU =================
def start_game(slot):
    show_text(["Tu te réveilles dans une pièce d'échos..."],wait=2)
    result=run_level(slot)
    saves=load_saves()
    if result=="true":
        true_end(); saves[slot]["progress"]=100
    elif result=="base":
        base_end(); saves[slot]["progress"]=50
    save_saves(saves)

def new_game_menu():
    saves=load_saves(); index=0
    while True:
        screen.fill(BG_COLOR)
        draw_center("Nouvelle Partie",big_font,WHITE,100)
        for i,s in enumerate(saves):
            t=f"Slot {i+1}: {'VIDE' if not s['exists'] else f'Progression {s['progress']}%'}"
            color=HIGHLIGHT if i==index else WHITE
            draw_center(t,font,color,240+i*60)
        draw_center("Entrée=jouer  Échap=retour",small_font,WHITE,HEIGHT-40)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%MAX_SLOTS
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%MAX_SLOTS
                if e.key==pygame.K_ESCAPE: return
                if e.key==pygame.K_RETURN:
                    saves[index]={"exists":True,"progress":0}; save_saves(saves)
                    start_game(index); return
        pygame.display.flip(); clock.tick(settings["fps"])

def continue_menu():
    saves=load_saves()
    avail=[i for i,s in enumerate(saves) if s["exists"]]
    if not avail: show_message(["Aucune sauvegarde.","Appuyez sur une touche."]); return
    index=0
    while True:
        screen.fill(BG_COLOR)
        draw_center("Continuer",big_font,WHITE,100)
        for i,slot in enumerate(avail):
            s=saves[slot]
            color=HIGHLIGHT if i==index else WHITE
            draw_center(f"Slot {slot+1}: {s['progress']}%",font,color,240+i*60)
        draw_center("Entrée=charger  Échap=retour",small_font,WHITE,HEIGHT-40)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.KEYDOWN:
                if e.key in [pygame.K_UP,pygame.K_z]: index=(index-1)%len(avail)
                if e.key in [pygame.K_DOWN,pygame.K_s]: index=(index+1)%len(avail)
                if e.key==pygame.K_ESCAPE: return
                if e.key==pygame.K_RETURN:
                    start_game(avail[index]); return
        pygame.display.flip(); clock.tick(settings["fps"])

def main_menu():
    index=0; options=["Nouvelle Partie","Continuer","Réglages","Quitter"]
    while True:
        screen.fill(BG_COLOR)
        draw_center("ECHOVERSE",big_font,WHITE,120)
        for i,opt in enumerate(options):
            color=HIGHLIGHT if i==index else WHITE
            draw_center(opt,font,color,260+i*60)
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
        pygame.display.flip(); clock.tick(settings["fps"])

# ================= LANCEMENT =================
if __name__ == "__main__":
    main_menu()
