import jaydebeapi
import logging
import yaml


class TeradataJDBCConnector:
    def __init__(self, config_path):
        self.config_path = config_path
        self.conn = None
        self.cursor = None
        self.load_config()

    def load_config(self):
        """Load Teradata connection configuration from a YAML file."""
        
        with open(self.config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        self.jdbc_url = self.config['jdbc_url']
        self.driver = self.config['driver']
        self.username = self.config['username']
        self.password = self.config['password']
        self.jar_path = self.config['jar_path']

    def connect(self):
        """Establish a connection to Teradata using JDBC."""
        try:
            self.conn = jaydebeapi.connect(
                self.driver,
                self.jdbc_url,
                [self.username, self.password],
                self.jar_path
            )
            self.cursor = self.conn.cursor()
            print("Successfully connected to Teradata.")
        except Exception as e:
            print(f"Failed to connect to Teradata: {e}")
            raise

    def query(self, sql):
        """Execute a SQL query and return the results."""
        try:
            self.cursor.execute(sql)
            results = self.cursor.fetchall()
            print(f"Query executed successfully: {sql}")
            return results
        except Exception as e:
            print(f"Failed to execute query: {sql}. Error: {e}")
            raise

    def close(self):
        """Close the database connection."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("Connection to Teradata closed.")
        except Exception as e:
            print(f"Failed to close connection: {e}")
            raise

    def __enter__(self):
        """Support for use with 'with' statement."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure the connection is closed when exiting the 'with' block."""
        self.close()


if __name__ == "__main__":
    config_path = "<placeholder>"  # Update with the actual path to your Teradata config YAML file
    with TeradataJDBCConnector(config_path) as connector:
        query = "SELECT * FROM BACKUPDB.EBI_LOAD_COMPLETION_TS_GOLD limit 1"  # sample query using provided table name
        results = connector.query(query)
        for row in results:
            print(row)