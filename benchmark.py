#!/usr/bin/env python3
"""
Benchmark FPS autonome pour Écho.

Démarre une session de jeu locale (server + client dans le même process), pilote
un bot scripté en conditions pires-cas (beaucoup d'ennemis, échos rapprochés),
mesure les temps de frame et sort AVG / 1% low / 0.1% low FPS.

Usage :
    python3 benchmark.py                    # 60 s, headless, FPS uncapped
    python3 benchmark.py --duration 30
    python3 benchmark.py --visible          # ouvre une vraie fenêtre
    python3 benchmark.py --cap-fps          # garde la limite 60 FPS
    python3 benchmark.py --no-extra-enemies # désactive le stress ennemis
"""

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime


# ---------------------------------------------------------------------------
#  1) CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Benchmark FPS pour Écho")
parser.add_argument("--duration", type=float, default=60.0,
                    help="Durée de la mesure en secondes (défaut: 60)")
parser.add_argument("--warmup", type=float, default=2.0,
                    help="Temps de warmup ignoré au début (défaut: 2)")
parser.add_argument("--visible", action="store_true",
                    help="Ouvre une fenêtre Pygame réelle (sinon headless)")
parser.add_argument("--cap-fps", action="store_true",
                    help="Garde la limite FPS native (sinon uncapped)")
parser.add_argument("--no-extra-enemies", action="store_true",
                    help="Désactive le spawn d'ennemis supplémentaires")
parser.add_argument("--extra-enemies", type=int, default=25,
                    help="Nombre d'ennemis supplémentaires à spawn (défaut: 25)")
parser.add_argument("--seed", type=int, default=42,
                    help="Seed pour le RNG du bot (défaut: 42)")
parser.add_argument("--output", default="benchmark_results.json",
                    help="Fichier JSON d'historique (défaut: benchmark_results.json)")
args = parser.parse_args()


# ---------------------------------------------------------------------------
#  2) Environnement (à poser AVANT tout import pygame)
# ---------------------------------------------------------------------------
if not args.visible:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Empêche le module envoyer_logs de poster pendant le bench (MODE_DEV).
os.environ["BENCH_MODE"] = "1"


# ---------------------------------------------------------------------------
#  3) Patch des paramètres globaux AVANT l'import du client
# ---------------------------------------------------------------------------
import parametres  # noqa: E402

# On garde MODE_DEV=True pour que les capacités (double-saut, dash, echo_dir)
# soient auto-unlock côté serveur — sinon le bot ne peut pas les déclencher et
# le stress test est moins représentatif. La capture HTTP des logs est neutralisée
# juste en dessous.
parametres.MODE_DEV = True
parametres.REVELATION = False
parametres.ASSOMBRISSEMENT = True
parametres.DISTORTION_ECHO_ACTIVE = True
if not args.cap_fps:
    parametres.FPS = 100000             # uncapped

# Neutraliser le hook HTTP de capture de logs AVANT l'import du client
# (client.py:10-11 appelle envoyer_logs.activer_capture() au top-level si MODE_DEV).
from utils import envoyer_logs as _envoyer_logs  # noqa: E402
_envoyer_logs.activer_capture = lambda *a, **kw: None
_envoyer_logs.envoyer_maintenant = lambda *a, **kw: None


# ---------------------------------------------------------------------------
#  4) Imports lourds (déclenchent pygame.init via Client.__init__)
# ---------------------------------------------------------------------------
import pygame  # noqa: E402

# Skip splash screen (3 s d'attente inutile).
import ui.splash_screen as _splash  # noqa: E402
_splash.afficher_splash_screen = lambda *a, **kw: None

# Skip tutoriel au cas où il s'afficherait.
import ui.tutoriel as _tuto  # noqa: E402
class _NoTuto:
    def __init__(self, *a, **kw): pass
    def lancer(self): pass
_tuto.Tutoriel = _NoTuto

# Désactive la musique (sinon le mixer dummy peut spam des warnings).
import utils.music as _music  # noqa: E402
for fn in ("demarrer", "pause", "reprendre", "jouer_sfx",
           "torche_boucle_start", "torche_boucle_stop", "init"):
    if hasattr(_music, fn):
        setattr(_music, fn, lambda *a, **kw: None)

from reseau import serveur as _serveur_mod  # noqa: E402
from core.ennemi import Ennemi  # noqa: E402


# ---------------------------------------------------------------------------
#  5) Stress : ajouter des ennemis près du spawn joueur
# ---------------------------------------------------------------------------
EXTRA_ENEMIES_ENABLED = not args.no_extra_enemies
N_EXTRA = args.extra_enemies

_original_creer_ennemis = _serveur_mod.Serveur.creer_ennemis

def _stress_creer_ennemis(self):
    _original_creer_ennemis(self)
    if not EXTRA_ENEMIES_ENABLED:
        return
    base_x, base_y = 1024, 384  # spawn joueur (start checkpoint "32_12")
    next_id = (max(self.ennemis.keys()) + 1) if self.ennemis else 0
    rng = random.Random(args.seed)
    # Mix : 60 % pv=2 (traqueurs/gardes — déclenchent A*), 40 % pv=3 (tanky).
    for i in range(N_EXTRA):
        pv = 2 if rng.random() < 0.6 else 3
        # Dispersion en arc autour du spawn pour éviter les chevauchements.
        dx = rng.randint(-200, 200)
        dy = rng.randint(-50, 50)
        x = base_x + dx
        y = base_y + dy
        self.ennemis[next_id] = Ennemi(x=x, y=y, id=next_id, pv_max=pv)
        next_id += 1
    print(f"[BENCH] {len(self.ennemis)} ennemis spawnés "
          f"({N_EXTRA} ajoutés par le bench)")

_serveur_mod.Serveur.creer_ennemis = _stress_creer_ennemis


# ---------------------------------------------------------------------------
#  6) Bot scripté : remplace gerer_evenements_jeu
# ---------------------------------------------------------------------------
from client import Client  # noqa: E402

_bot_rng = random.Random(args.seed)
_bot_state = {
    "t_start": None,
    "direction": 1,        # 1=droite, -1=gauche
    "next_flip": 1.5,
    "next_jump": 0.7,
    "next_attack": 0.3,
    "next_dash": 0.6,
    "next_echo": 0.0,      # cast immédiatement au début
    "next_echo_dir": 1.0,
    "next_interagir": 5.0,
    "next_torche": 10.0,
}

# Intervalles : juste au-dessus des cooldowns pour saturer.
_INT_FLIP = 1.5
_INT_JUMP = 1.9
_INT_ATTACK = 0.85           # cooldown attaque 800ms
_INT_DASH = 1.2              # cooldown dash 600ms (mais 1 use en l'air)
_INT_ECHO = 2.6              # cooldown 2500ms → forcé à chaque opportunité
_INT_ECHO_DIR = 4.1          # cooldown 4000ms
_INT_INTERAGIR = 8.0
_INT_TORCHE = 12.0


def _push_distortion(client, rayon_max, duree_ms):
    """Réplique le push de _distortions_echo fait par le gerer_evenements_jeu
    original (boucle_jeu.py:189-223) — sans lui, la ripple visuelle de l'écho
    n'est jamais dessinée."""
    if not parametres.DISTORTION_ECHO_ACTIVE:
        return
    joueur = client.joueurs_locaux.get(client.mon_id)
    if joueur is None:
        return
    if not hasattr(client, "_distortions_echo"):
        client._distortions_echo = []
    client._distortions_echo.append({
        "start_ms":  pygame.time.get_ticks(),
        "wx":        joueur.rect.centerx,
        "wy":        joueur.rect.centery,
        "rayon_max": rayon_max,
        "duree_ms":  duree_ms,
    })


def _bot_gerer_evenements_jeu(self):
    # Indispensable : vider la queue SDL sinon l'OS finit par tuer le process.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            self.running = False

    commandes = {
        "clavier": {"gauche": False, "droite": False,
                    "saut": False, "attaque": False, "dash": False},
        "echo": False,
        "echo_dir": False,
        "toggle_torche": False,
        "interagir": False,
    }

    now = time.perf_counter()
    if _bot_state["t_start"] is None:
        _bot_state["t_start"] = now
    t = now - _bot_state["t_start"]

    # Mouvement continu : la direction courante est tenue (key-held).
    if _bot_state["direction"] > 0:
        commandes["clavier"]["droite"] = True
    else:
        commandes["clavier"]["gauche"] = True

    if t >= _bot_state["next_flip"]:
        _bot_state["direction"] *= -1
        _bot_state["next_flip"] = t + _INT_FLIP + _bot_rng.uniform(-0.2, 0.4)

    if t >= _bot_state["next_jump"]:
        commandes["clavier"]["saut"] = True
        _bot_state["next_jump"] = t + _INT_JUMP + _bot_rng.uniform(-0.3, 0.3)

    if t >= _bot_state["next_attack"]:
        commandes["clavier"]["attaque"] = True
        _bot_state["next_attack"] = t + _INT_ATTACK + _bot_rng.uniform(-0.1, 0.2)

    if t >= _bot_state["next_dash"]:
        commandes["clavier"]["dash"] = True
        _bot_state["next_dash"] = t + _INT_DASH + _bot_rng.uniform(-0.1, 0.4)

    if t >= _bot_state["next_echo"]:
        commandes["echo"] = True
        _push_distortion(self,
                         parametres.PORTEE_ECHO,
                         parametres.ECHO_DUREE_REVEAL)
        _bot_state["next_echo"] = t + _INT_ECHO

    if t >= _bot_state["next_echo_dir"]:
        commandes["echo_dir"] = True
        _push_distortion(self,
                         parametres.PORTEE_ECHO_DIR,
                         int(parametres.PORTEE_ECHO_DIR / parametres.PORTEE_ECHO
                             * parametres.ECHO_DUREE_REVEAL))
        _bot_state["next_echo_dir"] = t + _INT_ECHO_DIR

    if t >= _bot_state["next_interagir"]:
        commandes["interagir"] = True
        _bot_state["next_interagir"] = t + _INT_INTERAGIR

    if t >= _bot_state["next_torche"]:
        commandes["toggle_torche"] = True
        _bot_state["next_torche"] = t + _INT_TORCHE

    return commandes


Client.gerer_evenements_jeu = _bot_gerer_evenements_jeu


# ---------------------------------------------------------------------------
#  7) Hook de mesure : wrapper pygame.display.flip
# ---------------------------------------------------------------------------
frame_times: list[float] = []
_bench_state = {
    "bench_start": None,
    "done": False,
    "client": None,
}

_original_flip = pygame.display.flip

def _measured_flip(*a, **kw):
    res = _original_flip(*a, **kw)
    now = time.perf_counter()
    if _bench_state["bench_start"] is None:
        _bench_state["bench_start"] = now
    elapsed = now - _bench_state["bench_start"]
    if elapsed >= args.warmup:
        frame_times.append(now)
    if elapsed >= args.warmup + args.duration and not _bench_state["done"]:
        _bench_state["done"] = True
        client = _bench_state["client"]
        if client is not None:
            client.running = False
            client.etat_jeu = "MENU_PRINCIPAL"
    return res

pygame.display.flip = _measured_flip


# ---------------------------------------------------------------------------
#  8) Lancement de la session
# ---------------------------------------------------------------------------
def _git_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        commit = None
    try:
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL, text=True).strip())
    except Exception:
        dirty = None
    return commit, dirty


def _compute_stats():
    if len(frame_times) < 10:
        return None
    deltas = [frame_times[i+1] - frame_times[i]
              for i in range(len(frame_times) - 1)]
    deltas_sorted = sorted(deltas)
    n = len(deltas)
    total = sum(deltas)
    avg_fps = n / total if total > 0 else 0.0

    # 1% low / 0.1% low = moyenne des frames les plus lentes (convention CapFrameX).
    k1 = max(1, n // 100)
    k01 = max(1, n // 1000)
    slowest_1pct = deltas_sorted[-k1:]
    slowest_01pct = deltas_sorted[-k01:]
    low_1 = 1.0 / (sum(slowest_1pct) / len(slowest_1pct))
    low_01 = 1.0 / (sum(slowest_01pct) / len(slowest_01pct))

    p99_idx = max(0, int(n * 0.99) - 1)
    p999_idx = max(0, int(n * 0.999) - 1)

    return {
        "frames": n,
        "duration_measured_s": total,
        "avg_fps": avg_fps,
        "low_1pct_fps": low_1,
        "low_01pct_fps": low_01,
        "frame_time_ms": {
            "avg": (total / n) * 1000.0,
            "p99": deltas_sorted[p99_idx] * 1000.0,
            "p999": deltas_sorted[p999_idx] * 1000.0,
            "max": deltas_sorted[-1] * 1000.0,
        },
    }


def _print_report(stats):
    mode = "headless" if not args.visible else "windowed"
    cap = f"capped @ {parametres.FPS}" if args.cap_fps else "uncapped"
    print()
    print(f"=== Bench Écho — {args.duration:.0f}s, {mode}, FPS {cap} ===")
    if stats is None:
        print("PAS ASSEZ DE FRAMES MESURÉES — le bench n'a pas tourné assez longtemps")
        return
    print(f"Frames mesurées : {stats['frames']}")
    print(f"Durée effective : {stats['duration_measured_s']:.2f} s")
    print(f"Avg FPS         : {stats['avg_fps']:7.1f}")
    print(f"1% low FPS      : {stats['low_1pct_fps']:7.1f}")
    print(f"0.1% low FPS    : {stats['low_01pct_fps']:7.1f}")
    ft = stats["frame_time_ms"]
    print(f"Frame time avg  : {ft['avg']:6.2f} ms")
    print(f"Frame time p99  : {ft['p99']:6.2f} ms")
    print(f"Frame time p999 : {ft['p999']:6.2f} ms")
    print(f"Frame time max  : {ft['max']:6.2f} ms")


def _append_json(stats):
    if stats is None:
        return
    commit, dirty = _git_info()
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_commit": commit,
        "git_dirty": dirty,
        "duration_s": args.duration,
        "warmup_s": args.warmup,
        "frames": stats["frames"],
        "avg_fps": round(stats["avg_fps"], 2),
        "low_1pct_fps": round(stats["low_1pct_fps"], 2),
        "low_01pct_fps": round(stats["low_01pct_fps"], 2),
        "frame_time_ms": {k: round(v, 3) for k, v in stats["frame_time_ms"].items()},
        "config": {
            "headless": not args.visible,
            "fps_cap": parametres.FPS if args.cap_fps else None,
            "extra_enemies": N_EXTRA if EXTRA_ENEMIES_ENABLED else 0,
            "seed": args.seed,
        },
    }
    path = args.output
    history = []
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(entry)
    with open(path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"\nRésultat ajouté à {path} (entrée #{len(history)})")


def main():
    print(f"[BENCH] Démarrage — duration={args.duration}s warmup={args.warmup}s "
          f"headless={not args.visible} cap={args.cap_fps} "
          f"extra_enemies={N_EXTRA if EXTRA_ENEMIES_ENABLED else 0}")
    client = Client()
    _bench_state["client"] = client

    # Watchdog : si le bench dépasse largement la durée prévue (mauvais cleanup,
    # blocage thread), on force la sortie.
    def _watchdog():
        time.sleep(args.warmup + args.duration + 30)
        if not _bench_state["done"]:
            print("[BENCH] Watchdog timeout — sortie forcée")
            os._exit(2)
    threading.Thread(target=_watchdog, daemon=True).start()

    # Lance une partie locale (slot 1 → "slot_1.json"), nouvelle partie pour
    # un état déterministe (vis_map vide, pas d'améliorations).
    client.lancer_partie_locale(id_slot=1, est_nouvelle_partie=True)
    if client.etat_jeu != "EN_JEU":
        print("[BENCH] ÉCHEC : la partie n'a pas pu démarrer")
        sys.exit(1)
    client.etat_jeu_interne = "JEU"

    # Boucle de jeu (l'arrêt est piloté par notre wrapper flip()).
    try:
        client.boucle_jeu_reseau()
    except SystemExit:
        pass
    except Exception as e:
        print(f"[BENCH] Exception pendant la boucle : {e}")

    # Cleanup minimal du serveur (le thread est daemon donc il mourra avec
    # le process, mais on libère le socket pour les runs successifs).
    srv = getattr(client, "_serveur_instance", None)
    if srv is not None:
        try:
            srv.actif = False
        except Exception:
            pass

    stats = _compute_stats()
    _print_report(stats)
    _append_json(stats)


if __name__ == "__main__":
    main()
    # pygame.quit() peut bloquer sur le dummy driver — on sort sec.
    os._exit(0)
