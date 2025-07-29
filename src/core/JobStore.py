import uuid
from datetime import datetime
from threading import Lock

class JobStore:
    def __init__(self):
        self._running = {}  # map bot_name -> set of run_ids
        self._history = []  # seznam dictů s běhy
        self._lock = Lock()

    def mark_running(self, bot_name: str) -> str:
        with self._lock:
            run_id = str(uuid.uuid4())
            self._running.setdefault(bot_name, set()).add(run_id)
            self._history.append({
                "id": bot_name,
                "run_id": run_id,
                "started": datetime.now(),
                "finished": None,
                "status": "running",
                "error": None,
            })
            return run_id

    def mark_finished(self, bot_name: str, run_id: str):
        with self._lock:
            if bot_name in self._running and run_id in self._running[bot_name]:
                self._running[bot_name].remove(run_id)
            for run in reversed(self._history):
                if run["id"] == bot_name and run["run_id"] == run_id and run["status"] == "running":
                    run["finished"] = datetime.now()
                    run["status"] = "finished"
                    break

    def mark_failed(self, bot_name: str, run_id: str, exc: Exception):
        with self._lock:
            if bot_name in self._running and run_id in self._running[bot_name]:
                self._running[bot_name].remove(run_id)
            for run in reversed(self._history):
                if run["id"] == bot_name and run["run_id"] == run_id and run["status"] == "running":
                    run["finished"] = datetime.now()
                    run["status"] = "error"
                    run["error"] = str(exc)
                    break

    def get_running(self):
        with self._lock:
            # vrátí dict bot_name -> počet běhů
            return {bot: len(runs) for bot, runs in self._running.items() if runs}

    def get_history(self, n=5):
        with self._lock:
            recent = self._history[-n:]
            return [
                {
                    "id": run["id"],
                    "run_id": run["run_id"],
                    "started": run["started"].isoformat(),
                    "finished": run["finished"].isoformat() if run["finished"] else None,
                    "status": run["status"],
                    "error": run["error"],
                }
                for run in recent
            ]
