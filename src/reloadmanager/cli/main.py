import argparse
from reloadmanager.cli import reload_table, query_teradata, batch_load, event_load
from reloadmanager.utils.datetimes import EventTime


def main():
    parser = argparse.ArgumentParser(
        description="NXP Reload Manager CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: reload_table
    reload_parser = subparsers.add_parser("reload-table", help="Reload a single table")
    reload_parser.add_argument("--source-table", required=True, help="Teradata: schema.table")
    reload_parser.add_argument("--target-table", required=True, help="Databricks: catalog.schema.table")
    reload_parser.add_argument("--strategy", required=False, help="'WriteNOS' or 'TPT", default="WriteNOS")
    reload_parser.add_argument("--replicant-path", required=False, help="Path to Arcion Replicant")
    reload_parser.add_argument("--config-dir-path", required=False, help="Optional path to put config files")
    reload_parser.add_argument("--lock-rows", required=False, help="Whether to enable row locking", default=True)
    reload_parser.set_defaults(func=reload_table.main)

    # Subcommand: query_teradata
    td_query_parser = subparsers.add_parser("query-teradata", help="Reload a single table")
    td_query_parser.add_argument("--query", required=True, help="Query")
    td_query_parser.set_defaults(func=query_teradata.main)

    # Subcommand: batch_load_csv
    batch_load_parser = subparsers.add_parser("batch-load", help="Reload multiple tables")
    batch_load_parser.add_argument("--input-csv", required=True, help="The input csv file")
    batch_load_parser.add_argument("--output", required=True, help="The output location")
    batch_load_parser.add_argument("--catalog", required=True, help="The target catalog")
    batch_load_parser.add_argument("--avoid-window-utc", required=False, default="6-18", help="6-18 or None")
    batch_load_parser.add_argument("--tpt-threads", required=False, help="# TPT threads (default: 8)", default=8)
    batch_load_parser.add_argument("--writenos-threads", required=False, help="# WriteNOS threads (default: 2)",
                                   default=2)
    batch_load_parser.add_argument("--lock-rows", required=False, help="Whether to enable row locking", default=True)
    batch_load_parser.add_argument("--log-level", required=False, help="Optional log level", default="INFO")
    batch_load_parser.set_defaults(func=batch_load.main)

    # Subcommand: event_load
    event_load_parser = subparsers.add_parser("event-load", help="Reload tables based on tracking table")
    event_load_parser.add_argument("--catalog", required=True, help="The target catalog")
    event_load_parser.add_argument("--tpt-threads", required=False, help="# TPT threads (default: 8)", default=8)
    event_load_parser.add_argument("--writenos-threads", required=False, help="# WriteNOS threads (default: 2)",
                                   default=2)
    event_load_parser.add_argument("--start", required=False, help="Starting watermark (%Y-%m-%d %H:%M:%S)",
                                   default=str(EventTime.now()))
    event_load_parser.add_argument("--table-metadata-path", required=False, help="Path to table metadata csv",
                                   default="/home/arcion/event_loader/table_metadata/TRTables.csv")
    event_load_parser.add_argument("--avoid-window-utc", required=False, default="None", help="6-18 or None")
    event_load_parser.add_argument("--sqlite-path", required=False, help="Location for SQLite database",
                                   default="/home/arcion/event_loader/sqlite/primary.db")
    event_load_parser.add_argument("--log-level", required=False, help="Optional log level", default="INFO")
    event_load_parser.add_argument("--reset-queue", required=False, help="Optional log level", default="false")
    event_load_parser.set_defaults(func=event_load.main)

    args = parser.parse_args()
    args.func(args)
