import os.path
import time
from datetime import datetime

# for error handler
import re

from reloadmanager.arcion.replicant_config_builder import ReplicantConfigBuilder
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.arcion.cli_runner import run_cli_cmd


class ReplicantRunner(LoggingMixin):

    def __init__(self,
                 builder: ReplicantConfigBuilder,
                 replicant_path: str | None = None):
        self.replicant_path: str = replicant_path or "/arcion/replicant-cli/bin/replicant"
        self.builder: ReplicantConfigBuilder = builder
        self.error_log_path: str = f"/arcion/replicant-cli/data/{self.builder.id.lower()}/error_trace.log"

    def find_error(self) -> str:

        if not os.path.exists(self.error_log_path):
            return ""

        with open(self.error_log_path, "r") as f:
            error_re: re.Pattern = re.compile(
                r"Error running query|HiveSQLException|DeltaAnalysisException|FAILED: Execution Error|"
                r"Failed to initialize pool"
            )
            unique_errors: set[str] = set([line for line in f if error_re.search(line)])

        if unique_errors:
            return unique_errors.pop()
        return ""

    class ReplicantRunError(Exception):
        def __init__(self, message: str):
            super().__init__(message)

    def run_snapshot(self):

        self.builder.write_config_files()
        self.logger.info(f"\tWriting yaml to dir: {self.builder.config_dir_path}...")

        log_file: str = f"{self.builder.config_dir_path}/{self.builder.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.logger.info(f"\tLogging to: {log_file}...")

        start = time.time()

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
            ], log_file)
        except Exception as e:
            self.logger.warning("Replicant failed")
            failure = True

        end = time.time()
        elapsed_minutes = (end - start) / 60

        if failure:
            self.logger.info(f"Failure: duration {elapsed_minutes:.2f} minutes")
            error: str = self.find_error()
            if error:
                raise self.ReplicantRunError(error)
            else:
                raise self.ReplicantRunError(f"Unknown error, check logs at: {self.error_log_path}")

        self.logger.info(f"Success: duration {elapsed_minutes:.2f} minutes")
