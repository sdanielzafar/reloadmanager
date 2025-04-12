from reloadmanager.clients.databricks_client import DatabricksClient


def main(args):
    dbx_client: DatabricksClient = DatabricksClient()
    results = dbx_client.query(args.query)
    for row in results:
        print(row)
