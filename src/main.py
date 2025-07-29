import argparse
import queue
import threading
from bots.test_connection import ConnectionTester
from core.BotScheduler import BotScheduler
from core.WorkerPool import WorkerPool

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bot", nargs="?", help="Run only this bot")
    args = parser.parse_args()

    available_bots = {
        ConnectionTester.NAME: ConnectionTester,
    }

    if args.bot:
        available_bots[args.bot]().run()
        return

    job_queue = queue.Queue()

    pool = WorkerPool(job_queue, num_threads=2)
    pool.start()

    scheduler = BotScheduler(job_queue, available_bots)
    scheduler.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        scheduler.stop()
        pool.stop()


if __name__ == "__main__":
    main()