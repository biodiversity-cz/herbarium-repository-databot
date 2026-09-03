"""Flask status/chart endpoints, served in-process by waitress.

Why waitress and not gunicorn: the scheduler, the worker pool and the JobStore
all live in the memory of this one process. Running the WSGI app with several
worker processes would start several schedulers and several database pools, so
the app is served by a single process with a small thread pool instead.
"""

import logging
import threading
from time import monotonic

from flask import Flask, jsonify, request, send_file

from config import config
from core.infrastructure.database.connection_pool import get_pool, peek_pool
from services.chart_service import ChartService

logger = logging.getLogger(__name__)


class BotUI:
    def __init__(self, job_store, scheduler, job_queue=None, worker_pool=None):
        self.job_store = job_store
        self.scheduler = scheduler
        self.job_queue = job_queue
        self.worker_pool = worker_pool
        self.started_at = monotonic()
        self.app = Flask(__name__)
        self._server = None
        self._thread = None
        self._register_routes()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    def _register_routes(self):
        @self.app.route("/healthz")
        def healthz():
            """Liveness probe: the process is up and its loop is alive.

            Deliberately does not touch the database, so a database incident
            does not make Kubernetes restart an otherwise healthy pod.
            """
            return jsonify({
                "status": "ok",
                "uptime_seconds": round(monotonic() - self.started_at, 1),
                "scheduler_running": bool(self.scheduler and self.scheduler.is_running()),
                "queue_depth": self.job_queue.qsize() if self.job_queue is not None else None,
            })

        @self.app.route("/readyz")
        def readyz():
            """Readiness probe: one cheap query through the connection pool."""
            try:
                with get_pool().connection() as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                    finally:
                        cursor.close()
            except Exception as exc:
                logger.warning("Readiness check failed: %s", exc)
                return jsonify({
                    "status": "unavailable",
                    "error": exc.__class__.__name__,
                    "db_pool": self._pool_stats(),
                }), 503

            return jsonify({"status": "ready", "db_pool": self._pool_stats()})

        @self.app.route("/")
        @self.app.route("/status")
        def status():
            """Operational overview - no credentials, no connection strings."""
            return jsonify(self._status_payload())

        @self.app.route("/chart/<metric>")
        def chart(metric: str):
            """
            Vygeneruje boxplot pro zadanou metriku s červenou linkou pro highlight.
            Parametry GET:
                highlight: hodnota červené linky (povinné)
                bins: počet binů (volitelné, default 10)
            """
            highlight = request.args.get("highlight", type=float)
            bins = request.args.get("bins", default=10, type=int)

            if highlight is None:
                return jsonify({"error": "Missing 'highlight' query parameter"}), 400

            try:
                service = ChartService()
                img_bytes = service.generate_boxplot(metric=metric, highlight=highlight)
            except Exception as exc:
                logger.exception("Chart generation failed for metric '%s': %s", metric, exc)
                return jsonify({"error": "chart_generation_failed"}), 500

            if img_bytes is None:
                return jsonify({"error": f"No data found for metric {metric}"}), 404

            return send_file(img_bytes, mimetype="image/png")

    def _pool_stats(self) -> dict:
        pool = peek_pool()
        return pool.stats() if pool is not None else {"initialized": False}

    def _status_payload(self) -> dict:
        payload = {
            "uptime_seconds": round(monotonic() - self.started_at, 1),
            "running": self.job_store.get_running(),
            "last_runs": self.job_store.get_history(config.get_application_int("history", 5)),
            "next_scheduled": self.scheduler.get_next_runs() if self.scheduler else [],
            "scheduler_running": bool(self.scheduler and self.scheduler.is_running()),
            "db_pool": self._pool_stats(),
        }
        if self.worker_pool is not None:
            payload["workers"] = self.worker_pool.stats()
        elif self.job_queue is not None:
            payload["queue_depth"] = self.job_queue.qsize()
        if self.scheduler is not None and hasattr(self.scheduler, "get_queued"):
            payload["queued"] = self.scheduler.get_queued()
        return payload

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------
    def start(self, host: str = "0.0.0.0", port: int = 5000, threads: int | None = None):
        """Start serving in a background thread and return the server object."""
        host = host or "0.0.0.0"
        port = int(port)
        threads = int(threads) if threads else max(4, config.get_application_int("web_threads", 8))
        self._server = self._create_server(host, port, threads)
        self._thread = threading.Thread(target=self._run_server, name="databot-web", daemon=True)
        self._thread.start()
        logger.info("Serving web UI on http://%s:%s (threads=%s)", host, port, threads)
        return self._server

    def _create_server(self, host: str, port: int, threads: int):
        try:
            from waitress import create_server
        except ImportError:
            logger.warning(
                "waitress is not installed - falling back to the Werkzeug development "
                "server; rebuild the image so the locked waitress release is used"
            )
            from werkzeug.serving import make_server
            return make_server(host, port, self.app, threaded=True)

        return create_server(
            self.app,
            listen=f"{host}:{port}",
            threads=threads,
            # A stuck request must not occupy a worker thread (and therefore a
            # database connection) indefinitely.
            channel_timeout=config.get_application_int("web_channel_timeout", 120),
            connection_limit=config.get_application_int("web_connection_limit", 100),
            expose_tracebacks=str(
                config.get_application_config("web_expose_tracebacks", False)
            ).strip().lower() in {"1", "true", "yes", "on"},
        )

    def _run_server(self):
        try:
            # Werkzeug's dev server is driven by serve_forever(), waitress by run().
            serve_forever = getattr(self._server, "serve_forever", None)
            if serve_forever is not None:
                serve_forever(poll_interval=0.2)
            else:
                self._server.run()
        except Exception:
            logger.exception("The web server stopped unexpectedly")

    def stop(self):
        """Stop the HTTP server without waiting forever for in-flight requests."""
        server, self._server = self._server, None
        if server is None:
            return
        logger.info("Stopping web server...")
        try:
            # Werkzeug's dev server exposes shutdown(), waitress exposes close().
            if hasattr(server, "shutdown"):
                server.shutdown()
            else:
                server.close()
        except Exception as exc:
            logger.warning("Web server shutdown failed: %s", exc)

        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def run(self, **kwargs):
        """Blocking variant, kept for compatibility with the old entry point."""
        host = kwargs.pop("host", "0.0.0.0")
        port = kwargs.pop("port", config.get_application_int("port", 5000))
        self.start(host=host, port=port)
        while self._server is not None:
            threading.Event().wait(1)

    def get_app(self):
        return self.app

