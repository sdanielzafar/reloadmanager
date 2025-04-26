import time
from functools import cached_property

from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_config_builder import ReplicantConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner, ReplicantRunError
from reloadmanager.writenos.writenos_runner import WriteNOSRunner, WritenosRunError
from reloadmanager.writenos.writenos_config_builder import WriteNOSConfigBuilder
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.table_loader.report_record import ReportRecord


class TableReloader(LoggingMixin):
    def __init__(self,
                 source_table: str,
                 target_table: str,
                 where_clause: str,
                 strategy: str,
                 engine: str,
                 lock_rows: bool,
                 config_dir_path: str):
        self.source_table: str = source_table
        self.target_table: str = target_table
        self.where_clause: str = where_clause
        self.strategy: str = strategy
        self.engine: str = engine
        self.lock_rows: bool = lock_rows
        self.config_dir_path: str = config_dir_path

    @cached_property
    def builder(self) -> ReplicantConfigBuilder | WriteNOSConfigBuilder:
        match self.engine:
            case "arcion":
                return NxpConfigBuilder(
                    source_table=self.source_table,
                    target_table=self.target_table,
                    strategy=self.strategy,
                    lock_rows=self.lock_rows,
                    config_dir_path=self.config_dir_path
                )
            case "native":
                return WriteNOSConfigBuilder(
                    source_table=self.source_table,
                    target_table=self.target_table,
                    where_clause=self.where_clause
                )
            case _:
                raise ValueError("Invalid migration engine, must be 'arcion' or 'native'")

    @cached_property
    def runner(self) -> ReplicantRunner | WriteNOSRunner:
        match self.engine:
            case "arcion":
                return ReplicantRunner(builder=self.builder)
            case "native":
                return WriteNOSRunner(builder=self.builder)

    def reload(self) -> ReportRecord:
        status = "SUCCESS"
        error = ""
        num_records: int = 0
        start: float = time.time()
        try:
            self.runner.run_snapshot()
            num_records = self.runner.num_records
        except (ReplicantRunError, WritenosRunError) as e:
            status = "FAILED"
            self.logger.error(str(e))
            error = str(e) or ""
        finally:
            end: float = time.time()

        report_record = ReportRecord(self.source_table, self.strategy, status, start, end, num_records, error)
        self.logger.info(f"{status}: duration {report_record.duration:.2f} minutes")
        return report_record
