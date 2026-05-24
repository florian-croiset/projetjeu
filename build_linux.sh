#!/bin/bash
# Script de compilation d'Écho pour Linux
# Usage : ./build_linux.sh [--clean] [--dev]
#   --clean  supprime les builds précédents avant de compiler
#   --dev    compile avec MODE_DEV=True (défaut : MODE_DEV=False)
# Prérequis : Python 3.10+, pip
# Sortie : dist/Echo (fichier unique)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Lecture des arguments (ordre libre)
OPT_CLEAN=0
OPT_DEV=0
for arg in "$@"; do
    case "$arg" in
        --clean) OPT_CLEAN=1 ;;
        --dev)   OPT_DEV=1 ;;
        *) echo "Argument inconnu : $arg"; exit 1 ;;
    esac
done

if [[ $OPT_DEV -eq 1 ]]; then
    echo "=== Compilation d'Écho pour Linux [MODE DEV] ==="
else
    echo "=== Compilation d'Écho pour Linux [RELEASE] ==="
fi
echo "Répertoire : $PROJECT_DIR"

# --- Nettoyage ---
if [[ $OPT_CLEAN -eq 1 ]]; then
    echo "[1/5] Nettoyage des builds précédents..."
    rm -rf build/ dist/ Echo.spec
fi

# --- Détection Python / virtualenv ---
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"; PIP=".venv/bin/pip"
    echo "[2/5] Virtualenv détecté : .venv"
elif [[ -f "venv/bin/python" ]]; then
    PYTHON="venv/bin/python"; PIP="venv/bin/pip"
    echo "[2/5] Virtualenv détecté : venv"
else
    PYTHON="python3"; PIP="pip3"
    echo "[2/5] Python système utilisé"
fi

# --- Patch MODE_DEV dans parametres.py ---
PARAMETRES="parametres.py"
PARAMETRES_BAK="parametres.py.bak_build"

# Restauration garantie même en cas d'erreur ou d'interruption
restore_parametres() {
    if [[ -f "$PARAMETRES_BAK" ]]; then
        mv "$PARAMETRES_BAK" "$PARAMETRES"
        echo "[INFO] parametres.py restauré."
    fi
}
trap restore_parametres EXIT

cp "$PARAMETRES" "$PARAMETRES_BAK"

if [[ $OPT_DEV -eq 0 ]]; then
    echo "[3/5] MODE_DEV désactivé pour la release..."
    $PYTHON -c "
import re, sys
with open('parametres.py', 'r') as f:
    content = f.read()
content = re.sub(r'^(MODE_DEV\s*=\s*)True', r'\1False', content, flags=re.MULTILINE)
with open('parametres.py', 'w') as f:
    f.write(content)
"
else
    echo "[3/5] MODE_DEV conservé (--dev)..."
fi

# --- Installation de PyInstaller ---
echo "[4/5] Installation de PyInstaller..."
$PIP install --quiet pyinstaller

# --- Compilation ---
echo "[5/5] Compilation en cours (peut prendre 2-4 minutes)..."
$PYTHON -m PyInstaller \
    --name "Echo" \
    --onefile \
    --add-data "assets:assets" \
    --add-data "demon_slime.json:." \
    --add-data "map.json:." \
    --add-data "favicon.ico:." \
    --add-data "favicon.png:." \
    --hidden-import "xml.etree.ElementTree" \
    --hidden-import "xml.etree.cElementTree" \
    --hidden-import "numpy" \
    --hidden-import "pygame" \
    --hidden-import "pygame.mixer" \
    --hidden-import "pygame.font" \
    --icon "favicon.ico" \
    --noconfirm \
    main.py

echo ""
echo "Compilation terminée !"
echo "Exécutable : dist/Echo (fichier unique, tout inclus)"
echo "Pour lancer : ./dist/Echo"
