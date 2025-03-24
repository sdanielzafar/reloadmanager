from reloadmanager.core.teradata_client import TeradataClient


def main(args):
    with TeradataClient() as connector:
        results = connector.query(args.query)
        for row in results:
            print(row)
