# core/pathfinding.py
# Service de pathfinding A* exécuté dans un thread dédié.
#
# Objectif : isoler la recherche A* du tick serveur (60 Hz) pour éviter
# les pics de latence lorsque plusieurs ennemis demandent un chemin la
# même frame.
#
# API utilisée par Ennemi :
#   svc.demander(id_ennemi, depart, arrivee, temps_ms)
#       Dépose une requête. Si une requête en attente existe déjà pour cet
#       ennemi, elle est remplacée (coalescing : seul le dernier état
#       compte). Très peu coûteux côté appelant.
#   svc.recuperer(id_ennemi) -> (temps_req_ms, [chemin]) | None
#       Lit le dernier résultat disponible. Le timestamp permet à l'ennemi
#       de détecter qu'un nouveau chemin est arrivé.
#   svc.oublier(id_ennemi)
#       Nettoie les buffers (à appeler quand l'ennemi quitte la chasse).
#   svc.arreter()
#       Stoppe proprement le thread (le worker est aussi daemon, donc il
#       meurt avec le process si on n'appelle pas arreter()).
#
# Threading model : un unique worker traite les requêtes en série. Toutes
# les structures partagées sont protégées par un Condition. La carte est
# accédée en lecture seule (map_data immuable après chargement).

import threading

from core.astar import trouver_chemin


class PathfindingService:
    def __init__(self, carte, max_iter=1500, hauteur_saut=2):
        self.carte = carte
        self.max_iter = max_iter
        self.hauteur_saut = hauteur_saut

        # État partagé
        self._pending = {}   # id_ennemi -> (depart, arrivee, temps_req_ms)
        self._results = {}   # id_ennemi -> (temps_req_ms, [chemin])
        self._stop = False

        self._cond = threading.Condition()
        self._thread = threading.Thread(
            target=self._boucle_worker,
            name="Pathfinder",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    #  API publique (appelée depuis le thread serveur)
    # ------------------------------------------------------------------

    def demander(self, id_ennemi, depart, arrivee, temps_ms):
        with self._cond:
            self._pending[id_ennemi] = (depart, arrivee, temps_ms)
            self._cond.notify()

    def recuperer(self, id_ennemi):
        # Lecture sans lock acceptable (dict read en CPython = atomique pour
        # un single get), mais on prend le lock par prudence — le coût est
        # négligeable comparé au reste de la frame.
        with self._cond:
            return self._results.get(id_ennemi)

    def oublier(self, id_ennemi):
        with self._cond:
            self._pending.pop(id_ennemi, None)
            self._results.pop(id_ennemi, None)

    def arreter(self):
        with self._cond:
            self._stop = True
            self._cond.notify_all()

    # ------------------------------------------------------------------
    #  Worker thread
    # ------------------------------------------------------------------

    def _boucle_worker(self):
        while True:
            with self._cond:
                while not self._pending and not self._stop:
                    self._cond.wait(timeout=1.0)
                if self._stop:
                    return
                # Pop d'une requête (dict ordonné → FIFO d'insertion).
                id_ennemi = next(iter(self._pending))
                depart, arrivee, temps_req_ms = self._pending.pop(id_ennemi)

            # Calcul A* hors lock — la carte est en lecture seule.
            try:
                chemin = trouver_chemin(
                    self.carte, depart, arrivee,
                    max_iter=self.max_iter,
                    hauteur_saut=self.hauteur_saut,
                )
            except Exception as exc:
                print(f"[PATHFINDING] A* a échoué pour ennemi {id_ennemi}: {exc}")
                chemin = []

            with self._cond:
                # On ne remplace que si plus récent qu'un éventuel résultat
                # déjà déposé (cas où plusieurs requêtes se chevauchent).
                ancien = self._results.get(id_ennemi)
                if ancien is None or ancien[0] <= temps_req_ms:
                    self._results[id_ennemi] = (temps_req_ms, chemin)
