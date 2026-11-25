# core/pathfinding.py
# A* pathfinding service running in a dedicated thread.
#
# Goal: isolate the A* search from the server tick (60 Hz) to avoid
# latency spikes when several enemies request a path in the same
# frame.
#
# API used by Enemy:
# svc.request(enemy_id, start, goal, time_ms)
# Submit a request. If a pending request already exists for this
# enemy it is replaced (coalescing: only the latest state
# matters). Very cheap for the caller.
# svc.fetch(enemy_id) -> (request_time_ms, [path]) | None
# Read the latest available result. The timestamp lets the enemy
# detect that a new path arrived.
# svc.forget(enemy_id)
# Clear the buffers (call when the enemy stops chasing).
# svc.stop()
# Stop the thread cleanly (the worker is also a daemon, so it
# dies with the process if stop() is not called).
#
# Threading model: a single worker processes the requests serially. All
# shared structures are protected by a Condition. The map is only
# read (map_data is immutable after loading).

import threading

from core.astar import find_path


class PathfindingService:
    def __init__(self, game_map, max_iter=1500, height_jump=2):
        self.game_map = game_map
        self.max_iter = max_iter
        self.height_jump = height_jump

        # Shared state
        self._pending = {}   # enemy_id -> (start, goal, request_time_ms)
        self._results = {}   # enemy_id -> (request_time_ms, [path])
        self._stop = False

        self._cond = threading.Condition()
        self._thread = threading.Thread(
            target=self._loop_worker,
            name="Pathfinder",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API (called from the server thread)
    # ------------------------------------------------------------------

    def request(self, id_enemy, start, goal, time_ms):
        with self._cond:
            self._pending[id_enemy] = (start, goal, time_ms)
            self._cond.notify()

    def fetch(self, id_enemy):
        # A lock-free read would be acceptable (a single dict get is atomic in CPython),
        # but the lock is taken to be safe - its cost is
        # negligible compared with the rest of the frame.
        with self._cond:
            return self._results.get(id_enemy)

    def forget(self, id_enemy):
        with self._cond:
            self._pending.pop(id_enemy, None)
            self._results.pop(id_enemy, None)

    def stop(self):
        with self._cond:
            self._stop = True
            self._cond.notify_all()

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _loop_worker(self):
        while True:
            with self._cond:
                while not self._pending and not self._stop:
                    self._cond.wait(timeout=1.0)
                if self._stop:
                    return
                # Pop one request (ordered dict -> insertion-order FIFO).
                id_enemy = next(iter(self._pending))
                start, goal, time_req_ms = self._pending.pop(id_enemy)

            # A* computation outside the lock - the map is read-only.
            try:
                path = find_path(
                    self.game_map, start, goal,
                    max_iter=self.max_iter,
                    height_jump=self.height_jump,
                )
            except Exception as exc:
                print(f"[PATHFINDING] A* failed for enemy {id_enemy}: {exc}")
                path = []

            with self._cond:
                # Only replace the stored result if the new one is newer than an
                # already deposited result (when several requests overlap).
                old = self._results.get(id_enemy)
                if old is None or old[0] <= time_req_ms:
                    self._results[id_enemy] = (time_req_ms, path)
