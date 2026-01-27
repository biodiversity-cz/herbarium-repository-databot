from flask import Flask, jsonify, request, send_file, abort
from config import config
from services.chart_service import ChartService

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

        @self.app.route("/chart/<metric>")
        def chart(metric: str):
            """
            Vygeneruje histogram pro zadanou metriku a červenou linku pro highlight.
            Parametry GET:
                highlight: hodnota červené linky (povinné)
                bins: počet binů (volitelné, default 10)
            """
            highlight = request.args.get("highlight", type=float)
            bins = request.args.get("bins", default=10, type=int)

            if highlight is None:
                return abort(400, description="Missing 'highlight' query parameter")

            service = ChartService()
            # img_bytes = service.generate_histogram(metric=metric, highlight=highlight, bins=bins)
            img_bytes = service.generate_boxplot(metric=metric, highlight=highlight)

            if img_bytes is None:
                return abort(404, description=f"No data found for metric {metric}")

            return send_file(img_bytes, mimetype="image/png")

    def run(self, **kwargs):
        self.app.run(**kwargs)

    def get_app(self):
        return self.app
