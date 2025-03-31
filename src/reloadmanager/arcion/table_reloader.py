import time
from datetime import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner, ReplicantRunError
from reloadmanager.mixins.logging_mixin import LoggingMixin


@dataclass(frozen=True)
class ReportRecord:
    table: str
    status: str
    start: float
    end: float
    num_records: int
    error: str

    @property
    def duration(self) -> float:
        return (self.end - self.start) / 60

    @staticmethod
    def format_mst(t: float) -> str:
        return datetime.fromtimestamp(t, ZoneInfo("America/Phoenix")).strftime('%-m/%-d/%y %-I:%M %p')

    def __str__(self):
        return f"{self.table},{self.status},{self.format_mst(self.start)},{self.format_mst(self.end)}," \
               f"{self.duration:.2f},{self.num_records},{self.error.strip()}\n"


class TableReloader(LoggingMixin):
    def __init__(self, source_table: str, target_table: str, method: str, lock_rows: bool, config_dir_path: str):
        self.source_table: str = source_table
        self.target_table: str = target_table
        self.method: str = method
        self.lock_rows: bool = lock_rows
        self.config_dir_path: str = config_dir_path

    def handle_error(self, replicant_error: str, num_records: int, duration: float, replicant_error_log_path: str):
        if replicant_error and num_records:
            self.logger.info(f"Failure: duration {duration:.2f} minutes")
            raise ReplicantRunError(replicant_error)
        elif replicant_error:
            self.logger.warning(f"Replicant transferred 0 rows, source table may be empty. Marking as SUCCESS.")
        else:
            self.logger.info(f"Failure: duration {duration:.2f} minutes")
            raise ReplicantRunError(f"Unknown error, check logs at: {replicant_error_log_path}")

    def reload(self) -> ReportRecord:
        builder: NxpConfigBuilder = NxpConfigBuilder(
            source_table=self.source_table,
            target_table=self.target_table,
            method=self.method,
            lock_rows=self.lock_rows,
            config_dir_path=self.config_dir_path
        )

        replicant: ReplicantRunner = ReplicantRunner(builder=builder)

        status = "SUCCESS"
        error = ""
        num_records: int = 0
        start: float = time.time()
        try:
            replicant.run_snapshot()
            num_records = replicant.num_records
        except ReplicantRunError as e:
            status = "FAILED"
            self.logger.error(str(e))
            error = str(e) or ""
        finally:
            end: float = time.time()

        report_record = ReportRecord(self.source_table, status, start, end, num_records, error)
        self.logger.info(f"{status}: duration {report_record.duration:.2f} minutes")
        return report_record
