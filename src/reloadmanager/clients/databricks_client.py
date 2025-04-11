import http.client
import json
import time
from contextlib import contextmanager

from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.mixins.secret_mixin import SecretMixin


class DatabricksWarehouseClient(SecretMixin, LoggingMixin):
    def __init__(self, secret_path: str | None = None):
        self.load_env_file(secret_path or "/home/arcion/secrets/.env")
        self.dbx_pat: str = self.get_secret("DATABRICKS_PAT")
        self.dbx_host = self.get_secret("DBX_HOST")
        self.dbx_warehouse = self.get_secret("DBX_WAREHOUSE")

    @contextmanager
    def _http_connection(self):
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.dbx_host)
            yield conn
        finally:
            if conn:
                conn.close()

    def query(self, sql: str) -> list[dict]:
        with self._http_connection() as conn:
            # Submit query
            headers = {
                'Authorization': f'Bearer {self.dbx_pat}',
                'Content-Type': 'application/json'
            }
            body = {
                "statement": sql,
                "warehouse_id": self.dbx_warehouse
            }

            try:
                conn.request("POST", "/api/2.0/sql/statements", body=json.dumps(body), headers=headers)
                resp = conn.getresponse()
                data = json.loads(resp.read())
                statement_id = data['statement_id']
            except Exception as e:
                self.logger.error(f"Failed to submit query to Databricks Warehouse: {e}")
                raise

            # Poll for results
            while True:
                try:
                    conn.request("GET", f"/api/2.0/sql/statements/{statement_id}", headers=headers)
                    poll_resp = conn.getresponse()
                    result = json.loads(poll_resp.read())
                    state = result['status']['state']
                except Exception as e:
                    self.logger.error(f"Failed polling query status: {e}")
                    raise

                if state in ["SUCCEEDED", "FAILED", "CANCELED"]:
                    break
                time.sleep(1)

            if state != "SUCCEEDED":
                self.logger.error(f"Query failed with state: {state}")
                raise RuntimeError(f"Query failed: {result}")

            columns = result['manifest']['schema'].get("columns")
            if not columns:
                Exception(str(result['manifest']['schema']))

            columns = [field['name'] for field in result['manifest']['schema']['columns']]
            rows = result['result']['data_array']
            return [dict(zip(columns, row)) for row in rows]
