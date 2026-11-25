# tools/level_editor.py - entry point of the Echo TMX level editor.
#
# Usage:
# python tools/level_editor.py          -> opens assets/MapS2.tmx
# python tools/level_editor.py path/to/map.tmx  -> opens the given map

import sys
import os

# Make sure the project root is in sys.path (same pattern as main.py)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.editor.editor import Editor


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/MapS2.tmx"
    if not os.path.exists(path):
        print(f"Error: file not found: {path}")
        sys.exit(1)

    Editor(path).launch()
