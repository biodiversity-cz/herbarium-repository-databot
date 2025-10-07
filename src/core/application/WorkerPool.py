import threading
import logging
from src.config import config

class WorkerPool:
    def __init__(self, job_queue, job_store):
        self.job_queue = job_queue
        self.job_store = job_store
        self.num_threads = config.get_application_config('threads',3)
        self.threads = []

    def _worker(self, worker_id):
        while True:
            job = self.job_queue.get()
            if job is None:
                break
            try:
                logging.info(f"[Worker {worker_id}] Running {job.__class__.__name__}")
                run_id = self.job_store.mark_running(job.NAME)
                job.run()
                logging.info(f"[Worker {worker_id}] Finished")
            except Exception as e:
                logging.exception(f"[Worker {worker_id}] Error: {e}")
                self.job_store.mark_failed(job.NAME, run_id, e)
            finally:
                self.job_store.mark_finished(job.NAME, run_id )
                self.job_queue.task_done()

    def start(self):
        for i in range(self.num_threads):
            t = threading.Thread(target=self._worker, args=(i,), daemon=True)
            t.start()
            self.threads.append(t)

    def stop(self):
        for _ in self.threads:
            self.job_queue.put(None)
        for t in self.threads:
            t.join()
