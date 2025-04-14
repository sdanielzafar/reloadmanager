import pytest
import logging
from unittest.mock import patch, MagicMock

from reloadmanager.cli.event_report import main
from reloadmanager.reporting.event_reporter import EventReporter


class TestEventReporter(EventReporter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, databricks_client=MagicMock())

    def run(self):
        print("EventReporter run called")


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.catalog = 'mock_catalog'
    args.target_table = 'mock_table'
    args.log_level = 'INFO'
    return args


@patch('reloadmanager.cli.event_report.EventReporter', new=TestEventReporter)
def test_main_happy_path(mock_args, capsys):
    main(mock_args)

    captured = capsys.readouterr()
    assert "EventReporter run called" in captured.out


def test_main_invalid_log_level(mock_args):
    mock_args.log_level = 'INVALID'

    with pytest.raises(ValueError, match="Invalid log level"):
        main(mock_args)


@patch('reloadmanager.cli.event_report.EventReporter', new=TestEventReporter)
@patch('reloadmanager.cli.event_report.logging.getLogger')
def test_main_sets_logging_level(mock_get_logger, mock_args):
    logger_mock = MagicMock()
    mock_get_logger.return_value = logger_mock
    mock_args.log_level = 'DEBUG'

    main(mock_args)

    logger_mock.setLevel.assert_called_once_with(logging.DEBUG)
