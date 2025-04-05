import pysqlite3

from reloadmanager.batch_loader.input_record import InputRecord


class BatchQueue:
    def __init__(self, db_path: str):
        self.db_path: str = db_path

    def create_queue(self):

        with pysqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DROP TABLE IF EXISTS BULK_QUEUE
            """)

        with pysqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE BULK_QUEUE (
                    source_table TEXT PRIMARY KEY,
                    target_table TEXT,
                    strategy TEXT,
                    lock_rows INTEGER CHECK(lock_rows IN (0, 1)),
                    status CHAR(1),
                    priority INTEGER
                )
            """)

    def enqueue_input(self, input_records: list[InputRecord]):
        len_input: int = len(input_records)
        priorities = reversed(range(len_input))
        input_data = (
            (i.source, i.target, i.strategy, i.lock_rows, 'Q', p) for i, p in zip(input_records, priorities)
        )
        with pysqlite3.connect(self.db_path) as conn:
            conn.executemany("""
            INSERT INTO BULK_QUEUE (source_table, target_table, strategy, lock_rows, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """, input_data)

    def poll_queue(self, strategy: str):
        with pysqlite3.connect(self.db_path, timeout=15) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE BULK_QUEUE
                SET status = 'R'
                WHERE rowid IN (
                    SELECT rowid
                    FROM BULK_QUEUE
                    WHERE status = 'Q'
                      AND strategy = ?
                    ORDER BY priority DESC
                    LIMIT 1
                )
                RETURNING source_table, target_table, lock_rows
            """, (strategy,))
            row = cursor.fetchone()

        if row:
            source_table, target_table, lock_rows = row
            return source_table, target_table, lock_rows
        else:
            return ()

    def dequeue(self, source_table: str):
        with pysqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE FROM BULK_QUEUE
            WHERE source_table = ?
            AND status = 'R'
            """, (source_table,))

    def __len__(self) -> int:
        with pysqlite3.connect(self.db_path, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT COUNT(*) FROM BULK_QUEUE WHERE status = 'Q'
            """)
            return cursor.fetchone()[0]
