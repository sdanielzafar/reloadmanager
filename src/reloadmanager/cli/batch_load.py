import logging
import time
import os
from reloadmanager.nxp_reload_runner import NxpReloadRunner
from reloadmanager.arcion.stats_tracker import RunStatsTracker


def reload_table(source_table: str, target_table: str, run_name: str):
    reloader: NxpReloadRunner = NxpReloadRunner(
        source_table,
        target_table,
        config_dir_path=os.path.expanduser(f"~/batch_loads/configs/{run_name}")
    )

    reloader.run_snapshot()


def main(args):

    with open(args.input_csv, "r") as f:
        tables = [line.strip() for line in f]

    logging.info(f"Found {len(tables)} tables to load...")

    for table in tables:
        logging.info(f"{table}...")
        start = time.time()
        status = "SUCCESS"
        try:
            reload_table(table, "1dp_migration_dev_catalog_3573379518104516." + table, args.run_name)
            logging.info(f"\t{status}")
        except Exception:
            status = "FAILED"
            logging.info(f"\t{status}")
        finally:
            end = time.time()
            elapsed_minutes = (end - start) / 60
            logging.info(f"\tTook{elapsed_minutes: .2f}")
            RunStatsTracker.record(table, "Failed", elapsed_minutes)

    logging.info(f"Finished all loads, generating report and placing at {args.output}...")
    RunStatsTracker.generate_report(args.output)
