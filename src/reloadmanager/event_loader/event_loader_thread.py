from threading import Lock, Event
import time

from reloadmanager.arcion.table_reloader import ReportRecord
from reloadmanager.event_loader.event_queue import EventQueue
from reloadmanager.threading.worker_thread import WorkerThread


class EventLoaderThread(WorkerThread):
    def __init__(self, thread_id: int, strategy: str, run_name: str, sqlite_path: str, stop_signal: Event):
        super().__init__(thread_id, strategy, run_name, stop_signal)
        self.queue: EventQueue = EventQueue(sqlite_path)
        self.output_lock: Lock = Lock()

    # only pick up if 'Q' and priority > 0

    def task(self):
        task: tuple = self.queue.poll_queue(self.strategy)

        if not task:
            self.logger.info(f"Thread {self.thread_id} found no queued tables. Sleeping...")
            time.sleep(60)
            return None

        source_table, target_table, lock_rows, event_time = task
        duration, end_time = 0.0, 0.0
        try:
            self.logger.info(f"Thread {self.thread_id} picked up {source_table}...")
            # reload the table
            result: ReportRecord = self.reload_table(source_table, target_table, lock_rows)

            self.logger.info(f"Thread {self.thread_id} reloaded table '{source_table}'")
            duration, end_time = result.duration, result.end
        except Exception as e:
            self.logger.error(f"CRITICAL FAILURE: Thread {self.thread_id} failed to reload '{source_table}': {e}")
        finally:
            # remove table from queue
            self.queue.dequeue(source_table, event_time, end_time, duration)

    def report(self, record: ReportRecord):
        pass
