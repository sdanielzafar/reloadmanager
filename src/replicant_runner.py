from dataclasses import dataclass
import textwrap
from abc import ABC, abstractmethod
import subprocess


@dataclass
class TableInfo:
    catalog: str | None
    schema: str
    table: str


@dataclass
class SourceConfig:
    type: str
    host: str
    port: str
    credential_store_type: str
    credential_store_path: str
    credential_store_key_prefix: str
    tpt_connection_host: str
    tpt_connection_un: str
    tpt_connection_pass: str
    max_connections: str


@dataclass
class TargetConfig:
    type: str
    host: str
    port: str
    url: str
    username: str
    password: str
    max_connections: int | str
    supports_timestamp_ntz: bool | str
    stage_type: str
    stage_root_dir: str
    stage_conn_url: str
    stage_key_id: str
    stage_secret_key: str
    stage_file_format: str


@dataclass
class ExtractorConfig:
    threads: int | str
    fetch_size_rows: str
    split_method: str
    extraction_method: str
    tpt_max_file_size_gb: int | str
    tpt_num_files_per_job: int | str
    write_nos_auth_schema: str
    write_nos_number_precision: int | str
    write_nos_number_scale: int | str
    write_nos_cast_str_type: int | str


@dataclass
class ConfigFilePaths:
    source: str
    target: str
    extractor: str
    applier: str
    filter: str
    map: str


class ReplicantRunner(ABC):
    """
    This class will run the Arcion Replicant CLI commands

    It should not have any customer-specific configs

    A typical shell command looks like this:

    /arcion/replicant-cli/bin/replicant snapshot
      /arcion/configs/teradata_src.yaml
      dest_config.yaml
      --extractor delta_file.yaml
      --applier /arcion/configs/databricks_applier.yaml
      --filter allow_file.yaml
      --map map_file.yaml
      --truncate-existing

    The various files do different things:
     - the first outlines the source (Teradata) config options
     - the second outlines the destination config options (Databricks)
     - extractor: the extraction metod and configs (WriteNos or TPT)
     - applier: configs for the engine...i don't know
     - filter: gives the tables information and filters on it
     - map: rules about what the table in the source should map to in the target

     This class should automate the creation of these files and running of the snapshot
    """

    def __init__(self,
                 source_table: str,
                 target_table: str,
                 replicant_path: str = "/arcion/replicant-cli/bin/replicant"):
        self.replicant_path: str = replicant_path
        self.source_table: TableInfo = self._validate_source_table(source_table)
        self.target_table: TableInfo = self._validate_target_table(target_table)
        self.src_config: SourceConfig = self.source_config_defaults()
        self.target_config: TargetConfig = self.target_config_defaults()
        self.extr_config: ExtractorConfig = self.extractor_config_defaults()
        self.config_file_paths: ConfigFilePaths = self.set_config_file_path_defaults()

    @staticmethod
    def _validate_source_table(source_table: str) -> TableInfo:
        source_schema_table: list[str] = source_table.upper().split(".")
        if len(source_schema_table) != 2:
            raise Exception(f"Argument source_table must have format schema.table. Not '{source_table}'")
        return TableInfo(catalog=None, *source_schema_table)

    @staticmethod
    def _validate_target_table(target_table: str) -> TableInfo:
        source_schema_table: list[str] = target_table.upper().split(".")
        if len(source_schema_table) != 3:
            raise Exception(f"Argument target_table must have format catalog.schema.table. Not '{target_table}'")
        return TableInfo(*source_schema_table)

    @abstractmethod
    def config_file_path_defaults(self) -> ConfigFilePaths:
        pass

    @abstractmethod
    def source_config_defaults(self) -> SourceConfig:
        pass

    @abstractmethod
    def target_config_defaults(self) -> TargetConfig:
        pass

    @abstractmethod
    def extractor_config_defaults(self) -> ExtractorConfig:
        pass

    def _write_src_config(self):
        textwrap.dedent(f"""
            type: {self.src_config.type}
    
            host: {self.src_config.host}
            port: {self.src_config.port}
            client-charset: UTF8
            
            credential-store:
              type: {self.src_config.credential_store_type}
              path: {self.src_config.credential_store_path}
              key-prefix: {self.src_config.credential_store_key_prefix}
            
            tpt-connection:
              host: {self.src_config.tpt_connection_host}
              username: {self.src_config.tpt_connection_un}
              password: {self.src_config.tpt_connection_pass}          
            max-connections: {self.src_config.max_connections}
            max-retries: 10
            retry-wait-duration-ms: 1000
            max-conn-retries: 4
            conn-retry-wait-duration-ms: 5000
        """)

    def _write_target_config(self):
        textwrap.dedent(f"""
            type: {self.target_config.type}
            host: {self.target_config.host}
            port: {self.target_config.port}
            url: {self.target_config.url}
            
            #auth-type: OAUTH_M2M
            #oauth-client-id: 7d973a81-6d3a-4e26-99e2-6b10df4bbf41
            #oauth-client-secret: ****
            username: {self.target_config.username}
            password: {self.target_config.password}
            max-connections: {str(self.target_config.max_connections)}
            max-retries: 3
            date-format: yyyy-MM-dd #default yyyy-MM-dd, specify the date format if source DB provides dates in a format other than default (yyyy-dd-mm)
            supports-timestamp-ntz: {str(self.target_config.supports_timestamp_ntz).lower()}
            retry-wait-duration-ms: 1000 #Duration in milliseconds replicant should wait before performing then next retry of a failed operation
            # stage config section
            stage:
              type: {self.target_config.stage_type}
              root-dir: {self.target_config.stage_root_dir}
              conn-url: {self.target_config.stage_conn_url}
              key-id: {self.target_config.stage_key_id}
              secret-key: {self.target_config.stage_secret_key}
              file-format: {self.target_config.stage_file_format}
        """)

    def _write_extractor_config(self):

        textwrap.dedent(f"""
            snapshot:
              threads: {str(self.extr_config.threads)}
              fetch-size-rows: {self.extr_config.fetch_size_rows}
              _traceDBTasks: true
              split-method: {self.extr_config.split_method}  # Allowed values are RANGE, MODULO
              extraction-method: {self.extr_config.extraction_method}
              tpt-max-file-size-gb: {str(self.extr_config.tpt_max_file_size_gb)}
              tpt-num-files-per-job: {str(self.extr_config.tpt_num_files_per_job)}
              write-nos-auth-schema: {self.extr_config.write_nos_auth_schema}
              write-nos-number-precision: {str(self.extr_config.write_nos_number_precision)}
              write-nos-number-scale: {str(self.extr_config.write_nos_number_scale)}
              write-nos-cast-str-type: {str(self.extr_config.write_nos_cast_str_type).lower()}
              native-extract-options:
                charset: "UTF8"  #Allowed values are ASCII, UTF8
                compression-type: "NONE" #Allowed values are GZIP and NONE
                max-object-size-mb: 8
              per-table-config:
              - schema: {self.source_table.schema}
                tables:
                  {self.source_table.table}:
                    extraction-method: {self.extr_config.extraction_method}
        """)

    @staticmethod
    def _write_applier_config():
        textwrap.dedent(f"""
           snapshot:
              threads: 16
              txn-size-rows: 1_000_000
              _traceDBTasks: true
              optimize-snapshot: True #deprecated
              bulk-load:
                enable: true
                type: FILE
                save-file-on-error: true
                serialize: false              
           realtime:
              threads: 16
        """)

    def _write_allow_config(self):
        textwrap.dedent(f"""
            allow:
            - schema : {self.source_table.schema}
              types: [TABLE, VIEW, QUERY]
              allow:
                {self.source_table.table} :
        """)

    def _write_map_config(self):
        textwrap.dedent(f"""
            rules:
            [{self.target_table.catalog}, {self.target_table.schema}]:
            source:
            - {self.target_table.schema}
        """)

    # DZ working on this
    def _write_config_files(self):
        pass
        # # source
        # # target
        # # extractor
        # # applier
        # # filter
        # # map
        # if not self.config_file_paths.source:


    @staticmethod
    def run_cli_cmd(command: list[str]) -> str:
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Command: '{' '.join(command)}' failed with exit code {e.returncode}")
            stderr: str = "\n\t\t" + e.stderr.strip().replace('\n', '\n\t\t')
            stdout: str = "\n\t\t" + e.stdout.strip().replace('\n', '\n\t\t')
            print(f"\tThe command's stderr: {stderr if e.stderr else 'No stderr available'}")
            print(f"\tThe command's stdout: {stdout if e.stdout else 'No stdout available'}")
            raise e

    def run_snapshot(self):

        self._write_config_files()

        self.run_cli_cmd([
            self.replicant_path, "snapshot",
            self.config_file_paths.source,
            self.config_file_paths.target,
            "--extractor", self.config_file_paths.extractor,
            "--applier", self.config_file_paths.applier,
            "--filter", self.config_file_paths.filter,
            "--map", self.config_file_paths.map,
            "--truncate-existing"
        ])
