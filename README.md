# Écho 🎮

**Projet de jeu vidéo multijoueur coopératif - Cycle Préparatoire S1 & S2**

---

## 📋 Table des matières

- [Présentation du projet](#présentation-du-projet)
- [Équipe de développement](#équipe-de-développement)
- [Fonctionnalités principales](#fonctionnalités-principales)
- [Architecture technique](#architecture-technique)
- [Installation et lancement](#installation-et-lancement)
- [Guide de jeu](#guide-de-jeu)
- [Structure du projet](#structure-du-projet)
- [Système de sauvegarde](#système-de-sauvegarde)
- [Technologies utilisées](#technologies-utilisées)
- [Développements futurs](#développements-futurs)
- [Crédits et remerciements](#crédits-et-remerciements)

---

## 🎯 Présentation du projet

**Écho** est un jeu d'action-plateforme 2D développé dans le cadre d'un projet étudiant de première année du cycle préparatoire. Le jeu s'inspire du genre "Metroidvania" en proposant une exploration progressive basée sur un système de vision unique : **l'écholocalisation**.

### Concept principal

Dans un monde plongé dans l'obscurité totale, le joueur ne peut voir son environnement qu'en utilisant des échos sonores. Cette mécanique centrale crée une expérience de jeu unique où l'exploration devient un défi permanent. Les joueurs doivent régulièrement émettre des échos pour révéler progressivement la carte et naviguer dans des labyrinthes complexes.

### Caractéristiques distinctives

- **Vision par écholocalisation** : Système de raycasting révélant progressivement l'environnement
- **Multijoueur coopératif** : Jusqu'à 3 joueurs peuvent explorer ensemble (architecture client-serveur)
- **Progression Metroidvania** : Déblocage de capacités (double saut, dash) ouvrant de nouvelles zones
- **Système d'âmes** : Mécanisme inspiré de Dark Souls pour la gestion de la mort
- **Sauvegarde persistante** : 3 emplacements de sauvegarde avec checkpoints

---

## 👥 Équipe de développement

Ce projet a été réalisé par une équipe de 5 étudiants :

1. **[Amaury Giraud--Laforet]** - Chef de projet, IA, Objets
2. **[Florian Croiset]** - Menu, site, Musique
3. **[Eric Sahakian]** - Level design, Graphismes
4. **[Gaspard Sapin]** - Déplacements, Mécaniques, Boss
5. **[Jules Cohen]** - Lore, Réseau, Jouabilité

### Site web du projet

Un site web compagnon a été développé pour promouvoir le jeu et présenter l'équipe.  
🔗 (https://florian-croiset.github.io/jeusite/)

---

## ✨ Fonctionnalités principales

### 🎮 Mécaniques de jeu

#### Écholocalisation
- **Cooldown** : 6 secondes entre chaque écho
- **Portée** : 250 pixels de rayon
- **Précision** : 360 rayons lancés pour une détection précise
- Les échos révèlent les murs, les checkpoints et les points d'intérêt

#### Système de combat
- **Attaque de mêlée** : Portée de 40 pixels
- **Dégâts** : 1 point par coup
- **Cooldown** : 500ms entre les attaques
- **Feedback visuel** : Hitbox affichée pendant l'attaque

#### Capacités débloquables
1. **Double Saut**
   - Force : 10 unités (légèrement moins puissant que le saut normal)
   - Permet d'atteindre des plateformes inaccessibles

2. **Dash**
   - Distance : 4 blocs (128 pixels)
   - Durée : 150ms
   - Cooldown : 600ms
   - Utilisable 1 fois en l'air avant de retoucher le sol

#### Système d'âmes perdues
Inspiré de la série Dark Souls :
- À la mort, le joueur laisse une **âme perdue** contenant tout son argent
- L'âme apparaît à l'endroit de la mort
- Le joueur peut la récupérer en l'attaquant
- Une nouvelle mort fait disparaître l'ancienne âme définitivement

### 🌐 Multijoueur

#### Architecture réseau
- **Type** : Client-Serveur via sockets TCP
- **Port** : 5555 (configurable)
- **Capacité** : 3 joueurs maximum simultanément
- **Protocole** : Sérialisation avec pickle pour l'échange de données

#### Fonctionnalités réseau
- L'hôte héberge le serveur et joue simultanément
- Les clients se connectent via l'IP locale de l'hôte
- Synchronisation en temps réel des positions, actions et états
- Cartes de visibilité individuelles par joueur
- Partage des ennemis et des âmes perdues

### 💾 Système de sauvegarde

#### Emplacements
- **3 slots** de sauvegarde indépendants
- Sauvegarde automatique aux checkpoints (tuiles jaunes de type 3)
- Stockage au format JSON pour faciliter le débogage

#### Données sauvegardées
- Position du dernier checkpoint
- Carte de visibilité révélée
- Argent collecté
- Capacités débloquées (double saut, dash)
- Items récupérés (système préparé pour extensions futures)

### 🗺️ Carte et environnement

#### Système de tilemap
- Grille de tuiles de 32×32 pixels
- Carte actuelle : 32×24 tuiles (1024×768 pixels)
- Types de tuiles :
  - `0` : Zone vide (accessible)
  - `1` : Mur (solide, visible après écho)
  - `2` : Point de repère (toujours visible, sert de guide)
  - `3` : Point de sauvegarde (checkpoint)

#### Caméra
- Système de caméra centrée sur le joueur
- Zoom configurable (défaut : 2.5×)
- Défilement fluide suivant les mouvements

---

## 🏗️ Architecture technique

### Structure modulaire

Le projet est organisé en modules Python spécialisés pour faciliter la maintenance et l'évolution :

```
metroidvania-echo/
├── client.py              # Point d'entrée client + boucle de jeu
├── serveur.py             # Logique serveur + autorité du jeu
├── joueur.py              # Classe Joueur (physique, combat, capacités)
├── ennemi.py              # Classe Ennemi (IA, patrouille, PV)
├── ame_perdue.py          # Système d'âmes perdues
├── carte.py               # Gestion tilemap et écholocalisation
├── bouton.py              # Composant UI pour les menus
├── parametres.py          # Constantes globales du jeu
├── gestion_parametres.py  # Lecture/écriture parametres.json
├── gestion_sauvegarde.py  # Lecture/écriture des slots
├── points_sauvegarde.py   # Gestion des checkpoints
├── langue.py              # Système i18n (FR/EN)
├── parametres.json        # Configuration utilisateur
├── slot_1.json            # Sauvegarde emplacement 1
├── slot_2.json            # Sauvegarde emplacement 2
├── slot_3.json            # Sauvegarde emplacement 3
└── Map.tmx                # Carte Tiled (potentiel futur)
```

### Physique et collisions

#### Gravité et mouvement
- **Gravité** : 0.6 unités/frame
- **Vitesse joueur** : 5 pixels/frame
- **Force de saut** : 13 unités
- Limitation de la vélocité verticale à 10 unités

#### Gestion des collisions
- Détection AABB (Axis-Aligned Bounding Box)
- Séparation des collisions X et Y
- Résolution immédiate pour éviter les overlaps
- Distinction entre surfaces solides et traversables

### Système de raycasting

L'écholocalisation utilise un algorithme de raycasting optimisé :

1. **Lancement des rayons** : 360 rayons équidistants depuis le joueur
2. **Marche de rayon** : Avancement progressif pixel par pixel
3. **Détection** : Arrêt au premier obstacle ou à la portée max
4. **Mise à jour** : Révélation permanente des tuiles touchées

```python
for i in range(NB_RAYONS_ECHO):  # 360 rayons
    angle = (i / NB_RAYONS_ECHO) * 2 * math.pi
    for dist in range(1, PORTEE_ECHO):  # Portée 250
        x = centre_x + dist * math.cos(angle)
        y = centre_y + dist * math.sin(angle)
        # Vérification collision et révélation
```

### Réseau et synchronisation

#### Architecture Client-Serveur

**Serveur (Autorité)**
- Gère la physique pour tous les joueurs
- Exécute l'IA des ennemis
- Détecte les collisions et les interactions
- Applique les règles du jeu
- Distribue l'état du monde à tous les clients

**Client (Affichage)**
- Capture les inputs du joueur local
- Envoie les commandes au serveur
- Reçoit l'état du monde
- Affiche le rendu graphique
- Gère l'interface utilisateur

#### Protocole de communication

**Client → Serveur** (chaque frame)
```python
{
    'clavier': {
        'gauche': bool,
        'droite': bool,
        'saut': bool,
        'attaque': bool,
        'dash': bool
    },
    'echo': bool
}
```

**Serveur → Client** (chaque frame)
```python
{
    'joueurs': [état_joueur1, état_joueur2, ...],
    'vis_map': [[bool, bool, ...], ...],
    'ennemis': [état_ennemi1, état_ennemi2, ...],
    'ames_perdues': [état_ame1, état_ame2, ...]
}
```

---

## 🚀 Installation et lancement

### Prérequis

- **Python** 3.8 ou supérieur
- **Pygame** 2.0 ou supérieur

### Installation

1. **Cloner le dépôt**
```bash
git clone [URL_DU_DEPOT]
cd metroidvania-echo
```

2. **Installer les dépendances**
```bash
pip install pygame
```

3. **Vérifier les fichiers**
```bash
# S'assurer que tous les fichiers .py sont présents
ls *.py

# Vérifier la présence de parametres.json
cat parametres.json
```

### Lancement du jeu

#### Mode Solo / Hébergement

```bash
python client.py
```

Puis dans le menu :
1. Sélectionner **"Héberger une partie"**
2. Choisir **"Nouvelle Partie"** ou **"Continuer"**
3. Sélectionner un emplacement de sauvegarde (1, 2 ou 3)
4. Le serveur démarre automatiquement
5. L'IP locale s'affiche dans la console (pour que d'autres joueurs se connectent)

#### Mode Multijoueur (Client)

1. Lancer le jeu : `python client.py`
2. Sélectionner **"Rejoindre une partie"**
3. Entrer l'IP de l'hôte (affichée dans sa console)
4. Se connecter

### Configuration

Le fichier `parametres.json` permet de personnaliser :

```json
{
    "jouabilite": {
        "langue": "fr",           // "fr" ou "en"
        "sensibilite_souris": 0.5
    },
    "video": {
        "plein_ecran": false,
        "vsync": false
    },
    "controles": {
        "gauche": "q",
        "droite": "d",
        "saut": "space",
        "echo": "e",
        "attaque": "k",
        "dash": "c"
    }
}
```

---

## 🎲 Guide de jeu

### Contrôles par défaut

| Action | Touche | Description |
|--------|--------|-------------|
| **Déplacement gauche** | Q | Se déplacer vers la gauche |
| **Déplacement droite** | D | Se déplacer vers la droite |
| **Saut** | Espace | Sauter (maintenir pour sauter plus haut) |
| **Double saut** | Espace (×2) | Second saut en l'air (après déblocage) |
| **Dash** | C | Propulsion rapide (après déblocage) |
| **Écho** | E | Révéler l'environnement (cooldown 6s) |
| **Attaque** | K | Attaque de mêlée |
| **Pause** | Échap | Mettre le jeu en pause |

### Objectifs et progression

#### Phase d'exploration
1. **Révéler la carte** : Utiliser les échos pour découvrir l'environnement
2. **Trouver les checkpoints** : Repérer les tuiles jaunes (type 3) pour sauvegarder
3. **Collecter des âmes** : Vaincre les ennemis pour gagner de l'argent (10 âmes/ennemi)

#### Système de progression
- Les **points de repère** (tuiles grises foncées) sont toujours visibles et servent de guides
- Les **checkpoints** sauvegardent automatiquement la progression
- Les **capacités** débloquées persistent entre les sessions
- La **carte révélée** est sauvegardée et reste visible

#### Gestion de la mort
1. À la mort, une **âme perdue** apparaît à votre position
2. Vous réapparaissez au dernier checkpoint **sans argent**
3. Retournez récupérer votre âme pour retrouver votre argent
4. **Attention** : Mourir avant de récupérer l'âme la fait disparaître définitivement

### Conseils stratégiques

- **Utilisez les échos avec parcimonie** : Le cooldown de 6 secondes vous oblige à anticiper
- **Mémorisez la carte** : La vision révélée reste permanente, profitez-en
- **Explorez méthodiquement** : Les points de repère vous guident vers les zones importantes
- **Gérez votre argent** : Ne prenez pas de risques inutiles avec une grosse somme
- **Coopérez en multijoueur** : Chaque joueur a sa propre vision, partagez vos découvertes
- **Maîtrisez le dash** : Un seul dash en l'air, utilisez-le pour franchir les gouffres

---

## 📁 Structure du projet

### Modules principaux

#### `client.py` - Interface et rendu
- Boucle de jeu principale
- Capture des inputs clavier/souris
- Affichage graphique (joueurs, ennemis, carte, UI)
- Gestion des menus (principal, pause, paramètres, slots)
- Communication avec le serveur
- Système de caméra

#### `serveur.py` - Logique de jeu
- Boucle de simulation physique (60 FPS)
- IA des ennemis (patrouille, détection du vide)
- Détection et résolution des combats
- Gestion de la mort et du respawn
- Sauvegarde automatique aux checkpoints
- Distribution de l'état du jeu aux clients

#### `joueur.py` - Entité joueur
- Physique (gravité, saut, dash)
- Stats (PV, argent)
- Combat (attaque, hitbox)
- Capacités spéciales (double saut, dash)
- Sérialisation pour le réseau

#### `carte.py` - Environnement
- Chargement de la tilemap
- Raycasting pour l'écholocalisation
- Gestion des cartes de visibilité individuelles
- Rendu de la carte avec offset caméra
- Détection de collisions

#### `ennemi.py` - Adversaires
- IA de patrouille simple
- Détection du vide (changement de direction)
- Système de PV et dégâts
- Feedback visuel (clignotement)

#### `ame_perdue.py` - Système d'âmes
- Objet laissé à la mort
- Stockage de l'argent perdu
- Récupération par attaque

### Modules utilitaires

#### `gestion_sauvegarde.py`
- Création de sauvegardes vierges
- Lecture/écriture des fichiers `slot_X.json`
- Validation de l'intégrité des données
- Gestion des chemins absolus

#### `gestion_parametres.py`
- Lecture/écriture de `parametres.json`
- Création de paramètres par défaut
- Validation et complétion automatique

#### `points_sauvegarde.py`
- Conversion ID checkpoint ↔ coordonnées
- Noms lisibles pour l'affichage
- Gestion du point de départ

#### `langue.py` - Internationalisation
- Dictionnaires de traduction (FR/EN)
- Fonction `get_texte(cle)` pour récupérer les chaînes
- Support de nouvelles langues facilité

#### `bouton.py` - Composant UI
- Classe réutilisable pour les menus
- Gestion du survol et des clics
- Rendu avec bordures arrondies

#### `parametres.py` - Configuration
- Toutes les constantes du jeu
- Valeurs de gameplay (vitesse, dégâts, cooldowns)
- Couleurs et dimensions
- Facilite le game design et le balancing

---

## 💾 Système de sauvegarde

### Format de sauvegarde

Chaque slot est un fichier JSON structuré :

```json
{
    "id_dernier_checkpoint": "3_21",
    "vis_map": [
        [true, false, false, ...],
        [false, true, false, ...],
        ...
    ],
    "items": [],
    "ameliorations": {
        "double_saut": true,
        "dash": false
    },
    "argent": 150
}
```

### Champs détaillés

| Champ | Type | Description |
|-------|------|-------------|
| `id_dernier_checkpoint` | string | Format "x_y" de la tuile checkpoint |
| `vis_map` | 2D array | Carte booléenne de visibilité (même taille que map_data) |
| `items` | array | Liste des items collectés (système extensible) |
| `ameliorations` | object | Capacités débloquées (double_saut, dash, etc.) |
| `argent` | integer | Âmes collectées et sauvegardées |

### Mécanisme de sauvegarde

1. **Déclenchement** : Contact avec une tuile de type 3
2. **Vérification** : Uniquement pour l'hôte (id_joueur == 0)
3. **Données capturées** :
   - Position actuelle → nouveau checkpoint
   - Carte de visibilité complète
   - Argent en possession
   - Capacités débloquées
4. **Écriture** : Sérialisation JSON avec indentation (lisibilité)

### Chargement

```python
# Au démarrage du serveur
donnees = gestion_sauvegarde.charger_partie(id_slot)
if donnees:
    # Restauration de l'état
    spawn = points_sauvegarde.get_coords_par_id(donnees["id_dernier_checkpoint"])
    joueur.argent = donnees.get("argent", 0)
    joueur.peut_double_saut = donnees["ameliorations"]["double_saut"]
    # etc.
```

---

## 🛠️ Technologies utilisées

### Langage et bibliothèques

- **Python 3.8+** : Langage principal
  - Facilité d'apprentissage pour un projet étudiant
  - Syntaxe claire et lisible
  - Riche écosystème de bibliothèques

- **Pygame 2.0+** : Framework de jeu 2D
  - Gestion de la fenêtre et des événements
  - Rendu graphique 2D (sprites, formes, texte)
  - Gestion du temps et de la boucle de jeu
  - Manipulation des surfaces et transformations

### Réseau

- **Sockets TCP** (bibliothèque standard `socket`)
  - Communication fiable client-serveur
  - Sérialisation avec `pickle` pour l'échange d'objets Python
  - Threading pour gérer plusieurs clients simultanément

### Données

- **JSON** : Format de sauvegarde
  - Lisible et éditable manuellement
  - Facilite le débogage
  - Support natif en Python (`json` module)

- **Pickle** : Sérialisation réseau
  - Transmission rapide d'objets complexes
  - Support des types Python natifs

### Outils de développement

- **Git** : Gestion de versions
- **VS Code / PyCharm** : Environnements de développement
- **Tiled Map Editor** : Création de cartes (Map.tmx)

---

## 🔮 Développements futurs

### Fonctionnalités planifiées

#### Court terme
- [ ] **Système de boutique** : Dépenser l'argent pour acheter des améliorations
- [ ] **Plus de capacités** : Escalade, glissade murale, double dash
- [ ] **Variété d'ennemis** : Différents patterns d'IA, ennemis volants, boss
- [ ] **Particules et effets** : Traînées de dash, échos visuels, impacts
- [ ] **Sound design** : Musique d'ambiance, bruitages d'écho, effets sonores

#### Moyen terme
- [ ] **Cartes TMX** : Chargement de cartes créées avec Tiled
- [ ] **Système de quêtes** : Objectifs secondaires, dialogues NPC
- [ ] **Items et inventaire** : Clés, potions, équipements
- [ ] **Sauvegarde cloud** : Synchronisation entre machines
- [ ] **Lobby multijoueur** : Liste de serveurs publics, chat

#### Long terme
- [ ] **Campagne complète** : Histoire scénarisée, cinématiques
- [ ] **Mode compétitif** : PvP, courses contre la montre
- [ ] **Éditeur de niveaux** : Création de cartes par la communauté
- [ ] **Modding** : Support de scripts Lua, assets personnalisés
- [ ] **Portage** : Version web (Pygame Web), mobile

### Améliorations techniques

- **Optimisation réseau** : Interpolation, prédiction client, delta compression
- **Système d'entités-composants** : Architecture ECS pour plus de flexibilité
- **Shaders** : Effets visuels avancés (glow, distorsion)
- **Pathfinding** : IA ennemie plus sophistiquée (A*, navigation meshes)
- **Génération procédurale** : Cartes aléatoires, mode roguelite

---

## 📜 Crédits et remerciements

### Équipe de développement

### Ressources et inspirations

- **Hollow Knight** : Inspiration pour le game feel et l'atmosphère
- **Dark Souls** : Système d'âmes perdues
- **Rain World** : IA ennemie et level design
- **Pygame Documentation** : [pygame.org](https://www.pygame.org/docs/)
- **Real Python** : Tutoriels réseau et bonnes pratiques

### Remerciements

- **Enseignants et encadrants** du cycle préparatoire pour leur soutien
- **Communauté Pygame** pour les ressources et l'entraide
- **Testeurs** ayant fourni des retours précieux

---

## 📄 Licence

Ce projet est un travail étudiant à but éducatif. Le code source est fourni tel quel pour référence et apprentissage.

**Projet réalisé dans le cadre du cycle préparatoire - S1 & S2**  
**Institution : [Nom de l'école à compléter]**  
**Année académique : [Année à compléter]**

---

## 📞 Contact

Pour toute question concernant ce projet :

- **Site web du jeu** : https://florian-croiset.github.io/jeusite/
- **Dépôt GitHub** : https://github.com/florian-croiset/projetjeu
---

*README généré avec ❤️ par la team Nightberry*