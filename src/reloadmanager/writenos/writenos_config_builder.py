import random
from functools import cached_property
from datetime import datetime

from reloadmanager.mixins.secret_mixin import SecretMixin
from reloadmanager.writenos.models import TableInfo


class WriteNOSConfigBuilder(SecretMixin):

    def __init__(
            self,
            source_table: str,
            target_table: str
    ):
        self.source_table: TableInfo = self._validate_source_table(source_table)
        self.target_table: TableInfo = self._validate_target_table(target_table)
        self.load_env_file("/home/arcion/secrets/.env")
        self.databricks_pat = self.get_secret("DATABRICKS_PAT")
        self.aws_key = self.get_secret("AWS_KEY")
        self.aws_secret = self.get_secret("AWS_SECRET")
        self.aws_bucket = self.get_secret("AWS_BUCKET")
        self.dbx_host = self.get_secret("DBX_HOST")
        self.dbx_warehouse = self.get_secret("DBX_WAREHOUSE")

    @cached_property
    def id(self) -> str:
        return f"{self.source_table.table[:8]}{random.randint(100, 999)}"

    @cached_property
    def stage_root_dir(self) -> str:
        ts: str = datetime.now().strftime("%Y%m%d_%H%M%S_") + f"{datetime.now().microsecond // 1000:03d}"
        return f"reload-manager-stage/{self.target_table.catalog}/{self.id}/migration_{self.source_table.table}_{ts}"

    @staticmethod
    def _validate_source_table(source_table: str) -> TableInfo:
        source_schema_table: list[str] = source_table.upper().split(".")
        if len(source_schema_table) != 2:
            raise Exception(f"Argument source_table must have format schema.table. Not '{source_table}'")
        schema, table = source_schema_table
        return TableInfo(catalog=None, schema=schema, table=table)

    @staticmethod
    def _validate_target_table(target_table: str) -> TableInfo:
        source_schema_table: list[str] = target_table.upper().split(".")
        if len(source_schema_table) != 3:
            raise Exception(f"Argument target_table must have format catalog.schema.table. Not '{target_table}'")
        return TableInfo(*source_schema_table)

    @staticmethod
    def _validate_extract_strategy(strategy: str) -> str:
        match strategy:
            case 'TPT':
                return "TPT"
            case 'WriteNOS':
                return "TERADATA_WRITE_NOS"
            case _:
                raise ValueError("'strategy' must be either 'TPT' or 'WriteNOS'")