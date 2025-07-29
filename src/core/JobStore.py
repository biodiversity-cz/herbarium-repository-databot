from datetime import datetime
from threading import Lock

class JobStore:
    def __init__(self):
        self._running = set()
        self._history = []
        self._lock = Lock()

    def mark_running(self, bot_name: str):
        with self._lock:
            self._running.add(bot_name)
            self._history.append((bot_name, datetime.now(), "running"))

    def mark_finished(self, bot_name: str):
        with self._lock:
            self._running.discard(bot_name)
            self._history.append((bot_name, datetime.now(), "finished"))

    def mark_failed(self, bot_name: str, exc: Exception):
        with self._lock:
            self._running.discard(bot_name)
            self._history.append((bot_name, datetime.now(), f"error: {exc}"))

    def get_running(self):
        with self._lock:
            return list(self._running)

    def get_history(self, n=5):
        with self._lock:
            return [
                {"name": name, "time": ts.isoformat(), "status": status}
                for name, ts, status in self._history[-n:]
            ]
