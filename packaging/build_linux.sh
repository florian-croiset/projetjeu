#!/bin/bash
# Build script for Echo on Linux.
# Usage: ./packaging/build_linux.sh [--clean] [--dev]
#   --clean  remove the previous builds before compiling
#   --dev    build with DEV_MODE=True (default: DEV_MODE=False)
# Requirements: Python 3.10+, pip
# Output: dist/Echo (single self-contained executable)

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Parse the arguments (any order)
OPT_CLEAN=0
OPT_DEV=0
for arg in "$@"; do
    case "$arg" in
        --clean) OPT_CLEAN=1 ;;
        --dev)   OPT_DEV=1 ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

if [[ $OPT_DEV -eq 1 ]]; then
    echo "=== Building Echo for Linux [DEV MODE] ==="
else
    echo "=== Building Echo for Linux [RELEASE] ==="
fi
echo "Directory: $PROJECT_DIR"

# --- Cleaning ---
if [[ $OPT_CLEAN -eq 1 ]]; then
    echo "[1/5] Removing the previous builds..."
    rm -rf build/ dist/
fi

# --- Python / virtualenv detection ---
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"; PIP=".venv/bin/pip"
    echo "[2/5] Virtualenv found: .venv"
elif [[ -f "venv/bin/python" ]]; then
    PYTHON="venv/bin/python"; PIP="venv/bin/pip"
    echo "[2/5] Virtualenv found: venv"
else
    PYTHON="python3"; PIP="pip3"
    echo "[2/5] Using the system Python"
fi

# --- Patch DEV_MODE in settings.py ---
SETTINGS="settings.py"
SETTINGS_BAK="settings.py.bak_build"

# Always restore the file, even on error or interruption
restore_settings() {
    if [[ -f "$SETTINGS_BAK" ]]; then
        mv "$SETTINGS_BAK" "$SETTINGS"
        echo "[INFO] settings.py restored."
    fi
}
trap restore_settings EXIT

cp "$SETTINGS" "$SETTINGS_BAK"

if [[ $OPT_DEV -eq 0 ]]; then
    echo "[3/5] DEV_MODE disabled for the release..."
    $PYTHON -c "
import re
with open('settings.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = re.sub(r'^(DEV_MODE\s*=\s*)True', r'\1False', content, flags=re.MULTILINE)
with open('settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
"
else
    echo "[3/5] DEV_MODE kept (--dev)..."
fi

# --- PyInstaller ---
echo "[4/5] Installing PyInstaller..."
$PIP install --quiet pyinstaller

# --- Build ---
echo "[5/5] Building (can take 2-4 minutes)..."
$PYTHON -m PyInstaller \
    --name "Echo" \
    --onefile \
    --add-data "assets:assets" \
    --hidden-import "xml.etree.ElementTree" \
    --hidden-import "numpy" \
    --hidden-import "pygame" \
    --hidden-import "pygame.mixer" \
    --hidden-import "pygame.font" \
    --icon "assets/favicon.ico" \
    --noconfirm \
    main.py

echo ""
echo "Build finished!"
echo "Executable: dist/Echo (single file, nothing else needed)"
echo "To run it: ./dist/Echo"
echo "To distribute it: send the dist/Echo file"
