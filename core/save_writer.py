"""Background writer for save files.

Serializing and writing a save slot takes tens of milliseconds; doing it on the
simulation thread would freeze the game for a few ticks. ``SaveWriter`` takes a
snapshot of the data on the caller's thread (cheap) and writes it on a worker
thread. Only the newest pending save is kept ("latest wins").
"""

import copy
import threading


class SaveWriter:
    def __init__(self, write_fn):
        """``write_fn(slot_id, data)`` performs the actual (blocking) write."""
        self._write_fn = write_fn
        self._cond = threading.Condition()
        self._pending = None
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="SaveWriter", daemon=True)
        self._thread.start()

    def save(self, slot_id, data):
        snapshot = copy.deepcopy(data)
        with self._cond:
            self._pending = (slot_id, snapshot)
            self._cond.notify()

    def flush_and_stop(self, timeout=5.0):
        """Write whatever is pending, then stop the worker."""
        with self._cond:
            self._stop = True
            self._cond.notify()
        self._thread.join(timeout)

    def _run(self):
        while True:
            with self._cond:
                while self._pending is None and not self._stop:
                    self._cond.wait()
                job, self._pending = self._pending, None
                stopping = self._stop
            if job is not None:
                try:
                    self._write_fn(*job)
                except Exception as exc:       # never kill the worker
                    print(f"[SAVE] write failed: {exc}")
            if stopping:
                with self._cond:
                    if self._pending is None:
                        return
