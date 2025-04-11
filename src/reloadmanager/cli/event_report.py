import logging

from reloadmanager.reporting.event_reporter import EventReporter


def main(args):

    level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")

    logging.getLogger().setLevel(level)

    event_reporter: EventReporter = EventReporter(target_table=args.target_table, catalog=args.catalog)
    event_reporter.run()
