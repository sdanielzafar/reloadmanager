from subprocess import CalledProcessError

import pytest
from unittest.mock import MagicMock, patch, mock_open, PropertyMock
from reloadmanager.arcion.replicant_runner import ReplicantRunner, ReplicantRunError


@pytest.fixture
def mock_builder():
    builder = MagicMock()
    builder.id = "TEST_ID"
    builder.config_dir_path = "/mock/config"
    builder.config_file_paths.source = "source.yaml"
    builder.config_file_paths.target = "target.yaml"
    builder.config_file_paths.extractor = "extractor.yaml"
    builder.config_file_paths.applier = "applier.yaml"
    builder.config_file_paths.filter = "filter.yaml"
    builder.config_file_paths.map = "map.yaml"
    return builder


@pytest.fixture
def mock_cli_runner():
    cli = MagicMock()
    return cli


@pytest.fixture
def runner(mock_builder, mock_cli_runner):
    return ReplicantRunner(mock_builder, cli_runner=mock_cli_runner)


@patch("os.path.exists", return_value=False)
def test_error_log_missing(mock_exists, runner):
    assert runner.error == ""


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="""
    Some random info
    Syntax error near line 42
    ExtractorException in pipeline
""")
def test_error_log_parses_unique_and_prefers_syntax_error(mock_open_file, mock_exists, runner):
    assert "Syntax error" in runner.error


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="""
Progress: ==================================================================100.00%=====================================

Elapsed time: 00:00:45                            ETA: 00:00:00                                     Buffered Rows: 0
Peak Rate: 2575957.04                             Average Rate: 62828.22                            Current Rate: 0.00
Used Memory(%): 1.67

Table name                                                  Rows                   Progress                    ETA      
________________________________________________________________________________________________________________________
`1DP_MIGRATION_DEV_CATALOG_3573379518104516`.`SGEN         2578533         =========================        00:00:00    

replicant exited with error code: 0

""")
def test_num_records_parses_valid_row_count(mock_open_file, mock_exists, runner):
    assert runner.num_records == 2578533


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="""
JAVA PATH: /usr/bin/java
openjdk version "1.8.0_442"
OpenJDK Runtime Environment (build 1.8.0_442-b06)
OpenJDK 64-Bit Server VM (build 25.442-b06, mixed mode)
replicant exited with error code: 1
Resuming replicant........
""")
def test_num_records_returns_zero_on_error_exit_code(mock_open_file, mock_exists, runner):
    assert runner.num_records == 0


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="""
Progress:                                                                   0.00%

Elapsed time: 00:00:09                            ETA: 00:00:00                                     Peak Rate: 0.00
Average Rate: 0.00                                Current Rate: 0.00                                Used Memory(%): 1.10


Table name                                                  Rows                   Progress                    ETA      
________________________________________________________________________________________________________________________

replicant exited with error code: 0
""")
def test_num_records_returns_zero_on_missing_row_info(mock_open_file, mock_exists, runner):
    assert runner.num_records == 0


@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="""
    just junk
    replicant exited with no clues
""")
def test_num_records_raises_on_weird_log(mock_open_file, mock_exists, runner):
    with pytest.raises(Exception, match="Issue parsing log file"):
        _ = runner.num_records


def test_handle_failure_raises_if_error_and_records_exist(runner):
    with pytest.raises(ReplicantRunError, match="boom"):
        runner._handle_failure("boom", 10)


def test_handle_failure_raises_on_syntax_error(runner):
    with pytest.raises(ReplicantRunError, match="Syntax error"):
        runner._handle_failure("Syntax error near clause", 0)


@patch.object(ReplicantRunner, "logger", new_callable=MagicMock)
def test_handle_failure_warns_if_zero_rows_and_non_syntax_error(mock_logger, runner):
    runner._handle_failure("Extractor failed", 0)
    mock_logger.warning.assert_called_once()


def test_handle_failure_raises_on_total_unknown(runner):
    with pytest.raises(ReplicantRunError, match="Unknown error"):
        runner._handle_failure("", 0)


@patch.object(ReplicantRunner, "logger", new_callable=MagicMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.log_file", new_callable=MagicMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.num_records", new_callable=MagicMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.error", new_callable=PropertyMock)
def test_run_snapshot_success(mock_error, mock_num_records, mock_log_file, mock_logger, runner):
    runner.builder.write_config_files = MagicMock()
    runner.cli.run = MagicMock()

    mock_error.return_value = ""
    mock_num_records.return_value = 100

    runner.run_snapshot()

    runner.builder.write_config_files.assert_called_once()
    runner.cli.run.assert_called_once()


@patch.object(ReplicantRunner, "logger", new_callable=MagicMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.error", new_callable=PropertyMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.num_records", new_callable=MagicMock)
@patch("reloadmanager.arcion.replicant_runner.ReplicantRunner.log_file", new_callable=MagicMock)
def test_run_snapshot_with_failure_triggers_error_handling(mock_error, mock_num_records, mock_log_file, mock_logger, runner):
    runner.builder.write_config_files = MagicMock()
    runner.cli.run = MagicMock(side_effect=CalledProcessError(1, ["fail"]))
    mock_error.return_value = "boom"
    mock_num_records.return_value = 0

    with pytest.raises(ReplicantRunError):
        runner.run_snapshot()
