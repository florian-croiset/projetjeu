# main.py — Point d'entrée du jeu Écho
# Ajoute la racine du projet au sys.path pour que les imports
# fonctionnent correctement depuis tous les sous-dossiers.

import sys
import os

# Garantir que la racine du projet est dans sys.path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from client import Client

if __name__ == "__main__":
    client_jeu = Client()
    client_jeu.lancer_application()


