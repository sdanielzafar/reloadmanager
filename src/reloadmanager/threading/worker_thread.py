import os
from abc import ABC, abstractmethod
from threading import Thread, Event
import traceback

from reloadmanager.arcion.table_reloader import TableReloader, ReportRecord
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.threading.synchronization import LogLock


class WorkerThread(Thread, ABC, LoggingMixin):
    def __init__(self, thread_id: int, strategy: str, run_name: str, stop_signal: Event):
        super().__init__()
        self.strategy: str = strategy
        self.thread_id: str = f"{strategy.lower()}_{str(thread_id)}"
        self.logger.info(f"Thread {thread_id} starting...")
        self.run_name: str = run_name
        self.stop_thread: bool = False
        self.stop_signal = stop_signal

    def run(self):
        try:
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
            os.path.expanduser(f"~/batch_loads/configs/{self.run_name}")
        )
        return reloader.reload()
