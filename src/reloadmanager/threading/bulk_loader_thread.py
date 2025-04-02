from threading import Lock

from reloadmanager.arcion.table_reloader import ReportRecord
from reloadmanager.batch_loader.batch_queue import BatchQueue
from reloadmanager.threading.synchronization import StopSignal
from reloadmanager.threading.worker_thread import WorkerThread


class BulkLoaderThread(WorkerThread):
    def __init__(self, thread_id: int, strategy: str, run_name: str, output_path: str, stop_signal: StopSignal):
        super().__init__(thread_id, strategy, run_name, stop_signal)
        self.output_path: str = output_path
        self.queue: BatchQueue = BatchQueue(f"/home/arcion/batch_loads/sqlite/{run_name}.db")
        self.output_lock: Lock = Lock()

    def task(self):
        task: tuple = self.queue.poll_queue(self.strategy)

        if task:
            source_table, target_table, lock_rows = task
            try:
                self.logger.info(f"Thread {self.thread_id} picked up {source_table}...")
                # reload the table
                result: ReportRecord = self.reload_table(source_table, target_table, lock_rows)
                # write to the csv
                self.report(result)
                self.logger.info(f"Thread {self.thread_id} reloaded table '{source_table}'")
            except Exception as e:
                self.logger.error(f"CRITICAL FAILURE: Thread {self.thread_id} failed to reload '{source_table}': {e}")
            finally:
                # remove table from queue
                self.queue.dequeue(source_table)
        else:
            self.logger.info(f"Thread {self.thread_id} found no tasks. Exiting...")
            self.stop_thread = True

    def report(self, record: ReportRecord):
        with self.output_lock:
            with open(self.output_path, 'a') as file:
                file.write(str(record))
