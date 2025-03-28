import logging
import os.path
import time
from datetime import datetime
from dataclasses import dataclass

# for error handler
import re
from collections import deque
from functools import cached_property

from reloadmanager.arcion.replicant_config_builder import ReplicantConfigBuilder
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.arcion.cli_runner import run_cli_cmd


@dataclass(frozen=True)
class SnapshotMetrics:
    start: float
    end: float
    num_records: int

    @property
    def duration(self) -> float:
        return (self.end - self.start) / 60


class ReplicantRunError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class ReplicantRunner(LoggingMixin):

    def __init__(self,
                 builder: ReplicantConfigBuilder,
                 replicant_path: str | None = None):
        self.replicant_path: str = replicant_path or "/arcion/replicant-cli/bin/replicant"
        self.builder: ReplicantConfigBuilder = builder
        self.error_log_path: str = f"/arcion/replicant-cli/data/{self.builder.id.lower()}/error_trace.log"
        self.log_file: str = ""

    @cached_property
    def error(self) -> str:

        if not os.path.exists(self.error_log_path):
            logging.debug(f"No error_trace.log found in {self.error_log_path}")
            return ""

        with open(self.error_log_path, "r") as f:
            error_re: re.Pattern = re.compile(
                r"Error running query|HiveSQLException|DeltaAnalysisException|FAILED: Execution Error|"
                r"Failed to initialize pool"
            )
            unique_errors: set[str] = set([line.strip() for line in f if error_re.search(line)])

        if unique_errors:
            logging.debug(f"Errors found...{str(unique_errors)}")
            return unique_errors.pop()
        return ""

    @cached_property
    def num_records(self) -> int:
        if not os.path.exists(self.log_file):
            raise Exception(f"No log file found: {self.log_file}")

        # open the file and go to the end, only keeping 10 lines in memory at a time
        with open(self.log_file, "r") as f:
            last_10_lines: list[str] = [line.strip() for line in deque(f, 10)]

        if "replicant existed with error code" in last_10_lines[-1]:
            return 0

        row_count_re: re.Pattern = re.compile(r"[^ ]* +([0-9]+) +.*")
        num_records: str = next(
            (row_count_re.match(s).groups()[0] for s in reversed(last_10_lines) if row_count_re.match(s)),
            None
        )
        if not num_records:
            raise Exception(f"Issue parsing log file: {str(last_10_lines)}")

        return int(num_records)

    def handle_failure(self, failure: bool, elapsed_minutes):
        if failure | bool(self.error):
            if self.error:
                if self.num_records:
                    self.logger.info(f"Failure: duration {elapsed_minutes:.2f} minutes")
                    raise ReplicantRunError(self.error)
                else:
                    self.logger.warning(f"Replicant transferred 0 rows, source table may be empty. Marking as SUCCESS.")
            else:
                self.logger.info(f"Failure: duration {elapsed_minutes:.2f} minutes")
                raise ReplicantRunError(f"Unknown error, check logs at: {self.error_log_path}")

    def run_snapshot(self) -> SnapshotMetrics:

        self.builder.write_config_files()
        self.logger.info(f"\tWriting yaml to dir: {self.builder.config_dir_path}...")

        self.log_file = \
            f"{self.builder.config_dir_path}/{self.builder.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.logger.info(f"\tLogging to: {self.log_file}...")

        start: float = time.time()

        failure: bool = False
        try:
            run_cli_cmd([
                self.replicant_path, "snapshot",
                self.builder.config_file_paths.source,
                self.builder.config_file_paths.target,
                "--extractor", self.builder.config_file_paths.extractor,
                "--applier", self.builder.config_file_paths.applier,
                "--filter", self.builder.config_file_paths.filter,
                "--map", self.builder.config_file_paths.map,
                "--id", self.builder.id,
                "--truncate-existing"
            ], self.log_file)
        except Exception:
            self.logger.warning("Replicant failed")
            failure = True

        metrics = SnapshotMetrics(start=start, end=time.time(), num_records=self.num_records)

        self.handle_failure(failure, metrics.duration)
        self.logger.info(f"Success: duration {metrics.duration:.2f} minutes")

        return metrics
