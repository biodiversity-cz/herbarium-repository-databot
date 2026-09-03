import logging
import queue
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import config
from core.application.BotJob import BotJob


class BotScheduler:
    """Cron style enqueueing of databots.

    Two rules keep the queue (and therefore the database) from exploding:

    * only a lightweight :class:`BotJob` is queued, no constructed bot;
    * a bot that is still waiting in the queue is never queued twice.

    APScheduler is additionally configured with ``max_instances=1`` and
    ``coalesce=True`` so a long running bot cannot overlap with itself and a
    stopped process does not fire all missed ticks at once on restart.
    """

    # A job that could not start within this window is skipped, not replayed.
    MISFIRE_GRACE_SECONDS = 300

    def __init__(self, job_queue, bot_registry: dict):
        self.config = config
        self.job_queue = job_queue
        self.bot_registry = bot_registry
        self.scheduler = BackgroundScheduler(
            job_defaults={
                "max_instances": 1,
                "coalesce": True,
                "misfire_grace_time": self.MISFIRE_GRACE_SECONDS,
            }
        )
        self._lock = threading.Lock()
        self._queued: set[str] = set()
        self._started = False

    def _enqueue(self, bot_cls):
        """
        Enqueue a bot for execution with its configuration.

        Args:
            bot_cls: The bot class to enqueue; instantiated by the worker.
        """
        bot_name = bot_cls.NAME
        bot_config = self.config.get_bot_config(bot_name) or {}

        with self._lock:
            if bot_name in self._queued:
                logging.warning("Bot '%s' is still waiting in the queue - skipping this trigger", bot_name)
                return
            self._queued.add(bot_name)

        try:
            # Never block the scheduler thread waiting for a free slot.
            self.job_queue.put_nowait(BotJob(bot_name=bot_name, bot_cls=bot_cls, config=bot_config))
            logging.info("Enqueueing %s with config: %s", bot_cls.__name__, bot_config)
        except queue.Full:
            self._forget(bot_name)
            logging.error(
                "Job queue is full (maxsize=%s) - dropping scheduled run of '%s'",
                self.job_queue.maxsize, bot_name
            )
        except Exception as e:
            self._forget(bot_name)
            logging.exception("Failed to enqueue '%s': %s", bot_name, e)

    def _forget(self, bot_name: str) -> None:
        with self._lock:
            self._queued.discard(bot_name)

    def mark_completed(self, bot_name: str) -> None:
        """Allow the bot to be scheduled again (called by the worker pool)."""
        self._forget(bot_name)

    def get_queued(self) -> list[str]:
        with self._lock:
            return sorted(self._queued)

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

    def is_running(self) -> bool:
        return self._started

    def start(self):
        if self._started:
            return
        logging.info("Starting scheduler...")
        self.schedule_all()
        self.scheduler.start()
        self._started = True

    def stop(self):
        if not self._started:
            return
        logging.info("Stopping scheduler...")
        try:
            # Never wait for running jobs - Kubernetes only gives us so long.
            self.scheduler.shutdown(wait=False)
        except Exception as e:
            logging.warning("Scheduler shutdown failed: %s", e)
        self._started = False

