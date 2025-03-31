import argparse
from reloadmanager.cli import reload_table, query_teradata, batch_load


def main():
    parser = argparse.ArgumentParser(
        description="NXP Reload Manager CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: reload_table
    reload_parser = subparsers.add_parser("reload-table", help="Reload a single table")
    reload_parser.add_argument("--source-table", required=True, help="Teradata: schema.table")
    reload_parser.add_argument("--target-table", required=True, help="Databricks: catalog.schema.table")
    reload_parser.add_argument("--method", required=False, help="'WriteNOS' or 'TPT", default="WriteNOS")
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
    batch_load_parser.add_argument("--avoid-window-utc", required=False, default="6-18", help="6-18 or None")
    batch_load_parser.add_argument("--tpt-threads", required=False, help="# TPT threads (default: 8)", default=8)
    batch_load_parser.add_argument("--writenos-threads", required=False, help="# WriteNOS threads (default: 2)", default=2)
    batch_load_parser.add_argument("--lock-rows", required=False, help="Whether to enable row locking", default=True)
    batch_load_parser.add_argument("--log-level", required=False, help="Optional log level", default="INFO")
    batch_load_parser.set_defaults(func=batch_load.main)

    args = parser.parse_args()
    args.func(args)
