import pytest
import subprocess
from reloadmanager.arcion.cli_runner import CliRunner


@pytest.fixture
def mock_file_writer():
    log = {}

    def _writer(path, content):
        log[path] = content
    return log, _writer


def test_run_success(mock_file_writer):
    log, writer = mock_file_writer

    def mock_runner(command):
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="Command executed successfully\n")

    runner = CliRunner(file_writer=writer, process_runner=mock_runner)
    output = runner.run(["echo", "hello"], "log.txt")

    assert output == "Command executed successfully"
    assert log["log.txt"] == "Command executed successfully\n"


def test_run_called_process_error(mock_file_writer):
    log, writer = mock_file_writer

    def mock_runner(command):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            output="Simulated error output\nLine 2"
        )

    runner = CliRunner(file_writer=writer, process_runner=mock_runner)

    with pytest.raises(subprocess.CalledProcessError):
        runner.run(["bad", "cmd"], "log_err.txt")

    assert log["log_err.txt"] == "Simulated error output\nLine 2"


def test_run_generic_exception(mock_file_writer):
    log, writer = mock_file_writer

    def mock_runner(command):
        raise RuntimeError("Unexpected failure")

    runner = CliRunner(file_writer=writer, process_runner=mock_runner)

    with pytest.raises(RuntimeError):
        runner.run(["explode"], "log_crash.txt")

    # Should not write anything to the file in this case
    assert "log_crash.txt" not in log


def test_run_empty_output(mock_file_writer):
    log, writer = mock_file_writer

    def mock_runner(command):
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="")

    runner = CliRunner(file_writer=writer, process_runner=mock_runner)
    output = runner.run(["echo"], "empty_log.txt")

    assert output == ""
    assert log["empty_log.txt"] == ""


def test_run_called_process_error_no_output(mock_file_writer):
    log, writer = mock_file_writer

    def mock_runner(command):
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=command,
            output=None  # this is the edge case
        )

    runner = CliRunner(file_writer=writer, process_runner=mock_runner)

    with pytest.raises(subprocess.CalledProcessError):
        runner.run(["fail"], "no_output.txt")

    # Should write empty string to the log file
    assert log["no_output.txt"] == ""
