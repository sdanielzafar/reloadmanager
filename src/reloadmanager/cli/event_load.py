import logging

from reloadmanager.event_loader.event_loader import EventLoader
from reloadmanager.utils.datetimes import EventTime


def main(args):

    level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.getLogger().setLevel(level)

    if args.reset_queue.lower() not in ('true', 'false'):
        raise ValueError(f"Argument reset-queue must be 'true' or 'false' not {args.reset_queue.lower()}")
    reset_queue: bool = args.reset_queue.lower() == "true"

    el = EventLoader(
        catalog=args.catalog,
        tpt_threads=int(args.tpt_threads),
        writenos_threads=int(args.writenos_threads),
        reset_queue=reset_queue,
        starting_watermark=str(EventTime(args.start)),
        table_metadata_csv=args.table_metadata_path,
        avoid_window_utc=args.avoid_window_utc,
        sqlite_path=args.sqlite_path
    )

    el.run()
