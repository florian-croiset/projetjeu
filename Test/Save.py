import os
import json 
import pygame
from Gaspard import *
SAVE_FILE = "save_slots.json"
CTRL_FILE = "controls.json"
SET_FILE = "settings.json"
MAX_SLOTS = 3
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