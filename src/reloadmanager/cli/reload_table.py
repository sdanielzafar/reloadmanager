from reloadmanager.table_loader.table_reloader import TableReloader
import logging


def main(args):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    reloader: TableReloader = TableReloader(
        source_table=args.source_table,
        target_table=args.target_table,
        strategy=args.strategy,
        engine=args.engine,
        lock_rows=args.lock_rows,
        config_dir_path=args.config_dir_path
    )

    reloader.reload()
