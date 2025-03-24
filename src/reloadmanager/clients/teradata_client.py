import jaydebeapi
from reloadmanager.mixins.secret_mixin import SecretMixin


class TeradataClient(SecretMixin):
    def __init__(self):
        self.conn: jaydebeapi.Connection | None = None
        self.cursor: jaydebeapi.Cursor | None = None
        self.load_env_file("/home/arcion/secrets/.env")
        self.td_user: str = self.get_secret("TD_USER")
        self.td_pass: str = self.get_secret("TD_PASS")

    def connect(self):
        """Establish a connection to Teradata using JDBC."""
        try:
            self.conn: jaydebeapi.Connection = jaydebeapi.connect(
                "com.teradata.jdbc.TeraDriver",
                "jdbc:teradata://edwpc.nxp.com/TMODE=TERA",
                [self.td_user, self.td_pass],
                "/arcion/replicant-cli/lib/terajdbc-20.00.00.16.jar"
            )
            self.cursor: jaydebeapi.Cursor = self.conn.cursor()
        except Exception as e:
            print(f"Failed to connect to Teradata: {e}")
            raise

    def query(self, sql):
        """Execute a SQL query and return the results."""
        try:
            self.cursor.execute(sql)
            results = self.cursor.fetchall()
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
