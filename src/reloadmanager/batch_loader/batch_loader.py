import os
from dataclasses import dataclass
import sqlite3
import time
from threading import Thread, Event, Lock

from reloadmanager.utils.avoid_window import AvoidWindow
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.arcion.table_reloader import TableReloader, ReportRecord


@dataclass(frozen=True)
class InputRecord:
    source: str
    target: str
    strategy: str
    lock_rows: bool

    @classmethod
    def from_csv(cls, line: str, lock_row_default: bool):
        def valid_table(s: str, n: int):
            if len(s.split(".")) != n:
                raise ValueError(f"Table '{s}' must have {n} namespaces in the input config file")
            return s

        source, target, method, *lock_rows_str = line.split(",")
        if method not in ["TPT", "WriteNOS"]:
            raise ValueError(f"Input line: {line} has invalid method. Should be 'TPT' or 'WriteNOS'")

        lock_rows = lock_row_default
        if lock_rows_str:
            if lock_rows_str[0].strip().lower() not in ["true", "false"]:
                raise ValueError(f"Input line: {line} has invalid lock rows. Should be 'true' or 'false'")
            lock_rows = lock_rows_str[0].strip().lower() == "true"
        return cls(valid_table(source, 2), valid_table(target, 3), method, lock_rows)


class BatchLoader(LoggingMixin):
    def __init__(self,
                 input_csv: str,
                 output: str,
                 tpt_threads: int = 8,
                 writenos_threads: int = 2,
                 avoid_window_utc: str = "6-18",
                 lock_rows: bool = True,
                 log_level: str = "INFO"):

        self.input_csv_path = input_csv
        self.threads: dict = {"TPT": tpt_threads, "WriteNOS": writenos_threads}
        self.run_name: str = os.path.basename(input_csv).rsplit(".", 1)[0]
        self.output: str = output
        self.avoid_window: AvoidWindow | None = AvoidWindow(avoid_window_utc) if "-" in avoid_window_utc else None
        self.lock_rows_default: bool = lock_rows
        self.logger.set_logger_level(log_level)
        self.input: list[InputRecord] = self.read_batch_input()
        self.db_path = f"home/arcion/batch_loads/sqlite/{self.run_name}.db"
        self.stop_signal: Event = Event()
        self.output_lock: Lock = Lock()

    def read_batch_input(self) -> list[InputRecord]:
        with open(self.input_csv_path, "r") as f:
            tables = [InputRecord.from_csv(line.strip(), self.lock_rows_default) for line in f]
        self.logger.info(f"Found {len(tables)} tables to load...")
        return tables

    def create_queue(self):

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS BULK_QUEUE (
                source_table TEXT PRIMARY KEY,
                target_table TEXT,
                strategy TEXT,
                lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                status CHAR(1),
                priority INTEGER
            )
        """)

    def enqueue_input(self):
        len_input: int = len(self.input)
        priorities = reversed(range(len_input))
        input_data = (
            (i.source, i.target, i.strategy, i.lock_rows, p, 'Q') for i, p in zip(self.input, priorities)
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
            INSERT INTO BULK_QUEUE (source_table, target_table, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """, input_data)

    # def poll_queue(self, strategy: str) -> tuple:
    #     with sqlite3.connect(self.db_path) as conn:
    #         cursor = conn.cursor()
    #         cursor.execute("""
    #         SELECT source_table, target_table, lock_rows FROM BULK_QUEUE
    #         WHERE status = 'Q'
    #         AND strategy = ?
    #         ORDER BY priority DESC LIMIT 1
    #         """, (strategy,))
    #         row = cursor.fetchone()
    #
    #     if not row:
    #         return ()
    #
    #     source_table, target_table, lock_rows = row
    #
    #     with sqlite3.connect(self.db_path) as conn:
    #         cursor = conn.cursor()
    #         cursor.execute("""
    #         UPDATE BULK_QUEUE
    #         SET status = 'R'
    #         WHERE source_table = ?
    #         """, (source_table,))
    #
    #     return source_table, target_table, lock_rows

    def poll_queue(self, strategy: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE BULK_QUEUE
                SET status = 'R'
                WHERE rowid IN (
                    SELECT rowid
                    FROM BULK_QUEUE
                    WHERE status = 'Q'
                      AND strategy = ?
                    ORDER BY priority DESC
                    LIMIT 1
                )
                RETURNING source_table, target_table, lock_rows
            """, (strategy,))
            row = cursor.fetchone()

        if row:
            source_table, target_table, lock_rows = row
            return source_table, target_table, lock_rows
        else:
            return ()

    # No row found for this strategy.

    def dequeue(self, source_table: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE FROM BULK_QUEUE
            WHERE source_table = ?
            AND status = 'R'
            """, (source_table,))

    def queue_is_empty(self) -> bool:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT COUNT(*) FROM BULK_QUEUE 
            """)
            return cursor.fetchone()[0] == 0

    def worker_thread(self, thread_id: int, strategy: str):
        thread_id = f"{strategy.lower()}_{str(thread_id)}"
        self.logger.info(f"Thread {thread_id} starting.")
        while not self.stop_signal.is_set():
            task: tuple = self.poll_queue(strategy)

            if task:
                source_table, target_table, lock_rows = task
                try:
                    # reload the table
                    reloader: TableReloader = TableReloader(
                        source_table, target_table, strategy, lock_rows,
                        os.path.expanduser(f"~/batch_loads/configs/{self.run_name}")
                    )
                    result: ReportRecord = reloader.reload()
                    # write to the csv
                    self.append_output_row(result)
                    # remove table from queue
                    self.dequeue(source_table)
                    self.logger.info(f"Thread {thread_id} reloaded table '{source_table}' with result: {result}")
                except Exception as e:
                    self.logger.warning(f"Thread {thread_id} failed to reload '{source_table}': {e}")
            else:
                self.logger.info(f"Thread {thread_id} found no tasks. Sleeping...")
                time.sleep(2)

        self.logger.info(f"Thread {thread_id} received stop signal. Exiting.")

    def create_output_file(self):
        with open(self.output, 'w') as file:
            self.logger.info(f"Creating report and placing at {self.output}...")
            file.write("TABLE,STATUS,START,END,DURATION_MINS,NUM_RECORDS,ERROR\n")

    def append_output_row(self, record: ReportRecord):
        with self.output_lock:
            with open(self.output, 'a') as file:
                file.write(str(record))

    def run(self):

        self.create_queue()
        self.enqueue_input()

        tpt_threads: list[Thread] = []
        for i in range(self.threads["TPT"]):
            thread = Thread(target=self.worker_thread, args=(i, "TPT",))
            thread.start()
            tpt_threads.append(thread)

        writenos_threads: list[Thread] = []
        for i in range(self.threads["WriteNOS"]):
            thread = Thread(target=self.worker_thread, args=(i, "WriteNOS",))
            thread.start()
            writenos_threads.append(thread)

        try:
            while True:
                if self.queue_is_empty():
                    self.logger.info("All tasks completed. Sending stop signal...")
                    self.stop_signal.set()
                    break
                time.sleep(15)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received. Sending stop signal for active threads...")
            self.stop_signal.set()

        for thread in tpt_threads + writenos_threads:
            thread.join()
