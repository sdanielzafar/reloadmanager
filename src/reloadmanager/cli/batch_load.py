import logging
import time
import os
from datetime import datetime
from reloadmanager.nxp_reload_runner import NxpReloadRunner
from reloadmanager.arcion.stats_tracker import RunStatsTracker


def reload_table(source_table: str, target_table: str, run_name: str):
    reloader: NxpReloadRunner = NxpReloadRunner(
        source_table,
        target_table,
        config_dir_path=os.path.expanduser(f"~/batch_loads/configs/{run_name}")
    )

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

    for table in tables:
        if is_run_forbidden():
            logging.info(f"It is {datetime.now()}, cannot run any more tables...")
            break
        logging.info(f"{table}...")
        start = time.time()
        status = "SUCCESS"
        try:
            reload_table(table, "1dp_migration_dev_catalog_3573379518104516." + table, args.run_name)
            logging.info(f"\t{status}")
        except Exception as e:
            status = "FAILED"
            logging.info(f"\t{status}")
            print(e)
        finally:
            end = time.time()
            elapsed_minutes = (end - start) / 60
            logging.info(f"\tTook{elapsed_minutes: .2f}")
            RunStatsTracker.record(table, status, elapsed_minutes)

    logging.info(f"Finished all loads, generating report and placing at {args.output}...")
    RunStatsTracker.generate_report(args.output)
