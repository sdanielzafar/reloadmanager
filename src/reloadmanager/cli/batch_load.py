import logging

from reloadmanager.batch_loader.batch_loader import BatchLoader


def main(args):

    level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.getLogger().setLevel(level)

    bl = BatchLoader(
        input_csv=args.input_csv,
        output=args.output,
        tpt_threads=int(args.tpt_threads),
        writenos_threads=int(args.writenos_threads),
        avoid_window_utc=args.avoid_window_utc,
        lock_rows=args.lock_rows
    )

    bl.run()
