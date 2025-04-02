import os
import time
from threading import Event, Lock

from reloadmanager.batch_loader.batch_queue import BatchQueue
from reloadmanager.batch_loader.input_record import InputRecord
from reloadmanager.batch_loader.bulk_loader_thread import BulkLoaderThread
from reloadmanager.utils.avoid_window import AvoidWindow
from reloadmanager.mixins.logging_mixin import LoggingMixin


class BatchLoader(LoggingMixin):
    def __init__(self,
                 input_csv: str,
                 output: str,
                 catalog: str,
                 tpt_threads: int = 8,
                 writenos_threads: int = 2,
                 avoid_window_utc: str = "6-18",
                 lock_rows: bool = True):

        self.input_csv_path = input_csv
        self.output: str = output
        self.catalog: str = catalog
        self.threads: dict = {"TPT": tpt_threads, "WriteNOS": writenos_threads}
        self.run_name: str = os.path.basename(input_csv).rsplit(".", 1)[0]
        self.avoid_window: AvoidWindow | None = AvoidWindow(avoid_window_utc) if "-" in avoid_window_utc else None
        self.lock_rows_default: bool = lock_rows
        self.input: list[InputRecord] = self.read_batch_input()
        self.queue = BatchQueue(f"/home/arcion/batch_loads/sqlite/{self.run_name}.db")
        self.stop_signal: Event = Event()
        self.output_lock: Lock = Lock()
        self.log_lock: Lock = Lock()

    def read_batch_input(self) -> list[InputRecord]:
        with open(self.input_csv_path, "r") as f:
            tables = [InputRecord.from_csv(
                line=line.strip(),
                catalog=self.catalog,
                lock_row_default=self.lock_rows_default
            ) for line in f]
        self.logger.info(f"Found {len(tables)} tables to load...")
        return tables

    def create_output_file(self):
        with open(self.output, 'w') as file:
            self.logger.info(f"Creating report and placing at {self.output}...")
            file.write("TABLE,STRATEGY,STATUS,START,END,DURATION_MINS,NUM_RECORDS,ERROR\n")

    def create_workers(self, strategy, count) -> list[BulkLoaderThread]:
        if count > 0:
            self.logger.info(f"Creating {count} {strategy} threads...")
            threads = [
                BulkLoaderThread(i, strategy, self.run_name, self.output, self.stop_signal) for i in range(count)
            ]
            for thread in threads:
                thread.start()
            return threads

    def run(self):
        self.logger.info(f"Creating and loading SQLite queue for input file {self.input_csv_path}...")
        self.queue.create_queue()
        self.queue.enqueue_input(self.input)

        self.threads["TPT"]: list[BulkLoaderThread] = self.create_workers("TPT", self.threads["TPT"])
        self.threads["WriteNOS"]: list[BulkLoaderThread] = self.create_workers("WriteNOS", self.threads["WriteNOS"])

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
                    if len(self.threads["TPT"] + self.threads["WriteNOS"]) == 0:
                        raise RuntimeError(f"{num_queued} items in queue, but no active threads.")
                time.sleep(30)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received. Sending stop signal for active threads...")
            self.stop_signal.set()

        for thread in self.threads["TPT"] + self.threads["WriteNOS"]:
            thread.join()
