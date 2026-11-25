# main.py - entry point of the Echo game
# Add the project root to sys.path so that the imports
# work correctly from every sub-folder.

import sys
import os

# Make sure the project root is in sys.path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from client import Client
from utils import crash_report

if __name__ == "__main__":
    crash_report.install()
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        from client.selftest import run
        run(sys.argv[2])
    client_game = Client()
    client_game.launch_application()
