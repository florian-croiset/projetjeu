# editeur_niveaux.py — Point d'entrée de l'éditeur de niveaux TMX d'Écho.
#
# Usage :
#   python editeur_niveaux.py                  → ouvre assets/MapS2.tmx
#   python editeur_niveaux.py chemin/map.tmx   → ouvre la map indiquée

import sys
import os

# Garantir que la racine du projet est dans sys.path (même pattern que main.py)
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from editeur.editeur import Editeur


if __name__ == "__main__":
    chemin = sys.argv[1] if len(sys.argv) > 1 else "assets/MapS2.tmx"
    if not os.path.exists(chemin):
        print(f"Erreur : fichier introuvable : {chemin}")
        sys.exit(1)

    Editeur(chemin).lancer()
