import time

from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner, ReplicantRunError
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.table_loader.report_record import ReportRecord


class TableReloader(LoggingMixin):
    def __init__(self,
                 source_table: str,
                 target_table: str,
                 strategy: str,
                 lock_rows: bool,
                 config_dir_path: str):
        self.source_table: str = source_table
        self.target_table: str = target_table
        self.strategy: str = strategy
        self.lock_rows: bool = lock_rows
        self.config_dir_path: str = config_dir_path

    def reload(self) -> ReportRecord:
        builder: NxpConfigBuilder = NxpConfigBuilder(
            source_table=self.source_table,
            target_table=self.target_table,
            strategy=self.strategy,
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

        report_record = ReportRecord(self.source_table, self.strategy, status, start, end, num_records, error)
        self.logger.info(f"{status}: duration {report_record.duration:.2f} minutes")
        return report_record
