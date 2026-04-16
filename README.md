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
- [Structure du projet](#structure-du-projet)
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

- Python 3.8+
- Pygame 2.1+, NumPy 2.4+

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
make all
```

### Héberger une partie multijoueur

Depuis le menu principal → **Héberger** → choisir un emplacement de sauvegarde. Le serveur démarre automatiquement dans un thread séparé. L'IP locale s'affiche pour que d'autres joueurs se connectent.

### Rejoindre une partie

Deux modes disponibles dans le menu **Rejoindre** :

1. **IP directe** — entrer l'IP de l'hôte (même LAN, ou VPN type Tailscale/Hamachi + port `5555/TCP` ouvert)
2. **Code de salle** — l'hôte partage un code à 6 caractères via un serveur relais (WAN sans redirection de port)

### Serveur relais (WAN sans NAT)

```bash
python3 -m reseau.relay_server        # port 7777 par défaut
python3 -m reseau.relay_server 8888   # port personnalisé
```

Configurer `RELAY_HOST` / `RELAY_PORT` dans `parametres.py`.

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

Les touches sont reconfigurables dans `parametres.json` (menu Paramètres en jeu).

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
| `OrbeCapacite` | Débloque une capacité au contact |
| `Porte` | Porte interactive (nécessite une clé) |
| `Cle` | Ramassable, ouvre une porte |
| `AmePerdue` | Loot de l'argent du joueur à sa mort |
| `AmeLoot` | Loot des ennemis vaincus |

---

## Architecture technique

L'autorité est séparée : **le serveur possède toute la logique de jeu** (physique, IA, combats, collisions) et **le client possède le rendu, les inputs et l'affichage**.

### Serveur (`reseau/serveur.py`)

Tourne dans un thread séparé au moment de l'hébergement.

- Physique joueurs : gravité (0,6 u/frame), AABB, mouvement (5 px/frame), saut (force 13), dash
- IA ennemis : patrouille, détection du vide, respawn timers
- Résolution de combats : mêlée, boss
- Objets : portes, orbes, clés, âmes, torches
- Détection des checkpoints et sauvegarde automatique
- Diffusion de l'état à tous les clients à **60 Hz**

### Client (`main.py` → `client.py`)

`Client` est composé de trois mixins :

| Mixin | Fichier | Rôle |
|-------|---------|------|
| `BoucleJeuMixin` | `boucle_jeu.py` | Boucle de jeu, envoi inputs, réception état serveur, rendu |
| `MenusMixin` | `ui/menus.py` | Tous les écrans de menu |
| `HudMixin` | `ui/hud.py` | HUD en jeu (barre de vie, mort/respawn, boss) |

### Protocole réseau

- **Transport** : TCP sur port `5555`
- **Encodage** : préfixe 4 octets (big-endian, longueur) + objet Python sérialisé avec `pickle` — voir `reseau/protocole.py` (`send_complet` / `recv_complet`)
- **Client → Serveur** : dict d'inputs (touches pressées, actions)
- **Serveur → Client** : état complet du monde (joueurs, ennemis, âmes, boss, clés, portes, orbes, cartes de visibilité)

### Système d'écholocalisation (`core/carte.py`)

```python
for i in range(NB_RAYONS_ECHO):          # 360 rayons
    angle = (i / NB_RAYONS_ECHO) * 2 * pi
    for dist in range(1, PORTEE_ECHO):   # 150 px
        x = cx + dist * cos(angle)
        y = cy + dist * sin(angle)
        # → révèle la tuile, arrêt sur mur
```

La surface de carte pré-baked (`_carte_prebake`) n'est reconstruite que lorsque `vis_map` change. La caméra applique un masque halo (`ui/camera.py` → `creer_masque_halo`) pour l'obscurité ambiante.

---

## Structure du projet

```
projetjeu/
├── main.py                        # Point d'entrée
├── client.py                      # Classe Client (mixins)
├── boucle_jeu.py                  # BoucleJeuMixin
├── parametres.py                  # Toutes les constantes du jeu
├── parametres.json                # Configuration utilisateur (langue, touches, vidéo)
│
├── core/                          # Logique de jeu
│   ├── carte.py                   # Tilemap + raycasting écholocalisation
│   ├── joueur.py                  # Physique, combat, capacités
│   ├── ennemi.py                  # IA ennemis
│   ├── demon_slime_boss.py        # Boss principal
│   ├── boss_room.py               # Gestion de la salle boss
│   ├── ame_perdue.py              # Âme du joueur à la mort
│   ├── ame_libre.py / ame_loot.py # Âmes loot ennemis
│   ├── orbe_capacite.py           # Objets débloquant des capacités
│   ├── porte.py                   # Portes interactives
│   ├── cle.py                     # Clés
│   ├── torche.py                  # Torches (halo passif)
│   ├── map.py                     # Chargement carte JSON
│   └── astar.py                   # Pathfinding A*
│
├── reseau/                        # Réseau
│   ├── serveur.py                 # Serveur autoritaire (TCP, threadé)
│   ├── protocole.py               # send_complet / recv_complet
│   ├── relay_server.py            # Serveur relais WAN (code de salle)
│   └── relay_client.py            # Helpers côté client pour le relais
│
├── ui/                            # Interface
│   ├── menus.py                   # MenusMixin — tous les menus
│   ├── hud.py                     # HudMixin — HUD en jeu
│   ├── camera.py                  # Caméra + masque halo
│   ├── bouton.py                  # Composant bouton réutilisable
│   ├── effets_visuels.py          # Effets visuels
│   ├── splash_screen.py           # Écran de démarrage
│   └── tutoriel.py                # Tutoriel
│
├── sauvegarde/                    # Persistance
│   ├── gestion_sauvegarde.py      # Lecture/écriture slots JSON
│   ├── gestion_parametres.py      # Lecture/écriture parametres.json
│   └── points_sauvegarde.py       # ID checkpoint ↔ coordonnées
│
├── utils/                         # Utilitaires
│   ├── langue.py                  # i18n FR/EN
│   ├── music.py                   # Gestion musique
│   ├── envoyer_logs.py            # Envoi de logs
│   └── install_package.py         # Installation dépendances runtime
│
└── assets/                        # Ressources
    ├── MapS2.tmx                  # Carte Tiled (XML, couches Wall.* / Sol.*)
    ├── tileset.png                # Tileset
    ├── sprite_perso*.png          # Sprites joueurs
    ├── demon_slime.png            # Sprite boss
    ├── Torche.png                 # Sprite torche
    └── musique.mp3                # Musique d'ambiance
```

### Format de carte

Fichier TMX (`assets/MapS2.tmx`) parsé en XML par `core/carte.py`. Les couches nommées `Wall.*` et `Sol.*` génèrent des tuiles solides (type 1) ; le reste est vide (type 0). Fallback : `map.json` (grille plate). Taille de tuile : **32×32 px**.

---

## Système de sauvegarde

3 emplacements → `slot_1.json`, `slot_2.json`, `slot_3.json`. Sauvegarde automatique au contact d'un checkpoint (tuile type 3), uniquement pour l'hôte.

### Format JSON

```json
{
    "id_dernier_checkpoint": "3_21",
    "vis_map": [[true, false, ...], ...],
    "items": [],
    "ameliorations": {
        "double_saut": true,
        "dash": false,
        "echo_dir": false
    },
    "argent": 150
}
```

| Champ | Description |
|-------|-------------|
| `id_dernier_checkpoint` | Coordonnées "x_y" de la tuile checkpoint |
| `vis_map` | Grille booléenne de visibilité (même taille que la carte) |
| `ameliorations` | Capacités débloquées |
| `argent` | Âmes/argent au moment de la sauvegarde |

---

## Technologies

| Technologie | Usage |
|-------------|-------|
| **Python 3.8+** | Langage principal |
| **Pygame 2.1+** | Rendu 2D, événements, boucle de jeu |
| **NumPy 2.4+** | Génération du masque halo (caméra) |
| **socket / pickle / struct** | Réseau TCP (stdlib) |
| **json** | Sauvegardes et configuration |
| **threading** | Serveur et relais dans des threads séparés |
| **Tiled Map Editor** | Création de la carte (`assets/MapS2.tmx`) |

### Flags de debug (`parametres.py`)

| Flag | Effet |
|------|-------|
| `MODE_DEV = True` | Compteur FPS, overlay debug, capture logs |
| `REVELATION = True` | Révèle toute la carte (bypass écholocalisation) |
| `ASSOMBRISSEMENT = False` | Désactive l'obscurité / le halo |

---

*Projet réalisé dans le cadre du Cycle Préparatoire — Année académique 2024-2025*  
*Dépôt GitHub : [florian-croiset/projetjeu](https://github.com/florian-croiset/projetjeu)*
