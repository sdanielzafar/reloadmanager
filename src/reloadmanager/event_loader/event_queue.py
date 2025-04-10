import sys

from reloadmanager.mixins.logging_mixin import LoggingMixin

if sys.platform.startswith("darwin"):
    import sqlite3 as sqlite3
else:
    import pysqlite3 as sqlite3
import time
import os

from reloadmanager.event_loader.models import QueueRecord
from reloadmanager.utils.datetimes import EventTime


class EventQueue(LoggingMixin):
    def __init__(self, db_path: str):
        self.db_path: str = db_path

    def create(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS QUEUE (
                    source_table TEXT PRIMARY KEY,
                    target_table TEXT,
                    event_time TEXT,
                    trigger_time TEXT,
                    strategy TEXT,
                    lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                    status CHAR(1),
                    priority INTEGER,
                    event_time_latest TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS QUEUE_HISTORY (
                    source_table TEXT,
                    target_table TEXT,
                    status TEXT,
                    event_time TEXT,
                    trigger_time TEXT,
                    finish_time TEXT,
                    duration_min REAL,
                    strategy TEXT,
                    lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                    priority INTEGER,
                    error TEXT,
                    PRIMARY KEY (source_table, event_time)
                )
            """)

    def truncate(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM QUEUE")
            conn.execute("DELETE FROM QUEUE_HISTORY")

    def requeue_running(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE QUEUE
                SET status = 'Q'
                WHERE status = 'R'
                RETURNING source_table, event_time
                """)
            rows: list[tuple] = cursor.fetchall()

            for source_table, event_time in rows:
                self.logger.info(f"Put {source_table} back in queue...")
                cursor.execute("""
                DELETE FROM QUEUE_HISTORY 
                WHERE source_table = ?
                AND event_time = ?
                """, (source_table, event_time))

    def poll(self, strategy: str) -> tuple:
        with sqlite3.connect(self.db_path, timeout=15) as conn:
            cursor = conn.cursor()
            now = EventTime.from_epoch(int(time.time()))

            cursor.execute("""
                UPDATE QUEUE
                SET status = 'R',
                    trigger_time = ?
                WHERE rowid IN (
                    SELECT rowid
                    FROM QUEUE
                    WHERE status = 'Q'
                      AND strategy = ?
                      AND priority > 0
                    ORDER BY priority DESC
                    LIMIT 1
                )
                RETURNING source_table, target_table, event_time, strategy, lock_rows, priority
            """, (str(now), strategy))
            row = cursor.fetchone()

            if not row:
                return ()

            source_table, target_table, event_time, strategy, lock_rows, priority = row

            cursor.execute("""
                SELECT status FROM QUEUE_HISTORY 
                WHERE source_table = ?
                AND event_time = ?
            """, (source_table, event_time))
            row = cursor.fetchone()

            if not row:
                cursor.execute("""
                    INSERT INTO QUEUE_HISTORY (
                        source_table, target_table, status, event_time, trigger_time, strategy, lock_rows, priority
                    ) VALUES (?, ?, 'RUNNING', ?, ?, ?, ?, ?)
                """, (source_table, target_table, event_time, str(now), strategy, lock_rows, priority))
            else:
                # if it's status "RUNNING" we do nothing, but...
                if row[0] == "SUCCESS" or row[0] == "FAILED":
                    self.logger.warning(
                        f"Source table: {source_table} with event time {event_time} was previously processed with "
                        f"status {row[0]}, removing from QUEUE_HISTORY and reprocessing it."
                    )
                    cursor.execute("""
                        DELETE FROM QUEUE_HISTORY 
                        WHERE source_table = ?
                        AND event_time = ?
                    """, (source_table, event_time))

        return source_table, target_table, lock_rows, event_time

    def upsert_queued(self, tables: list[QueueRecord]):
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany("""
            INSERT INTO QUEUE (
                source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority, 
                event_time_latest
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_table) DO UPDATE SET
                priority = excluded.priority,
                event_time_latest = excluded.event_time
            WHERE QUEUE.status = 'Q'
            """, tables)

    @property
    def in_queue(self) -> list[QueueRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM QUEUE
                WHERE status = 'Q'
            """)
            rows: list[tuple] = cursor.fetchall()
        return [QueueRecord(*row) for row in rows]

    def dequeue(self, source_table: str, event_time: str, end_time: float, duration: float, status: str, error: str):

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE FROM QUEUE
            WHERE source_table = ?
            AND event_time = ?
            AND status = 'R'
            """, (source_table, event_time))

            cursor.execute("""
                UPDATE QUEUE_HISTORY
                SET status = ?,
                    finish_time = ?,
                    duration_min = ?,
                    error = ?
                WHERE source_table = ?
                AND event_time = ?
            """, (status, str(EventTime.from_epoch(int(end_time))), duration, error, source_table, event_time))

    def last_load_time(self) -> str:
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT MAX(et) FROM (
                SELECT MAX(COALESCE(event_time_latest, event_time)) as et FROM QUEUE
                UNION ALL 
                SELECT MAX(event_time) as et FROM QUEUE_HISTORY
                )
            """)
            row = cursor.fetchone()
            if not row:
                return ""
            return row[0]

    def __len__(self) -> int:
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT COUNT(*) FROM QUEUE WHERE status = 'Q'
                """)
                return cursor.fetchone()[0]
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                return 0
            else:
                raise
