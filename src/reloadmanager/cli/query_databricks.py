from reloadmanager.clients.databricks_client import DatabricksWarehouseClient


def main(args):
    dbx_client: DatabricksWarehouseClient = DatabricksWarehouseClient()
    results = dbx_client.query(args.query)
    for row in results:
        print(row)
