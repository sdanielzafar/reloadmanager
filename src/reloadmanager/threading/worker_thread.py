import os
from abc import ABC, abstractmethod
from threading import Thread, Event
import traceback
import time

from reloadmanager.table_loader.table_reloader import TableReloader
from reloadmanager.table_loader.report_record import ReportRecord
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.threading.synchronization import LogLock


class WorkerThread(Thread, ABC, LoggingMixin):
    def __init__(self, thread_id: int, strategy: str, config_dir_path: str, stop_signal: Event):
        super().__init__()
        self.strategy: str = strategy
        self.thread_id: str = f"{strategy.lower()}_{str(thread_id)}"
        self.logger.info(f"Thread {thread_id} starting...")
        self.config_dir_path: str = config_dir_path
        self.stop_thread: bool = False
        self.stop_signal = stop_signal

    def run(self):
        try:
            time.sleep(10)
            while not self.stop_signal.is_set():
                self.task()
                if self.stop_thread:
                    break
            if self.stop_signal.is_set():
                self.logger.info(f"Thread {self.thread_id} received stop signal. Exiting.")
        except Exception:
            with LogLock.lock:
                traceback.print_exc()

    @abstractmethod
    def task(self):
        pass

    @abstractmethod
    def report(self, result: ReportRecord):
        pass

    def reload_table(self, source_table: str, target_table: str, lock_rows: bool) -> ReportRecord:
        reloader: TableReloader = TableReloader(
            source_table, target_table, self.strategy, bool(lock_rows),
            os.path.expanduser(self.config_dir_path)
        )
        return reloader.reload()
