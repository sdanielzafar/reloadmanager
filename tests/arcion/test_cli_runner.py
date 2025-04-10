import pytest
from unittest.mock import patch, mock_open, MagicMock
import subprocess
from reloadmanager.arcion.cli_runner import run_cli_cmd


def test_run_cli_cmd_success():
    mock_command = ["echo", "hello"]
    mock_output = "hello world\n"

    with patch("subprocess.run") as mock_run, patch("builtins.open", mock_open()) as mock_file:
        mock_run.return_value = MagicMock(stdout=mock_output)
        result = run_cli_cmd(mock_command, "log.txt")

        mock_run.assert_called_once_with(
            mock_command,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        mock_file().write.assert_called_once_with(mock_output)
        assert result == mock_output.strip()


def test_run_cli_cmd_called_process_error():
    mock_command = ["fake", "command"]
    mock_output = "error: command not found\n"
    error = subprocess.CalledProcessError(
        returncode=1, cmd=mock_command, output=mock_output
    )

    with patch("subprocess.run", side_effect=error), patch("builtins.open", mock_open()) as mock_file:
        with pytest.raises(subprocess.CalledProcessError):
            run_cli_cmd(mock_command, "log.txt")
        mock_file().write.assert_called_once_with(mock_output)


def test_run_cli_cmd_general_exception():
    mock_command = ["whatever"]
    with patch("subprocess.run", side_effect=ValueError("boom")), patch("builtins.open", mock_open()) as mock_file:
        with pytest.raises(ValueError, match="boom"):
            run_cli_cmd(mock_command, "log.txt")
        mock_file().write.assert_not_called()
