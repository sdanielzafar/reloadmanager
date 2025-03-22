import argparse
from reloadmanager import reload_table

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

    args = parser.parse_args()
    args.func(args)

