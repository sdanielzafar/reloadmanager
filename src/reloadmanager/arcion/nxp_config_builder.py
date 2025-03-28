from datetime import datetime
from reloadmanager.arcion.replicant_config_builder import ReplicantConfigBuilder
from reloadmanager.arcion.config_models import SourceConfig, ExtractorConfig, TargetConfig, ConfigFilePaths


class NxpConfigBuilder(ReplicantConfigBuilder):

    def __init__(self,
                 source_table: str,
                 target_table: str,
                 method: str,
                 config_dir_path: str = None,
                 lock_rows: bool = False
                 ):

        super().__init__(source_table, target_table, method, lock_rows, config_dir_path)

        self.load_env_file("/home/arcion/secrets/.env")
        self.oauth_client_id = "7d973a81-6d3a-4e26-99e2-6b10df4bbf41"
        self.databricks_pat = self.get_secret("DATABRICKS_PAT")
        self.aws_key = self.get_secret("AWS_KEY")
        self.aws_secret = self.get_secret("AWS_SECRET")

        # need to do this as a separate call, not in the parent's constructor or else the above attributes will
        # not be passed in because they won't be defined yet.
        self.load_config_defaults()

    def source_config_defaults(self) -> SourceConfig:
        return SourceConfig(
            type="TERADATA",
            host="edwpc.nxp.com",
            port="1025",
            credential_store_type="PKCS12",
            credential_store_path="/arcion/configs/teradata.jks",
            credential_store_key_prefix='"teradata"',
            tpt_connection_host="edwpc.nxp.com",
            tpt_connection_un="'EDW_DB_SYNC_USER'",
            tpt_connection_pass="'Syndb$25pc'",
            max_connections="4",
        )

    def target_config_defaults(self) -> TargetConfig:

        ts: str = datetime.now().strftime("%Y%m%d_%H%M%S_") + f"{datetime.now().microsecond // 1000:03d}"

        return TargetConfig(
            type="DATABRICKS_LAKEHOUSE",
            host="dbc-7c9eb967-788d.cloud.databricks.com",
            port="443",
            url="jdbc:databricks://dbc-7c9eb967-788d.cloud.databricks.com:443/default;transportMode=http;ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/79ae80263968b83a;",
            username="token",
            password=self.databricks_pat,
            max_connections="8",
            supports_timestamp_ntz="false",
            stage_type="S3",
            stage_root_dir=f"replicant-stage/{self.oauth_client_id}/{self.id}/"
                           f"migration_{self.source_table.table}_{ts}",
            stage_conn_url="1dp-migration-acrion-td-sync",
            stage_key_id=self.aws_key,
            stage_secret_key=self.aws_secret,
            stage_file_format="PARQUET",
        )

    def extractor_config_defaults(self) -> ExtractorConfig:
        return ExtractorConfig(
            fetch_size_rows="10_000",
            split_method="RANGE",
            extraction_method="TERADATA_WRITE_NOS",
            tpt_max_file_size_gb="5",
            tpt_num_files_per_job="16",
            write_nos_auth_schema="EDW_DB_SYNC_USER",
            write_nos_number_precision="38",
            write_nos_number_scale="10",
            cast_varchar_type="true"
        )

    def config_file_path_defaults(self) -> ConfigFilePaths:
        return ConfigFilePaths(
            source="/arcion/configs/teradata_src.yaml",
            target=None,
            extractor=None,
            applier="/arcion/configs/databricks_applier.yaml",
            filter=None,
            map=None,
        )
