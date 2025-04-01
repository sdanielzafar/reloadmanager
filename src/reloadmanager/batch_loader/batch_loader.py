import os
import time
from threading import Thread, Event, Lock
import traceback

from reloadmanager.batch_loader.batch_queue import BatchQueue
from reloadmanager.batch_loader.models import InputRecord
from reloadmanager.utils.avoid_window import AvoidWindow
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.arcion.table_reloader import TableReloader, ReportRecord


class BatchLoader(LoggingMixin):
    def __init__(self,
                 input_csv: str,
                 output: str,
                 tpt_threads: int = 8,
                 writenos_threads: int = 2,
                 avoid_window_utc: str = "6-18",
                 lock_rows: bool = True):

        self.input_csv_path = input_csv
        self.threads: dict = {"TPT": tpt_threads, "WriteNOS": writenos_threads}
        self.run_name: str = os.path.basename(input_csv).rsplit(".", 1)[0]
        self.output: str = output
        self.avoid_window: AvoidWindow | None = AvoidWindow(avoid_window_utc) if "-" in avoid_window_utc else None
        self.lock_rows_default: bool = lock_rows
        self.input: list[InputRecord] = self.read_batch_input()
        self.queue = BatchQueue(f"/home/arcion/batch_loads/sqlite/{self.run_name}.db")
        self.stop_signal: Event = Event()
        self.output_lock: Lock = Lock()
        self.log_lock: Lock = Lock()

    def read_batch_input(self) -> list[InputRecord]:
        with open(self.input_csv_path, "r") as f:
            tables = [InputRecord.from_csv(line.strip(), self.lock_rows_default) for line in f]
        self.logger.info(f"Found {len(tables)} tables to load...")
        return tables

    def safe_thread(self, thread_id: int, strategy: str):
        try:
            self.worker_thread(thread_id, strategy)
        except Exception:
            with self.log_lock:
                traceback.print_exc()

    def worker_thread(self, thread_id: int, strategy: str):
        thread_id = f"{strategy.lower()}_{str(thread_id)}"
        self.logger.info(f"Thread {thread_id} starting...")
        while not self.stop_signal.is_set():
            task: tuple = self.queue.poll_queue(strategy)

            if task:
                source_table, target_table, lock_rows = task
                try:
                    self.logger.info(f"Thread {thread_id} picked up {source_table}...")
                    # reload the table
                    reloader: TableReloader = TableReloader(
                        source_table, target_table, strategy, bool(lock_rows),
                        os.path.expanduser(f"~/batch_loads/configs/{self.run_name}")
                    )
                    result: ReportRecord = reloader.reload()
                    # write to the csv
                    self.append_output_row(result)
                    self.logger.info(f"Thread {thread_id} reloaded table '{source_table}'")
                except Exception as e:
                    self.logger.warning(f"Thread {thread_id} failed to reload '{source_table}': {e}")
                finally:
                    # remove table from queue
                    self.queue.dequeue(source_table)
            else:
                self.logger.info(f"Thread {thread_id} found no tasks. Exiting...")
                break

        if self.stop_signal.is_set():
            self.logger.info(f"Thread {thread_id} received stop signal. Exiting.")

    def create_output_file(self):
        with open(self.output, 'w') as file:
            self.logger.info(f"Creating report and placing at {self.output}...")
            file.write("TABLE,STRATEGY,STATUS,START,END,DURATION_MINS,NUM_RECORDS,ERROR\n")

    def append_output_row(self, record: ReportRecord):
        with self.output_lock:
            with open(self.output, 'a') as file:
                file.write(str(record))

    def run(self):

        self.logger.info(f"Creating and loading SQLite queue for input file {self.input_csv_path}...")
        self.queue.create_queue()
        self.queue.enqueue_input(self.input)

        self.logger.info(f"Creating {self.threads['TPT']} TPT threads...")
        tpt_threads: list[Thread] = []
        for i in range(self.threads["TPT"]):
            thread = Thread(target=self.safe_thread, args=(i, "TPT",))
            thread.start()
            tpt_threads.append(thread)

        self.logger.info(f"Creating {self.threads['WriteNOS']} WriteNOS threads...")
        writenos_threads: list[Thread] = []
        for i in range(self.threads["WriteNOS"]):
            thread = Thread(target=self.safe_thread, args=(i, "WriteNOS",))
            thread.start()
            writenos_threads.append(thread)

        self.create_output_file()
        time.sleep(5)
        try:
            while True:
                num_queued: int = len(self.queue)
                if num_queued == 0:
                    self.logger.info("All tasks picked up or completed. Sending stop signal...")
                    self.stop_signal.set()
                    break
                else:
                    self.logger.info(f"PROGRESS: {(len(self.input)-num_queued)}/{len(self.input)} tables picked up")
                time.sleep(30)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received. Sending stop signal for active threads...")
            self.stop_signal.set()

        for thread in tpt_threads + writenos_threads:
            thread.join()
