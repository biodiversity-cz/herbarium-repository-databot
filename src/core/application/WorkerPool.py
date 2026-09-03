import logging
import queue
import threading
import time

from config import config
from core.application.BotJob import BotJob

# Sentinel put into the queue by stop() to wake workers up immediately.
STOP = None


class WorkerPool:
    """Thread pool executing queued BotJob objects.

    Hardening compared to the first version:

    * jobs are constructed here (inside the try block), so a bot that cannot
      even be built is reported as a failed run instead of killing a worker;
    * ``BaseException`` is caught - a bot that raises SystemExit (sys.exit())
      or KeyboardInterrupt no longer takes the worker thread with it, which
      previously also skipped ``task_done()``;
    * ``task_done()`` and the job-store bookkeeping always run;
    * ``stop()`` is bounded, so a stuck job cannot hang the shutdown.
    """

    POLL_INTERVAL_SECONDS = 0.5

    def __init__(self, job_queue, job_store, on_job_finished=None):
        self.job_queue = job_queue
        self.job_store = job_store
        # Optional callback(bot_name) used by the scheduler to release its
        # "already queued" marker.
        self.on_job_finished = on_job_finished
        self.num_threads = max(1, config.get_application_int("threads", 3))
        self.shutdown_timeout = float(config.get_application_int("worker_shutdown_timeout", 30))
        self.threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    @staticmethod
    def _job_name(job) -> str:
        """Bot name of a queued item (BotJob, or a bot object for compatibility)."""
        name = getattr(job, "bot_name", None)
        if name:
            return name
        return getattr(job, "NAME", job.__class__.__name__)

    def _execute(self, worker_id: int, job) -> None:
        bot_name = self._job_name(job)
        run_id = None
        try:
            logging.info("[Worker %s] Running %s", worker_id, bot_name)
            # Registered before the bot is built, so a bot that cannot even be
            # constructed still shows up as a failed run in the status output.
            run_id = self.job_store.mark_running(bot_name)
            bot = job.create_bot() if isinstance(job, BotJob) else job
            bot.run()
            self.job_store.mark_finished(bot_name, run_id)
            logging.info("[Worker %s] Finished %s", worker_id, bot_name)
        except BaseException as e:  # SystemExit and KeyboardInterrupt included
            logging.exception("[Worker %s] Error in %s: %s", worker_id, bot_name, e)
            if run_id is not None:
                try:
                    self.job_store.mark_failed(bot_name, run_id, e)
                except Exception:
                    logging.exception("[Worker %s] Could not record the failure of %s", worker_id, bot_name)
        finally:
            if self.on_job_finished is not None:
                try:
                    self.on_job_finished(bot_name)
                except Exception:
                    logging.exception("[Worker %s] on_job_finished callback failed for %s", worker_id, bot_name)

    def _worker(self, worker_id: int):
        while not self._stop_event.is_set():
            try:
                job = self.job_queue.get(timeout=self.POLL_INTERVAL_SECONDS)
            except queue.Empty:
                continue

            try:
                if job is STOP:
                    return
                self._execute(worker_id, job)
            finally:
                # Exactly once per retrieved item, whatever happened above.
                self.job_queue.task_done()

    def start(self):
        if self.threads:
            return
        self._stop_event.clear()
        for i in range(self.num_threads):
            thread = threading.Thread(
                target=self._worker, args=(i,), name=f"databot-worker-{i}", daemon=True
            )
            thread.start()
            self.threads.append(thread)
        logging.info("Started %s worker(s)", self.num_threads)

    def stop(self, timeout: float | None = None):
        """Ask workers to finish and wait for them up to ``timeout`` seconds."""
        drain_budget = self.shutdown_timeout if timeout is None else float(timeout)
        logging.info(
            "Stopping %s worker(s), queue depth %s, drain budget %.0fs",
            len(self.threads), self.job_queue.qsize(), drain_budget
        )
        self._stop_event.set()

        for _ in self.threads:
            try:
                self.job_queue.put(STOP, timeout=1.0)
            except queue.Full:
                logging.warning("Job queue still full while stopping - workers use the stop flag")
                break

        deadline = time.monotonic() + max(0.0, drain_budget)
        for thread in self.threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(remaining)

        alive = [thread.name for thread in self.threads if thread.is_alive()]
        if alive:
            logging.warning(
                "Workers still busy after %.0fs (they are daemon threads): %s",
                drain_budget, ", ".join(alive)
            )
        self.threads = [thread for thread in self.threads if thread.is_alive()]

    def stats(self) -> dict:
        """Worker counters for the status endpoint."""
        return {
            "workers": self.num_threads,
            "alive": sum(1 for thread in self.threads if thread.is_alive()),
            "stopping": self._stop_event.is_set(),
            "queue_depth": self.job_queue.qsize(),
        }

