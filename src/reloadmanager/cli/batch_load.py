import logging
import time
import os
from dataclasses import dataclass
from datetime import datetime

from reloadmanager.utils.avoid_window import AvoidWindow
from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner, ReplicantRunError
from reloadmanager.arcion.replicant_runner import SnapshotMetrics


@dataclass(frozen=True)
class ReportRecord:
    table: str
    status: str
    start: float
    end: float
    duration: float
    num_records: int
    error: str

    def __str__(self):
        start_str = datetime.fromtimestamp(self.start).strftime('%-m/%-d/%y %-I:%M %p')
        end_str = datetime.fromtimestamp(self.end).strftime('%-m/%-d/%y %-I:%M %p')
        return f"{self.table},{self.status},{start_str},{end_str}," \
               f"{self.duration:.2f},{self.num_records},{self.error}\n"


def reload_table(source_table: str, target_table: str, run_name: str, threads: int) -> ReportRecord:
    builder: NxpConfigBuilder = NxpConfigBuilder(
        source_table=source_table,
        target_table=target_table,
        extractor_threads=threads,
        config_dir_path=os.path.expanduser(f"~/batch_loads/configs/{run_name}")
    )

    reloader: ReplicantRunner = ReplicantRunner(builder=builder)

    status = "SUCCESS"
    error = ""
    num_records: int = 0
    start: float = time.time()
    try:
        metrics: SnapshotMetrics = reloader.run_snapshot()
        num_records = metrics.num_records
    except ReplicantRunError as e:
        status = "FAILED"
        logging.info(f"\t{status}")
        error = repr(e) or ""
    finally:
        end: float = time.time()

    return ReportRecord(source_table, status, start, end, (end - start) / 60, num_records, error)


def report_writer(file_path):
    first_call = True

    def write_row(record: ReportRecord):
        nonlocal first_call

        mode = 'w' if first_call else 'a'
        with open(file_path, mode) as file:
            # On the first call, write header
            if first_call:
                logging.info(f"Creating report and placing at {file_path}...")
                file.write("TABLE,STATUS,START,END,DURATION_MINS,NUM_RECORDS,ERROR\n")
                first_call = False

            file.write(str(record))

    return write_row


def main(args):
    avoid_window: AvoidWindow = AvoidWindow(args.avoid_window_utc)

    level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    with open(args.input_csv, "r") as f:
        tables = [line.strip() for line in f]

    logging.info(f"Found {len(tables)} tables to load...")
    add_to_report = report_writer(args.output)
    for i, table in enumerate(tables):
        avoid_window.check()
        logging.info(f"{i + 1}/{len(tables)} {table}...")

        reload_summary: ReportRecord = reload_table(
            table,
            "1dp_migration_dev_catalog_3573379518104516." + table,
            args.run_name,
            args.threads
        )

        add_to_report(reload_summary)

    logging.info(f"Finished all loads, report is at {args.output}...")
