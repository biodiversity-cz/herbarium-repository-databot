import argparse
import queue
import threading
from bots.DatabaseConnectionTestDatabot import DatabaseConnectionTestDatabot
from bots.NoReferenceImageMetricsDatabot import NoReferenceImageMetricsDatabot
from core.BotScheduler import BotScheduler
from core.WorkerPool import WorkerPool
from core.JobStore import JobStore
from web.app import BotUI
from config import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bot", nargs="?", help="Run only this bot")
    args = parser.parse_args()

    available_bots = {
        DatabaseConnectionTestDatabot.NAME: DatabaseConnectionTestDatabot,
        NoReferenceImageMetricsDatabot.NAME: NoReferenceImageMetricsDatabot,
    }

    if args.bot:
        available_bots[args.bot]().run()
        return

    job_queue = queue.Queue()
    job_store = JobStore()

    # Worker
    pool = WorkerPool(job_queue, job_store)
    pool.start()

    # Scheduler
    scheduler = BotScheduler(job_queue, available_bots)
    scheduler.start()

    # Flask
    ui = BotUI(job_store, scheduler)
    threading.Thread(target=lambda: ui.run(port=config.get_application_config('port', 5000)), daemon=True).start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        scheduler.stop()
        pool.stop()


if __name__ == "__main__":
    main()
