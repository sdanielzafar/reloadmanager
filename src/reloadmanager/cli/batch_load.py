from reloadmanager.batch_loader.batch_loader import BatchLoader


def main(args):
    bl = BatchLoader(
        input_csv=args.input_csv,
        output=args.output,
        tpt_threads=args.tpt_threads,
        writenos_threads=args.writenos_threads,
        avoid_window_utc=args.avoid_window_utc,
        lock_rows=args.lock_rows,
        log_level=args.log_level
    )

    bl.run()
