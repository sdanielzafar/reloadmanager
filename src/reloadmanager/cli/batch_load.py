import logging
import time
import os
from datetime import datetime

from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner
from reloadmanager.arcion.stats_tracker import RunStatsTracker


def reload_table(source_table: str, target_table: str, run_name: str, threads: int):

    builder: NxpConfigBuilder = NxpConfigBuilder(
        source_table=source_table,
        target_table=target_table,
        extractor_threads=threads,
        config_dir_path=os.path.expanduser(f"~/batch_loads/configs/{run_name}")
    )

    reloader: ReplicantRunner = ReplicantRunner(builder=builder)
    reloader.run_snapshot()


def respect_time_window(start: int, end: int, asleep: bool = False) -> None:
    if start > end:
        raise Exception("Logic assumes start time < end time, please revise code if needed.")
    now = datetime.now().hour
    if start <= now < end:
        if not asleep:
            logging.info(f"It is {datetime.now()}, putting job to sleep...zzZZzz")
        time.sleep(60 * 5)
        respect_time_window(start, end, True)
    if asleep:
        logging.info(f"It is {datetime.now()}, waking up job...*yawn*")


def main(args):

    start, end = args.avoid_window_utc.split("-")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    with open(args.input_csv, "r") as f:
        tables = [line.strip() for line in f]

    logging.info(f"Found {len(tables)} tables to load...")

    counter: int = 1
    for table in tables:
        respect_time_window(start, end)
        logging.info(f"{counter}/{len(tables)} {table}...")
        start = time.time()
        status = "SUCCESS"
        error = ""
        try:
            reload_table(table, "1dp_migration_dev_catalog_3573379518104516." + table, args.run_name, args.threads)
        except Exception as e:
            status = "FAILED"
            logging.info(f"\t{status}")
            error = str(e)
        finally:
            end = time.time()
            elapsed_minutes = (end - start) / 60
            RunStatsTracker.record(table, status, elapsed_minutes, error or "")
            counter += 1

    logging.info(f"Finished all loads, generating report and placing at {args.output}...")
    RunStatsTracker.generate_report(args.output)
