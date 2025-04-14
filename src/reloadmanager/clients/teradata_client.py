import jaydebeapi
from contextlib import contextmanager
import time

from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.mixins.secret_mixin import SecretMixin


class TeradataClient(SecretMixin, LoggingMixin):
    def __init__(self):
        self.load_env_file("/home/arcion/secrets/.env")
        self.td_user: str = self.get_secret("TD_USER")
        self.td_pass: str = self.get_secret("TD_PASS")
        self.jdbc_driver = "com.teradata.jdbc.TeraDriver"
        self.jdbc_url = "jdbc:teradata://edwpc.nxp.com/TMODE=TERA"
        self.jdbc_jar = "/arcion/replicant-cli/lib/terajdbc-20.00.00.16.jar"
        self.MAX_BACKOFF_SECONDS = 300

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

    def query(self, sql: str) -> list[tuple]:
        with self._connection() as cursor:
            try:
                cursor.execute(sql)
                return cursor.fetchall()
            except Exception:
                self.logger.error(f"Teradata JDBC query failed: `{sql}`")
                raise

    def query(self, sql: str) -> list[tuple]:
        attempt = 0
        delay = 1

        while True:
            try:
                with self._connection() as cursor:
                    cursor.execute(sql)
                    return cursor.fetchall()

            # retry with exponential backoff to 30s
            except Exception as e:
                attempt += 1
                self.logger.warning(f"Query failed (attempt {attempt}), retrying in {delay}s: {e}")
                time.sleep(delay)
                delay = min(delay * 2, self.MAX_BACKOFF_SECONDS)
