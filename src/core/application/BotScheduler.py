import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import config
from datetime import datetime

class BotScheduler:
    def __init__(self, job_queue, bot_registry: dict):
        self.config = config
        self.job_queue = job_queue
        self.bot_registry = bot_registry
        self.scheduler = BackgroundScheduler()

    def _enqueue(self, bot_cls):
        logging.info(f"Enqueueing {bot_cls.__name__}")
        self.job_queue.put(bot_cls())

    def schedule_all(self):
        for bot_name, bot_cls in self.bot_registry.items():
            bot_config = self.config.get_bot_config(bot_name)
            interval = bot_config.get("interval")

            if not interval:
                logging.warning(f"Bot '{bot_name}' has no interval, skipping.")
                continue

            try:
                trigger = CronTrigger.from_crontab(interval)
                self.scheduler.add_job(
                    self._enqueue,
                    trigger,
                    id=bot_name,
                    kwargs={"bot_cls": bot_cls}
                )
                logging.info(f"Scheduled bot '{bot_name}' with interval '{interval}'")
            except Exception as e:
                logging.error(f"Failed to schedule '{bot_name}': {e}")

    def get_next_runs(self):
        runs = []
        for job in self.scheduler.get_jobs():
            runs.append({
                "id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })
        return runs

    def get_bot_names(self):
        return list(self.bot_registry.keys())

    def start(self):
        logging.info("Starting scheduler...")
        self.schedule_all()
        self.scheduler.start()

    def stop(self):
        logging.info("Stopping scheduler...")
        self.scheduler.shutdown()
