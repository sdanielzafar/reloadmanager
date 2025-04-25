import traceback
from threading import Lock, Event
import time
from datetime import datetime

from reloadmanager.table_loader.report_record import ReportRecord
from reloadmanager.clients.databricks_client_factory import get_dbx_client
from reloadmanager.clients.generic_database_client import GenericDatabaseClient
from reloadmanager.event_loader.event_queue import EventQueue
from reloadmanager.threading.worker_thread import WorkerThread


class EventLoaderThread(WorkerThread):
    def __init__(self,
                 thread_id: int,
                 strategy: str,
                 run_name: str,
                 sqlite_path: str,
                 stop_signal: Event,
                 databricks_client: GenericDatabaseClient = None):
        super().__init__(thread_id, strategy, f"~/event_loader/configs/{run_name}", stop_signal)
        self.queue: EventQueue = EventQueue(sqlite_path)
        self.output_lock: Lock = Lock()
        self.databricks_client = databricks_client or get_dbx_client()

    def wait_if_needed(self):
        messaged = False
        while True:
            current_minute = datetime.now().minute
            if current_minute > 2:
                break
            if not messaged:
                self.logger.info(f"Thread {self.thread_id} is waiting till minute 3 to proceed. Sleeping...")
                messaged = True
            time.sleep(2)

    def trigger_validation(self, source_table: str, target_table: str):
        job_id: int = 895566902612908
        s_schema, s_table = source_table.split(".")
        t_schema, t_table = target_table.split(".")[1:]
        params: dict[str, str] = {
            "source_schema":  s_schema,
            "source_table":  s_table,
            "target_schema":  t_schema,
            "target_table":  t_table,

        }
        run_id: str = self.databricks_client.trigger_job(job_id, params)
        self.logger.info(f"Successfully triggered validation job for table '{source_table}' with run_id: {run_id}")

    def task(self):

        self.wait_if_needed()

        task: tuple = self.queue.poll(self.strategy)

        if not task:
            self.logger.info(f"Thread {self.thread_id} found no queued tables. Sleeping...")
            time.sleep(60)
            return None

        source_table, target_table, lock_rows, event_time = task
        duration, end_time, n_records, status, error = 0.0, 0.0, 0, 'Failed', ""
        try:
            self.logger.info(f"Thread {self.thread_id} picked up {source_table}...")
            # reload the table
            result: ReportRecord = self.reload_table(source_table, target_table, lock_rows)

            self.logger.info(f"Thread {self.thread_id} reloaded table '{source_table}'")
            self.trigger_validation(source_table, target_table)
            duration, end_time, n_records, status, error = \
                result.duration, result.end, result.num_records, result.status, result.error
        except Exception as e:
            self.logger.error(f"CRITICAL FAILURE: Thread {self.thread_id} failed to reload '{source_table}': {e}")
            traceback.print_exc()
        finally:
            # remove table from queue
            self.queue.dequeue(source_table, event_time, end_time, duration, n_records, status, error)

    def report(self, record: ReportRecord):
        pass
