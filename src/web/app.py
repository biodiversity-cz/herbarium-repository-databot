from flask import Flask, jsonify
from core import job_store
from config.config import Config

app = Flask(__name__)
config = Config()

@app.route("/status")
def status():
    return jsonify({
        "running": job_store.get_running(),
        "last_runs": job_store.get_history(5),
        "next_scheduled": list(config.bots.keys())[:5],  # Zatím fake
    })
