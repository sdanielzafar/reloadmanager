# test_event_queue.py

import os
import tempfile
import time
import pytest
import sqlite3

from reloadmanager.event_loader.models import QueueRecord
from reloadmanager.utils.datetimes import EventTime
from reloadmanager.event_loader.event_queue import EventQueue  # Replace with the actual import path


@pytest.fixture
def temp_db_path():
    """
    Yields a transient file path for the test SQLite database.
    We conjure it in a temp directory to ensure no cross-test contamination.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_event_queue.db")
        yield db_path


@pytest.fixture
def event_queue(temp_db_path):
    """
    Yields an EventQueue instance, freshly instantiated
    with tables created for each test.
    """
    eq = EventQueue(temp_db_path)
    eq.create()
    return eq


def test_create_tables(event_queue, temp_db_path):
    """
    Verifies that the tables are correctly created in the ephemeral DB.
    """
    # Using sqlite3 directly to validate table presence
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert 'QUEUE' in tables
    assert 'QUEUE_HISTORY' in tables

    conn.close()


def test_truncate(event_queue, temp_db_path):
    """
    Proves that truncate expunges everything from the QUEUE table.
    """
    # Prepopulate with data
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("""
            INSERT INTO QUEUE (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES ('source1', 'target1', '2025-01-01', '2025-01-01', 'some_strategy', 1, 'Q', 5)
        """)

    event_queue.truncate()

    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM QUEUE")
        count = cursor.fetchone()[0]
        assert count == 0


def test_poll_queue(event_queue, temp_db_path):
    """
    Tests that poll_queue updates status to 'R',
    logs new row in QUEUE_HISTORY, then returns the polled row properly.
    """
    # Insert multiple rows with one matching strategy
    records = [
        ("source1", "target1", "2025-01-01", "", "strategy_a", 1, "Q", 5),
        ("source2", "target2", "2025-01-02", "", "strategy_b", 0, "Q", 8),
        ("source3", "target3", "2025-01-03", "", "strategy_b", 1, "Q", 2),
    ]
    with sqlite3.connect(temp_db_path) as conn:
        conn.executemany("""
            INSERT INTO QUEUE 
            (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

    # Poll for strategy_b – expects the highest priority row
    polled = event_queue.poll_queue("strategy_b")
    # Should be ('source2', 'target2', 0, '2025-01-02') from the code’s return signature
    assert polled
    assert polled[0] == "source2"
    assert polled[1] == "target2"
    assert polled[2] == 0  # lock_rows
    assert polled[3] == "2025-01-02"

    # Confirm QUEUE status is updated to 'R'
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM QUEUE WHERE source_table='source2'")
        status = cursor.fetchone()[0]
        assert status == 'R'

    # Confirm QUEUE_HISTORY got a new row with status='R'
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM QUEUE_HISTORY WHERE source_table='source2'")
        hist_status = cursor.fetchone()[0]
        assert hist_status == 'R'


def test_upsert_queued(event_queue, temp_db_path):
    """
    Ensures upsert_queued properly inserts or updates records
    only when QUEUE.status is 'Q'.
    """
    # Insert an initial row manually that has status 'Q'
    initial_record = ("sourceA", "targetA", "2025-01-01", "", "stratA", 1, "Q", 1)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("""
            INSERT INTO QUEUE
            (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_record)

    # Attempt to upsert a new priority for sourceA
    # and insert a brand-new row sourceB
    new_records = [
        QueueRecord("sourceA", "targetA", "2025-01-01", "", "stratA", True, "Q", 10),
        QueueRecord("sourceB", "targetB", "2025-01-02", "", "stratB", False, "Q", 99),
    ]
    event_queue.upsert_queued(new_records)

    # Verify priority update
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT priority FROM QUEUE WHERE source_table='sourceA'")
        updated_priority = cursor.fetchone()[0]
        assert updated_priority == 10

        # Verify new row was inserted
        cursor.execute("SELECT priority FROM QUEUE WHERE source_table='sourceB'")
        inserted_priority = cursor.fetchone()[0]
        assert inserted_priority == 99


def test_in_queue(event_queue, temp_db_path):
    """
    Demonstrates retrieval of all 'Q' records.
    """
    records = [
        ("source1", "target1", "2025-01-01", "", "strategy_a", 1, "Q", 2),
        ("source2", "target2", "2025-01-02", "", "strategy_b", 0, "F", 9),  # finished
        ("source3", "target3", "2025-01-03", "", "strategy_a", 1, "Q", 7),
    ]
    with sqlite3.connect(temp_db_path) as conn:
        conn.executemany("""
            INSERT INTO QUEUE 
            (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

    queued = event_queue.in_queue
    # We anticipate only 2 'Q' status
    assert len(queued) == 2

    # Confirm the IDs match
    source_tables = [r.source_table for r in queued]
    assert "source1" in source_tables
    assert "source3" in source_tables
    assert "source2" not in source_tables


def test_dequeue(event_queue, temp_db_path):
    """
    Confirms we can delete an entry from QUEUE after completion
    and update its matching QUEUE_HISTORY row with finish time and duration.
    """
    # Insert a row in QUEUE as running (R) and replicate in QUEUE_HISTORY
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("""
            INSERT INTO QUEUE (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES ('sourceZ', 'targetZ', '2025-01-01', '2025-01-01', 'stratZ', 1, 'R', 5)
        """)
        conn.execute("""
            INSERT INTO QUEUE_HISTORY (source_table, target_table, status, event_time, trigger_time,
                                       finish_time, duration_min, strategy, lock_rows, priority)
            VALUES ('sourceZ', 'targetZ', 'R', '2025-01-01', '2025-01-01', '', NULL, 'stratZ', 1, 5)
        """)

    end_time = str(EventTime.from_epoch(int(time.time())))
    duration = 2.5
    event_queue.dequeue("sourceZ", "2025-01-01", end_time, duration, 999, "SUCCESS", "")

    # Confirm removal from QUEUE
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM QUEUE WHERE source_table='sourceZ'
        """)
        count = cursor.fetchone()[0]
        assert count == 0

        # Confirm QUEUE_HISTORY got updated
        cursor.execute("""
            SELECT status, finish_time, duration_min
            FROM QUEUE_HISTORY
            WHERE source_table='sourceZ'
        """)
        row = cursor.fetchone()
        assert row[0] == 'F'
        assert row[1] == end_time
        assert row[2] == duration
        assert row[3] == 999


def test_recent_queued(event_queue, temp_db_path):
    """
    Checks if recent_queued gives the newest event_time among 'Q' rows.
    """
    # Insert multiple Q and non-Q statuses
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("""
            INSERT INTO QUEUE (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES ('tableA', 'targetA', '2025-01-01', '', 'stratA', 1, 'Q', 5)
        """)
        conn.execute("""
            INSERT INTO QUEUE (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES ('tableB', 'targetB', '2025-01-02', '', 'stratB', 0, 'F', 3)
        """)
        conn.execute("""
            INSERT INTO QUEUE (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES ('tableC', 'targetC', '2025-01-03', '', 'stratC', 0, 'Q', 9)
        """)

    recent = event_queue.recent_queued()
    # Expect '2025-01-03'
    assert recent == '2025-01-03'


def test_len(event_queue, temp_db_path):
    """
    Verifies the __len__ method returns the count of 'Q' records.
    """
    # Insert some rows with status=Q
    records = [
        ("source1", "target1", "2025-01-01", "", "strategy_a", 1, "Q", 5),
        ("source2", "target2", "2025-01-02", "", "strategy_b", 0, "Q", 10),
        ("source3", "target3", "2025-01-03", "", "strategy_a", 1, "F", 2),
    ]
    with sqlite3.connect(temp_db_path) as conn:
        conn.executemany("""
            INSERT INTO QUEUE 
            (source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

    # Should only count the Q ones
    assert len(event_queue) == 2
