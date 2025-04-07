import pysqlite3
import time
import os

from reloadmanager.event_loader.models import QueueRecord
from reloadmanager.utils.datetimes import EventTime


class EventQueue:
    def __init__(self, db_path: str):
        self.db_path: str = db_path

    def create_queue(self):
        os.makedirs(self.db_path, exist_ok=True)

        with pysqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS QUEUE (
                    source_table TEXT PRIMARY KEY,
                    target_table TEXT,
                    event_time TEXT,
                    trigger_time TEXT,
                    strategy TEXT,
                    lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                    status CHAR(1),
                    priority INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS QUEUE_HISTORY (
                    source_table TEXT,
                    target_table TEXT,
                    status CHAR(1),
                    event_time TEXT,
                    trigger_time TEXT,
                    finish_time TEXT,
                    duration_min REAL,
                    strategy TEXT,
                    lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                    priority INTEGER,
                    PRIMARY KEY (source_table, event_time)
                )
            """)

    def poll_queue(self, strategy: str) -> tuple:
        with pysqlite3.connect(self.db_path, timeout=15) as conn:
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
                INSERT INTO QUEUE_HISTORY (
                    source_table, target_table, status, event_time, trigger_time, strategy, lock_rows, priority
                ) VALUES (?, ?, 'R', ?, ?, ?, ?, ?)
            """, (source_table, target_table, event_time, now, strategy, lock_rows, priority))

        return source_table, target_table, lock_rows, event_time

    def upsert_queued(self, tables: list[QueueRecord]):
        with pysqlite3.connect(self.db_path) as conn:
            conn.executemany("""
            INSERT INTO QUEUE (
                source_table, target_table, event_time, trigger_time, strategy, lock_rows, status, priority
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_table) DO UPDATE SET
                priority = excluded.priority
            WHERE QUEUE.status = 'Q'
            """, tables)

    @property
    def in_queue(self) -> list[QueueRecord]:
        with pysqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM QUEUE
                WHERE status = 'Q'
            """)
            rows: list[tuple] = cursor.fetchall()
        return [QueueRecord(*row) for row in rows]

    def dequeue(self, source_table: str, event_time: str, end_time: float, duration: float):

        with pysqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE FROM QUEUE
            WHERE source_table = ?
            AND event_time = ?
            AND status = 'R'
            """, (source_table, event_time))

            cursor.execute("""
                UPDATE QUEUE_HISTORY
                SET status = 'F',
                    finish_time = ?,
                    duration_min = ?
                WHERE source_table = ?
                AND event_time = ?
            """, (end_time, duration, source_table, event_time))

    def recent_queued(self) -> str:
        with pysqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT MAX(event_time) FROM QUEUE WHERE status = 'Q'
            """)
            return cursor.fetchone()[0]

    def __len__(self) -> int:
        with pysqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT COUNT(*) FROM QUEUE WHERE status = 'Q'
            """)
            return cursor.fetchone()[0]
