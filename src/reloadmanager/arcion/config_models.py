from dataclasses import dataclass

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
    fetch_size_rows: str
    split_method: str
    tpt_max_file_size_gb: int | str
    tpt_num_files_per_job: int | str
    write_nos_auth_schema: str
    write_nos_number_precision: int | str
    write_nos_number_scale: int | str
    cast_varchar_type: bool | str


@dataclass
class ConfigFilePaths:
    source: str | None
    target: str | None
    extractor: str | None
    applier: str | None
    filter: str | None
    map: str | None
