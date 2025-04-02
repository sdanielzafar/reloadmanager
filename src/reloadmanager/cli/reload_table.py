from reloadmanager.arcion.table_reloader import TableReloader
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
        lock_rows=args.lock_rows,
        config_dir_path=args.config_dir_path
    )

    reloader.reload()
