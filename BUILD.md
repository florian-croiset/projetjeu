# Compilation d'Écho

## Prérequis

- Python 3.10+
- pip
- Les dépendances du projet (`pip install -r requirements.txt`)

PyInstaller est installé automatiquement par les scripts.

---

## Linux

```bash
./build_linux.sh          # build release (MODE_DEV désactivé)
./build_linux.sh --dev    # build avec MODE_DEV activé
./build_linux.sh --clean  # nettoie les builds précédents puis compile
```

Sortie : `dist/Echo/Echo`

Pour lancer : `./dist/Echo/Echo`

---

## Windows

```bat
build_windows.bat          :: build release (MODE_DEV désactivé)
build_windows.bat --dev    :: build avec MODE_DEV activé
build_windows.bat --clean  :: nettoie les builds précédents puis compile
```

Les arguments peuvent se combiner dans n'importe quel ordre :
```bat
build_windows.bat --clean --dev
```

Sortie : `dist\Echo\Echo.exe`

---

## Distribution

Zipper le dossier `dist/Echo/` — il contient tout le nécessaire, aucun Python requis sur la machine cible.

Ne pas distribuer les fichiers `slot_*.json` ni `parametres.json` — ils sont propres à chaque joueur et générés automatiquement au premier lancement dans :
- **Linux** : `~/.local/share/Echo/`
- **Windows** : `%LOCALAPPDATA%\Echo\`

---

## Différences release / dev

| | Release (défaut) | `--dev` |
|---|---|---|
| `MODE_DEV` | `False` | `True` |
| Compteur FPS | non | oui |
| Orbes débloqués auto | non | oui |
| Overlay debug | non | oui |

> `parametres.py` est patché temporairement pendant la compilation puis restauré automatiquement.
