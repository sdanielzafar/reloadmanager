from reloadmanager.clients.databricks_client import DatabricksClient


def main(args):
    dbx_client: DatabricksClient = DatabricksClient()
    results = dbx_client.query(args.query, args.headers)
    for row in results:
        print(row)
