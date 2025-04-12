import pytest
import logging
from unittest.mock import patch, MagicMock

from reloadmanager.batch_loader.batch_loader import BatchLoader
from reloadmanager.cli.batch_load import main


class TestBatchLoader(BatchLoader):
    def __init__(self, *args, **kwargs):
        with patch.object(BatchLoader, "read_batch_input", return_value=[]), \
                patch("reloadmanager.batch_loader.batch_loader.BatchQueue"):
            super().__init__(*args, **kwargs)

    def run(self):
        print("Called")


@pytest.fixture
def mock_args():
    args = MagicMock()
    args.input_csv = 'some_input.csv'
    args.output = '/some/output'
    args.catalog = 'my_catalog'
    args.avoid_window_utc = "None"
    args.tpt_threads = '4'
    args.writenos_threads = '2'
    args.lock_rows = True
    return args


@patch('reloadmanager.cli.batch_load.BatchLoader', new=TestBatchLoader)
def test_main_happy_path(mock_args, capsys):
    mock_args.log_level = 'INFO'

    main(mock_args)

    captured = capsys.readouterr()
    assert "Called" in captured.out


def test_main_invalid_log_level_raises(mock_args):
    mock_args.log_level = '🤡NOTALEVEL🤡'

    with pytest.raises(ValueError, match="Invalid log level"):
        main(mock_args)


@patch('reloadmanager.cli.batch_load.BatchLoader', new=TestBatchLoader)
@patch('reloadmanager.cli.batch_load.logging.getLogger')
def test_main_sets_logging_level(mock_get_logger, mock_args):
    mock_args.log_level = 'DEBUG'
    logger_mock = MagicMock()
    mock_get_logger.return_value = logger_mock

    main(mock_args)

    logger_mock.setLevel.assert_called_once_with(logging.DEBUG)
