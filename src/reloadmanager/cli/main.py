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
    reload_parser.add_argument("--replicant-path", required=False, help="Path to Arcion Replicant")
    reload_parser.add_argument("--config-dir-path", required=False, help="Optional path to put config files")
    reload_parser.set_defaults(func=reload_table.main)

    # Subcommand: query_teradata
    reload_parser = subparsers.add_parser("query-teradata", help="Reload a single table")
    reload_parser.add_argument("--query", required=True, help="Query")
    reload_parser.set_defaults(func=query_teradata.main)

    # Subcommand: batch_load_csv
    reload_parser = subparsers.add_parser("batch_load", help="Reload multiple tables")
    reload_parser.add_argument("--input-csv", required=True, help="The input csv file")
    reload_parser.add_argument("--output", required=True, help="The output location")
    reload_parser.add_argument("--run-name", required=True, help="A name for the run")
    reload_parser.add_argument("--avoid-window", required=False, default=("06:00:00", "18:00:00"))
    reload_parser.set_defaults(func=batch_load.main)

    args = parser.parse_args()
    args.func(args)
