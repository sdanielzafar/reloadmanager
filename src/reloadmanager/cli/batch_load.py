import logging
import time
import os
from datetime import datetime

from reloadmanager.arcion.nxp_config_builder import NxpConfigBuilder
from reloadmanager.arcion.replicant_runner import ReplicantRunner
from reloadmanager.arcion.stats_tracker import RunStatsTracker


def reload_table(source_table: str, target_table: str, run_name: str):

    builder: NxpConfigBuilder = NxpConfigBuilder(
        source_table=source_table,
        target_table=target_table,
        config_dir_path=os.path.expanduser(f"~/batch_loads/configs/{run_name}")
    )

    reloader: ReplicantRunner = ReplicantRunner(builder=builder)
    reloader.run_snapshot()


def is_run_forbidden() -> bool:
    now = datetime.now().hour
    return 6 <= now < 18


def main(args):

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    with open(args.input_csv, "r") as f:
        tables = [line.strip() for line in f]

    logging.info(f"Found {len(tables)} tables to load...")

    counter: int = 1
    for table in tables:
        if is_run_forbidden():
            logging.info(f"It is {datetime.now()}, cannot run any more tables...")
            break
        logging.info(f"{counter}/{len(tables)} {table}...")
        start = time.time()
        status = "SUCCESS"
        error = ""
        try:
            reload_table(table, "1dp_migration_dev_catalog_3573379518104516." + table, args.run_name)
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
