import os
import random
import textwrap
import tempfile
from abc import ABC, abstractmethod
from functools import cached_property
import time
from datetime import datetime

from reloadmanager.core.secret_mixin import SecretMixin
from reloadmanager.core.config_models import *
from reloadmanager.core.cli_runner import run_cli_cmd


class ReplicantRunner(ABC, SecretMixin):
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
                 replicant_path: str = "/arcion/replicant-cli/bin/replicant",
                 config_dir_path: str = None):
        self.replicant_path: str = replicant_path
        self.source_table: TableInfo = self._validate_source_table(source_table)
        self.target_table: TableInfo = self._validate_target_table(target_table)
        self.src_config: SourceConfig | None = None
        self.target_config: TargetConfig | None = None
        self.extr_config: ExtractorConfig | None = None
        self.config_file_paths: ConfigFilePaths | None = None
        self.config_dir_path = config_dir_path if config_dir_path else tempfile.mkdtemp()

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

    @cached_property
    def _id(self) -> str:
        return f"{self.source_table.table[:6]}{random.randint(100, 999)}"

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

    def load_config_defaults(self):
        self.src_config = self.source_config_defaults()
        self.target_config = self.target_config_defaults()
        self.extr_config = self.extractor_config_defaults()
        self.config_file_paths = self.config_file_path_defaults()

    def _write_src_config(self) -> str:
        src_yaml: str = textwrap.dedent(f"""
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
            max-retries: 3
            retry-wait-duration-ms: 1000
            max-conn-retries: 4
            conn-retry-wait-duration-ms: 5000
        """)

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_source.yaml")
        with open(file_path, "w") as file:
            file.write(src_yaml)

        return file_path

    def _write_target_config(self) -> str:

        target_yaml: str = textwrap.dedent(f"""
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
            retry-wait-duration-ms: 1000 #Duration replicant should wait before performing then next retry
            # stage config section
            stage:
              type: {self.target_config.stage_type}
              root-dir: {self.target_config.stage_root_dir}
              conn-url: {self.target_config.stage_conn_url}
              key-id: {self.target_config.stage_key_id}
              secret-key: {self.target_config.stage_secret_key}
              file-format: {self.target_config.stage_file_format}
        """)

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_target.yaml")
        with open(file_path, "w") as file:
            file.write(target_yaml)

        return file_path

    def _write_extractor_config(self) -> str:

        extractor_yaml: str = textwrap.dedent(f"""
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

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_extractor.yaml")
        with open(file_path, "w") as file:
            file.write(extractor_yaml)

        return file_path

    def _write_applier_config(self) -> str:

        applier_yaml: str = textwrap.dedent(f"""
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

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_applier.yaml")
        with open(file_path, "w") as file:
            file.write(applier_yaml)

        return file_path

    def _write_allow_config(self) -> str:
        allow_yaml: str = textwrap.dedent(f"""
            allow:
            - schema : {self.source_table.schema}
              types: [TABLE, VIEW, QUERY]
              allow:
                {self.source_table.table} :
        """)

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_allow.yaml")
        with open(file_path, "w") as file:
            file.write(allow_yaml)

        return file_path

    def _write_map_config(self) -> str:
        map_yaml: str = textwrap.dedent(f"""
            rules:
              [{self.target_table.catalog}, {self.target_table.schema}]:
                source:
                - {self.target_table.schema}
                tables:
                  {self.target_table.table}:
                    source:
                      [{self.source_table.schema}, {self.source_table.table}]:
        """)

        file_path: str = os.path.join(self.config_dir_path, f"{self._id}_map.yaml")
        with open(file_path, "w") as file:
            file.write(map_yaml)

        return file_path

    def _write_config_files(self):
        if not self.config_file_paths.source:
            self.config_file_paths.source = self._write_src_config()
        if not self.config_file_paths.target:
            self.config_file_paths.target = self._write_target_config()
        if not self.config_file_paths.extractor:
            self.config_file_paths.extractor = self._write_extractor_config()
        if not self.config_file_paths.applier:
            self.config_file_paths.applier = self._write_applier_config()
        if not self.config_file_paths.filter:
            self.config_file_paths.filter = self._write_allow_config()
        if not self.config_file_paths.map:
            self.config_file_paths.map = self._write_map_config()

    def run_snapshot(self):

        self._write_config_files()
        print(f"\tWriting yaml to dir: {self.config_dir_path}...")

        log_file: str = f"{self.config_dir_path}/{self._id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        print(f"\tLogging to: {log_file}...")

        start = time.time()

        run_cli_cmd([
            self.replicant_path, "snapshot",
            self.config_file_paths.source,
            self.config_file_paths.target,
            "--extractor", self.config_file_paths.extractor,
            "--applier", self.config_file_paths.applier,
            "--filter", self.config_file_paths.filter,
            "--map", self.config_file_paths.map,
            "--truncate-existing"
        ], log_file)

        end = time.time()
        elapsed_minutes = (end - start) / 60
        print(f"Success: duration {elapsed_minutes:.2f} minutes")
