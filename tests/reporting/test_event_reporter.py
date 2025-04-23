import pytest
from unittest.mock import MagicMock

from reloadmanager.reporting.event_reporter import EventReporter


@pytest.fixture
def reporter():
    mock_dbx_client = MagicMock()
    return EventReporter(databricks_client=mock_dbx_client)


def test_fmt_row(reporter):
    assert reporter.fmt_row(("a", "b", 3)) == "('a', 'b', '3')"
    assert reporter.fmt_row(("a",)) == "('a')"
    assert reporter.fmt_row(()) == "()"


def test_fmt_values(reporter):
    case_a = [
        ("a", "b", 1),
        ("c", "d", 2)
    ]

    assert reporter.fmt_values(case_a) == "('a', 'b', '1'), ('c', 'd', '2')"


def test_fmt_values_unknown_error(reporter):
    case_a = [
        ("a", "b", "Re-run the command with '/arcion/replicant-cli/bin a'"),
        ("c", "d", "Re-run the command with '/arcion/replicant-cli/bin b'")
    ]

    assert reporter.fmt_values(case_a) == "('a', 'b', 'Re-run the command with /arcion/replicant-cli/bin a'), " \
                                          "('c', 'd', 'Re-run the command with /arcion/replicant-cli/bin b')"
