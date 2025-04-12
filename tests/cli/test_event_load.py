import pytest
import logging
from unittest.mock import patch, MagicMock

from reloadmanager.cli.event_load import main
from reloadmanager.event_loader.event_loader import EventLoader


class TestEventLoader(EventLoader):
    def __init__(self, *args, **kwargs):
        with patch("reloadmanager.event_loader.event_loader.EventQueue"), \
             patch("reloadmanager.event_loader.event_loader.TeradataClient"):
            super().__init__(*args, **kwargs)

    def run(self):
        print("EventLoader run called")


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.catalog = 'mock_catalog'
    args.tpt_threads = '4'
    args.writenos_threads = '2'
    args.start = '2024-01-01 00:00:00'
    args.reset_queue = 'false'
    args.table_metadata_path = 'some/path.csv'
    args.avoid_window_utc = '6-18'
    args.sqlite_path = 'db.sqlite'
    args.log_level = 'INFO'
    return args


@patch('reloadmanager.cli.event_load.EventLoader', new=TestEventLoader)
def test_main_happy_path(mock_args, capsys):
    main(mock_args)

    captured = capsys.readouterr()
    assert "EventLoader run called" in captured.out


def test_main_invalid_log_level(mock_args):
    mock_args.log_level = 'WHACK'

    with pytest.raises(ValueError, match="Invalid log level"):
        main(mock_args)


def test_main_invalid_reset_queue(mock_args):
    mock_args.reset_queue = 'maybe'

    with pytest.raises(ValueError, match="Argument reset-queue must be 'true' or 'false'"):
        main(mock_args)


@patch('reloadmanager.cli.event_load.EventLoader', new=TestEventLoader)
@patch('reloadmanager.cli.event_load.logging.getLogger')
def test_main_sets_logging_level(mock_get_logger, mock_args):
    logger_mock = MagicMock()
    mock_get_logger.return_value = logger_mock
    mock_args.log_level = 'DEBUG'

    main(mock_args)

    logger_mock.setLevel.assert_called_once_with(logging.DEBUG)
