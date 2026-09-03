import argparse
import logging
import os
import queue
import signal
import sys
import threading

from bots.implementations.database_connection_test_databot import DatabaseConnectionTestDatabot
from bots.implementations.hespi_bbox_detector import HespiBboxDetectorDatabot
from bots.implementations.no_reference_image_metrics_databot import NoReferenceImageMetricsDatabot
from bots.implementations.cetaf_metadata_databot import CetafMetadataDatabot
from bots.implementations.vouvis_metadata_databot import VouvisDatabot
from core.application.BotScheduler import BotScheduler
from core.application.WorkerPool import WorkerPool
from core.application.JobStore import JobStore
from core.infrastructure.database.connection_pool import close_pool
from web.app import BotUI
from config import config

logger = logging.getLogger(__name__)

# Bot registry: key must match NAME attribute in bot class AND config.yaml
AVAILABLE_BOTS = {
    DatabaseConnectionTestDatabot.NAME: DatabaseConnectionTestDatabot,
    NoReferenceImageMetricsDatabot.NAME: NoReferenceImageMetricsDatabot,
    CetafMetadataDatabot.NAME: CetafMetadataDatabot,
    HespiBboxDetectorDatabot.NAME: HespiBboxDetectorDatabot,
    VouvisDatabot.NAME: VouvisDatabot,
}


def configure_logging():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s",
    )


def log_configuration() -> None:
    """Log what the process really got - a missing value has to be visible here.

    Values that come out as None used to be discovered only much later by an
    unrelated TypeError deep inside a bot.
    """
    logger.info(
        "Config: db %s:%s/%s, pool min=%s max=%s, workers=%s, web port=%s",
        config.get_database_config("host", "localhost"),
        config.get_database_config("port", 5433),
        config.get_database_config("database", "jacq_dev"),
        config.get_pool_config("min", 1),
        config.get_pool_config("max", 5),
        config.get_application_int("threads", 3),
        config.get_application_int("port", 5000),
    )
    logger.info(
        "S3: endpoint=%s, thumb bucket=%s, fullsize bucket=%s",
        config.get_s3_config("endpoint_url"),
        config.get_s3_config("thumb_bucket"),
        config.get_s3_config("fullsize_bucket"),
    )

    missing_s3 = config.missing_s3_config()
    if missing_s3:
        logger.error(
            "Image bots cannot download from S3 - missing %s "
            "(set s3.<key> in config.yaml or env S3_<KEY>)",
            ", ".join(missing_s3),
        )


def run_single_bot(bot_name: str) -> int:
    """Run one bot immediately (one-off Kubernetes Job style).

    Any problem propagates, so the container exits with a non-zero code instead
    of silently reporting success.
    """
    bot_cls = AVAILABLE_BOTS.get(bot_name)
    if bot_cls is None:
        print(f"Unknown bot: {bot_name}")
        print(f"Available bots: {', '.join(AVAILABLE_BOTS.keys())}")
        return 2

    # Config is empty on purpose: one-off runs use the same defaults as before.
    bot_cls(config={}).run()
    return 0


def shutdown(ui, scheduler, pool) -> None:
    """Best effort, bounded shutdown - every step logs instead of throwing."""
    logger.info("Shutting down: scheduler, workers, web, database pool")

    for name, action in (
        ("scheduler", scheduler.stop),
        ("worker pool", pool.stop),
        ("web server", ui.stop),
        ("database pool", close_pool),
    ):
        try:
            action()
        except Exception:
            logger.exception("Error while stopping the %s", name)

    logger.info("Shutdown complete")


def serve() -> int:
    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        if stop_event.is_set():
            logger.warning("Second %s received - exiting immediately", signal.Signals(signum).name)
            os._exit(1)
        logger.info("Received %s - starting graceful shutdown", signal.Signals(signum).name)
        stop_event.set()

    for supported_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(supported_signal, handle_signal)
        except (ValueError, OSError):  # pragma: no cover - not the main thread
            logger.debug("Signal handler for %s could not be installed", supported_signal)

    # Bounded queue: a stuck worker slows the scheduler down instead of letting
    # the process grow an unbounded backlog of jobs.
    job_queue = queue.Queue(maxsize=max(1, config.get_application_int("queue_maxsize", 100)))
    job_store = JobStore()

    scheduler = BotScheduler(job_queue, AVAILABLE_BOTS)
    pool = WorkerPool(job_queue, job_store, on_job_finished=scheduler.mark_completed)
    ui = BotUI(job_store, scheduler, job_queue=job_queue, worker_pool=pool)

    try:
        pool.start()
        scheduler.start()
        ui.start(host="0.0.0.0", port=config.get_application_int("port", 5000))

        while not stop_event.wait(1.0):
            pass
    except Exception:
        logger.exception("Startup failed - shutting down")
        raise
    finally:
        shutdown(ui, scheduler, pool)

    return 0


def main() -> int:
    configure_logging()
    log_configuration()

    parser = argparse.ArgumentParser(description="Herbarium repository databots")
    parser.add_argument("bot", nargs="?", help="Run only this bot")
    args = parser.parse_args()

    if args.bot:
        return run_single_bot(args.bot)

    return serve()


if __name__ == "__main__":
    sys.exit(main())

