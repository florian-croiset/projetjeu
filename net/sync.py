"""Client-side time synchronisation and snapshot interpolation helpers."""

import bisect
import collections

MAX_EXTRAPOLATION_MS = 100


class ServerClock:
    """Maps the server simulation clock onto the local monotonic clock.

    Each snapshot gives one sample ``local_arrival - server_time`` (= clock
    offset + one-way delay). The *minimum* over a sliding window is the best
    estimate of the pure offset (the sample that suffered the least delay)."""

    def __init__(self, window=180):
        self._samples = collections.deque(maxlen=window)
        self.offset_ms = None

    def add_sample(self, server_ms: float, local_ms: float):
        self._samples.append(local_ms - server_ms)
        self.offset_ms = min(self._samples)

    def server_time_at(self, local_ms: float):
        """Estimated server time at local time ``local_ms`` (None until synced)."""
        if self.offset_ms is None:
            return None
        return local_ms - self.offset_ms

    def jitter_ms(self) -> float:
        """Spread of the recent samples above the minimum (rough jitter estimate)."""
        if len(self._samples) < 10:
            return 0.0
        ordered = sorted(self._samples)
        return ordered[int(len(ordered) * 0.9)] - ordered[0]


class PositionBuffer:
    """Time-stamped positions of a remote entity, sampled with interpolation."""

    def __init__(self, keep_ms=1000):
        self._times = []
        self._points = []           # (x, y), parallel to _times
        self._keep_ms = keep_ms

    def push(self, t_ms: float, x: float, y: float):
        if self._times and t_ms <= self._times[-1]:
            return                   # out of order / duplicate
        self._times.append(t_ms)
        self._points.append((x, y))
        horizon = t_ms - self._keep_ms
        cut = bisect.bisect_left(self._times, horizon)
        if cut > 1:
            del self._times[:cut - 1]
            del self._points[:cut - 1]

    def clear(self):
        self._times.clear()
        self._points.clear()

    def sample(self, t_ms: float):
        """Position at server time ``t_ms``; None if the buffer is empty."""
        times = self._times
        if not times:
            return None
        if t_ms <= times[0]:
            return self._points[0]
        if t_ms >= times[-1]:
            x, y = self._points[-1]
            if len(times) >= 2:
                over = min(t_ms - times[-1], MAX_EXTRAPOLATION_MS)
                span = times[-1] - times[-2]
                if span > 0:
                    px, py = self._points[-2]
                    k = over / span
                    return x + (x - px) * k, y + (y - py) * k
            return x, y
        i = bisect.bisect_right(times, t_ms)
        t0, t1 = times[i - 1], times[i]
        (x0, y0), (x1, y1) = self._points[i - 1], self._points[i]
        a = (t_ms - t0) / (t1 - t0)
        return x0 + (x1 - x0) * a, y0 + (y1 - y0) * a
