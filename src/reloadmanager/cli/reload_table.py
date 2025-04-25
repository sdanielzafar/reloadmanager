from reloadmanager.table_loader.table_reloader import TableReloader
import logging


def main(args):
    logger = logging.getLogger("reloadmanager")
    logger.setLevel(logging.DEBUG)

    # Attach a handler with custom formatting
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

    logger.info("Starting reload...")

    reloader: TableReloader = TableReloader(
        source_table=args.source_table,
        target_table=args.target_table,
        strategy=args.strategy,
        engine=args.engine,
        lock_rows=args.lock_rows,
        config_dir_path=args.config_dir_path
    )

    reloader.reload()
