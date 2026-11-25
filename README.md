# Écho

**Jeu d'action-plateforme 2D coopératif — Projet étudiant Cycle Préparatoire S1 & S2**

*Développé par la team Nightberry*

---

## Table des matières

- [Présentation](#présentation)
- [Équipe](#équipe)
- [Installation et lancement](#installation-et-lancement)
- [Contrôles](#contrôles)
- [Mécaniques de jeu](#mécaniques-de-jeu)
- [Architecture technique](#architecture-technique)
- [Système de sauvegarde](#système-de-sauvegarde)
- [Technologies](#technologies)

---

## Présentation

**Écho** est un jeu d'action-plateforme 2D coopératif en Python/Pygame où les joueurs ne perçoivent leur environnement que par **écholocalisation** (raycasting). Plongé dans l'obscurité totale, le joueur émet des échos sonores qui révèlent progressivement et définitivement la carte autour de lui.

Le jeu s'inspire du genre **Metroidvania** (progression par capacités débloquables ouvrant de nouvelles zones) et de **Dark Souls** (système d'âmes perdues à la mort). Jusqu'à 3 joueurs peuvent coopérer via une architecture client-serveur TCP.

### Fonctionnalités principales

- **Écholocalisation** : vision uniquement par rayons — radiale (360°) ou directionnelle (cône ±25°, débloquable)
- **Multijoueur coopératif** : jusqu'à 3 joueurs, LAN ou WAN via serveur relais
- **Progression Metroidvania** : double saut, dash, écho directionnel débloquables
- **Système d'âmes** : à la mort, une âme perdue contenant votre argent apparaît sur place et peut être récupérée
- **Boss** : Demon Slime avec salle dédiée
- **3 emplacements de sauvegarde** persistants avec checkpoints

---

## Équipe

| Membre | Contributions |
|--------|--------------|
| **Amaury Giraud--Laforet** | Chef de projet, IA ennemis, objets |
| **Florian Croiset** | Menus, site web, musique |
| **Eric Sahakian** | Level design, graphismes |
| **Gaspard Sapin** | Déplacements, mécaniques de jeu, boss |
| **Jules Cohen** | Lore, réseau, jouabilité |

Site web du projet : [florian-croiset.github.io/jeusite](https://florian-croiset.github.io/jeusite/)

---

## Installation et lancement

### Prérequis

- Python 3.10+
- Pygame 2.1+, NumPy 1.24+

### Installation

```bash
git clone https://github.com/florian-croiset/projetjeu
cd projetjeu
pip install -r requirements.txt
```

### Lancer le jeu

```bash
python3 main.py
# ou
make run
```

### Héberger une partie multijoueur

Depuis le menu principal → **Héberger** → choisir un emplacement de sauvegarde. Le serveur démarre automatiquement dans le même processus. Les adresses IP à communiquer aux autres joueurs (et le code de salle si un relais est configuré) s'affichent dans le **menu pause**.

Pour un serveur sans fenêtre (machine dédiée) :

```bash
python3 -m net.dedicated --slot 0          # --new pour une nouvelle partie
```

### Rejoindre une partie

Deux modes dans le menu **Rejoindre** :

1. **IP directe** — entrer l'IP de l'hôte (même réseau local, ou VPN type Tailscale / Hamachi). Ports à ouvrir côté hôte : `5555/TCP` et `5556/UDP`. Si l'UDP est bloqué, le jeu bascule automatiquement sur le TCP.
2. **Code de salle** — entrer le code à 6 lettres donné par l'hôte (nécessite un serveur relais, voir ci-dessous ; la partie reste en TCP).

### Serveur relais (WAN sans redirection de port)

```bash
python3 -m net.relay_server          # port 7777 par défaut
python3 -m net.relay_server 8888     # port personnalisé
```

Renseigner `RELAY_HOST` / `RELAY_PORT` dans `settings.py` (hôte **et** joueurs).

---

## Contrôles

| Action | Touche par défaut |
|--------|------------------|
| Se déplacer | Q / D |
| Sauter / Double saut | Espace |
| Dash | C |
| Écho radial | E |
| Attaque | K |
| Pause | Échap |

Les touches sont reconfigurables dans le menu Paramètres (fichier `user_settings.json`).

---

## Mécaniques de jeu

### Écholocalisation

| Mode | Portée | Cooldown | Angle | Condition |
|------|--------|----------|-------|-----------|
| Écho radial | 150 px | 2,5 s | 360° | Disponible dès le début |
| Écho directionnel | 300 px | 4 s | Cône ±25° | Débloquable (orbe) |

Les rayons sont lancés pixel par pixel depuis le joueur. Les tuiles touchées sont révélées **définitivement** dans la `vis_map` sauvegardée. Les torches proches fournissent un halo de visibilité passif.

### Capacités débloquables

Chaque capacité est obtenue en récupérant une **orbe** (objet interactif sur la carte).

- **Double saut** : second saut en l'air (force 10 vs 13 pour le saut normal)
- **Dash** : propulsion de 4 tuiles (128 px) en 150 ms, cooldown 600 ms, 1 utilisation max en l'air
- **Écho directionnel** : voir tableau ci-dessus

### Combat

- **Attaque de mêlée** : portée 40 px, cooldown 600 ms
- **Ennemis** : patrouille, détection du vide, feedback visuel à l'impact
- **Boss Demon Slime** : salle dédiée avec déclenchement de combat

### Système d'âmes perdues (inspiration Dark Souls)

1. À la mort, une **âme perdue** apparaît à l'endroit du décès avec tout votre argent
2. Le joueur réapparaît au dernier checkpoint sans argent
3. Récupérer l'âme en l'attaquant restaure l'argent
4. Mourir une seconde fois sans l'avoir récupérée la fait disparaître définitivement

### Objets du monde

| Objet | Rôle |
|-------|------|
| `AbilityOrb` | Débloque une capacité au contact |
| `Door` | Porte interactive (nécessite une clé) |
| `KeyItem` | Ramassable, ouvre une porte |
| `LostSoul` | Loot de l'argent du joueur à sa mort |
| `LootSoul` | Loot des ennemis vaincus |

---

## Architecture technique

Le code (identifiants, commentaires, journaux) est en anglais. Documentation détaillée :

- **[CLAUDE.md](CLAUDE.md)** — architecture, modules, commandes, conventions
- **[docs/NETWORK.md](docs/NETWORK.md)** — protocole réseau (TCP + UDP), prédiction client, sécurité
- **[docs/BUILD.md](docs/BUILD.md)** — compilation d'un exécutable (PyInstaller)

En résumé :

```
main.py → Client (client/app.py)
            ├─ MenusMixin / HudMixin        ui/
            ├─ GameLoopMixin                client/game_loop.py  entrées, ticks de prédiction, rendu
            ├─ ClientStateMixin             client/state.py      applique les données serveur
            └─ ClientConnectionMixin        client/connection.py rejoindre / héberger

net/server.py  → Server : sockets + boucle 60 Hz        (thread de jeu unique)
core/world.py  → World  : toute la simulation (sans réseau, testable)
```

- Le **serveur est autoritaire** ; le client prédit ses propres déplacements (même code physique) et se corrige à la réception des snapshots.
- Réseau : TCP (poignée de main, repli) + UDP (jeu en temps réel). Aucun `pickle` n'est utilisé sur le réseau.
- Tests : `make test` (pytest). Benchmark serveur : `make bench`.

### Système d'écholocalisation (`core/game_map.py`)

Les rayons sont lancés par DDA depuis la position du joueur ; les tuiles touchées sont stockées dans la `vis_map` (sauvegardée, compressée). La surface de carte pré-calculée n'est reconstruite que lorsque la `vis_map` change, et la caméra applique un masque de halo (`ui/camera.py` → `create_mask_halo`).

### Format de carte

Fichier TMX (`assets/MapS2.tmx`) lu par `core/game_map.py`. Les couches `Wall.1` et `Sol.1` génèrent des tuiles solides ; le reste est vide. Taille de tuile : **32×32 px**, carte de 100×70 tuiles. L'éditeur de niveaux : `python3 tools/level_editor.py`.

## Optimisations par rapport à l'ancienne version

Comparaison avec le code d'avant la refonte (sauvegardé à part). **Mesuré** = relevé sur la même machine avec le même scénario ; **calculé** = déduit du format ou du fonctionnement, sans mesure réelle (le réseau réel n'a pas été simulé).

| Domaine | Avant | Après | Gain | Statut |
|---------|-------|-------|------|--------|
| FPS moyen (client + serveur, 44 ennemis, bot qui joue, sans limite de FPS, sans fenêtre) | 19 à 21 FPS | 111 à 113 FPS | ≈ **×5,5** | mesuré (2 essais chacun) |
| FPS « 1 % bas » (pires images) | 2,6 à 3,0 FPS | 26 FPS | ≈ **×9** | mesuré |
| Temps moyen d'une image | 48 à 52 ms | 9 ms | **−82 %** | mesuré |
| Coût d'un tick serveur (simulation + sérialisation, 2 joueurs, 59 ennemis) | non mesurable séparément | 0,5 à 0,9 ms sur 16,7 ms disponibles (3 à 6 %) | — | mesuré (`tools/benchmark.py`) |
| Taille d'un snapshot (2 joueurs, 44 ennemis) | 547 octets | 286 octets | **−48 %** (et il contient en plus l'état de physique du joueur pour la correction) | calculé / mesuré |
| Débit descendant par joueur (snapshots à 60 Hz) | ≈ 33 Ko/s | ≈ 17 Ko/s | ≈ **−48 %** | calculé |
| États du monde (âmes, portes, ennemis…) | renvoyés en entier à 10 Hz | envoyés seulement quand ils changent | proche de 0 quand rien ne bouge | conception |
| Ennemis envoyés | tous | seulement ceux à moins de 900 px | selon la position | conception |
| Délai entre l'appui sur une touche et le mouvement du joueur local | durée d'un aller-retour réseau (≈ 50 ms pour 40 ms de ping, ≈ 110 ms pour 100 ms) + attente du tick serveur | une image (≤ 16 ms), quel que soit le ping | de ≈ 50-110 ms à ≈ 0 ms | calculé |
| Délai d'affichage des joueurs et ennemis distants | 100 ms fixes | 60 ms, augmenté automatiquement si la connexion est instable (max 200 ms) | jusqu'à −40 ms | conception |
| Fichier de sauvegarde (votre ancienne sauvegarde 1) | 140 943 octets | 1 329 octets | **−99 %** (÷ 106) | mesuré |
| Écriture de la sauvegarde | écriture directe dans le fichier (fichier corrompu si le jeu plante pendant l'écriture) ; la partie bloque le jeu | fichier temporaire puis remplacement atomique, dans un thread séparé | plus de corruption, plus d'à-coups | conception |
| Sécurité | exécution de code à distance possible (`pickle`) | format borné, testé avec des données aléatoires | — | testé |
| Jeu via VPN (Hamachi, Tailscale) | impossible (le serveur n'écoutait que l'IP du réseau local) | le serveur écoute sur toutes les interfaces | — | corrigé |
| Tests automatiques | 0 | 82 | — | mesuré |
| Code | 58 fichiers, ≈ 17 000 lignes ; boucle de jeu 1 521 lignes, serveur 1 277 lignes | 84 fichiers, ≈ 18 600 lignes (dont ≈ 1 200 de tests et d'outils) ; boucle de jeu 720 lignes, serveur 521 lignes + simulation 811 lignes | découpage et lisibilité, pas de réduction du volume | mesuré |

Notes sur les mesures :

- Scénario identique des deux côtés : session locale (serveur et client dans le même processus), pilote automatique (marche, saut, attaque, dash, écho), 25 ennemis ajoutés autour du point d'apparition, images non limitées, pilote vidéo « dummy » (pas d'affichage réel).
- Les FPS réels dans une fenêtre dépendent de la carte graphique et de l'écran ; le gain relatif devrait rester du même ordre, mais seule la mesure `--visible` sur votre machine le confirmerait.
- Les pires images restent à ≈ 30 ms (rayons de l'écho) : c'est le prochain point à optimiser.
- Reproduire : `python tools/fps_benchmark.py` (client complet) et `python tools/benchmark.py` (simulation serveur seule).

## Système de sauvegarde

Trois emplacements `slot_1.json` … `slot_3.json` (dossier du projet, ou `%LOCALAPPDATA%\Echo` / `~/.local/share/Echo` pour un exécutable). Écriture atomique ; les anciens fichiers (clés françaises, `vis_map` en liste) sont migrés automatiquement à la lecture.

```json
{
  "version": 2,
  "id_last_checkpoint": "42_22",
  "vis_map": {"w": 100, "h": 70, "bits": "<base64>"},
  "items": [],
  "money": 18,
  "upgrades": {"double_jump": true, "dash": false, "echo_dir": false}
}
```

Les réglages utilisateur sont dans `user_settings.json` (l'ancien `parametres.json` est migré au premier lancement).

## Technologies

| Technologie | Usage |
|-------------|-------|
| **Python 3.10+** | Langage principal |
| **Pygame 2.1+** | Rendu 2D, événements, boucle de jeu |
| **NumPy** | Génération du masque halo (caméra) |
| **socket / struct / zlib** | Réseau TCP + UDP (bibliothèque standard) |
| **json** | Sauvegardes et configuration |
| **threading** | Serveur, relais, pathfinding |
| **pytest / ruff** | Tests et analyse statique (développement) |
| **Tiled Map Editor** | Création de la carte (`assets/MapS2.tmx`) |

### Flags de debug (`settings.py`)

| Flag | Effet |
|------|-------|
| `DEV_MODE = True` | Compteur FPS, overlay debug, toutes les capacités débloquées |
| `REVEAL_ALL = True` | Révèle toute la carte (bypass écholocalisation) |
| `DARKNESS_ENABLED = False` | Désactive l'obscurité / le halo |
| `USE_UDP = False` | Force le transport TCP |

---

*Projet réalisé dans le cadre du Cycle Préparatoire — Année académique 2025-2026*  
*Dépôt GitHub : [florian-croiset/projetjeu](https://github.com/florian-croiset/projetjeu)*
