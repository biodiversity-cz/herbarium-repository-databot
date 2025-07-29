from flask import Flask, jsonify
from config import config

class BotUI:
    def __init__(self, job_store, scheduler):
        self.job_store = job_store
        self.scheduler = scheduler
        self.app = Flask(__name__)
        self._register_routes()

    def _register_routes(self):
        @self.app.route("/")
        def status():
            return jsonify({
                "running": self.job_store.get_running(),
                "last_runs": self.job_store.get_history(config.get_application_config('history', 5)),
                "next_scheduled": self.scheduler.get_next_runs(),
            })

    def run(self, **kwargs):
        self.app.run(**kwargs)

    def get_app(self):
        return self.app
