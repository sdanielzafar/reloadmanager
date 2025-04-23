import jaydebeapi
from contextlib import contextmanager

from reloadmanager.clients.generic_database_client import GenericDatabaseClient
from reloadmanager.mixins.secret_mixin import SecretMixin


class TeradataClient(GenericDatabaseClient, SecretMixin):
    def __init__(self):
        super().__init__()
        self.load_env_file("/home/arcion/secrets/.env")
        self.td_user: str = self.get_secret("TD_USER")
        self.td_pass: str = self.get_secret("TD_PASS")
        self.jdbc_driver = "com.teradata.jdbc.TeraDriver"
        self.jdbc_url = "jdbc:teradata://edwpc.nxp.com/TMODE=TERA"
        self.jdbc_jar = "/arcion/replicant-cli/lib/terajdbc-20.00.00.16.jar"

    @contextmanager
    def _connection(self):
        conn = None
        cursor = None
        try:
            conn = jaydebeapi.connect(
                self.jdbc_driver,
                self.jdbc_url,
                [self.td_user, self.td_pass],
                self.jdbc_jar
            )
            cursor = conn.cursor()
            yield cursor
        except Exception as e:
            self.logger.error(f"Unable to create JDBC connection to Teradata: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception as e:
                    self.logger.error(f"Teradata JDBC cursor cleanup failed: {e}")
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    print(f"Teradata JDBC connection cleanup failed: {e}")

    def _query(self, sql: str, headers: bool) -> list[tuple] | list[dict]:
        with self._connection() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            if not headers:
                return rows
            headers = [desc[0] for desc in cursor.description]
            return [dict(zip(headers, row)) for row in rows]
