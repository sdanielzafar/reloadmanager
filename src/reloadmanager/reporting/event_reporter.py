import sys
if sys.platform.startswith("darwin"):
    import sqlite3 as sqlite3
else:
    import pysqlite3 as sqlite3

from reloadmanager.clients.databricks_client import DatabricksClient
from reloadmanager.mixins.logging_mixin import LoggingMixin


class EventReporter(LoggingMixin):
    def __init__(
            self,
            target_table: str = "td_migration.tnr_history",
            catalog: str = "1dp_migration_dev_catalog_3573379518104516",
            sqlite_path: str = "/home/arcion/event_loader/sqlite/primary.db",
            databricks_client: DatabricksClient = None):
        self.databricks_client = databricks_client or DatabricksClient()
        self.target: str = f"{catalog}.{target_table}"
        self.db_path: str = sqlite_path

    def last_update(self) -> str | None:
        last_time: list[dict[str, str]] = self.databricks_client.query(f"SELECT MAX(finish_time) as max_dttm FROM {self.target}")
        return last_time[0]["max_dttm"].replace("T", " ").replace(".000Z", "")

    def query_queue_history(self, from_dttm: str) -> list[tuple]:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM QUEUE_HISTORY 
                WHERE finish_time > ?
            """, (from_dttm,))

            return cursor.fetchall()

    @staticmethod
    def fmt_row(row: tuple) -> str:
        expanded: str = "', '".join([str(r) for r in row])
        if not expanded:
            return "()"
        return f"('{expanded}')"

    def fmt_values(self, records: list[tuple]) -> str:
        return ", ".join(([self.fmt_row(row) for row in records]))

    def run(self):
        last_update: str | None = self.last_update()
        self.logger.info(f"Target table last updated: {last_update or '<empty>'}")
        records: list[tuple] = self.query_queue_history(last_update or 0)
        if not records:
            self.logger.info("No new records received from sqlite...")
            return
        sql: str = f"INSERT INTO {self.target} VALUES {self.fmt_values(records)};"
        self.logger.debug(f"Running Databricks query: \n{sql}")
        self.databricks_client.query(sql)
