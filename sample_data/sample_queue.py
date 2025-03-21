import sqlite3
from datetime import datetime, timedelta

def create_sample_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create QUEUE table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS QUEUE (
            table_name TEXT PRIMARY KEY,
            insert_time TIMESTAMP,
            trigger_time TIMESTAMP,
            status TEXT,
            priority INTEGER
        )
    ''')

    # Create QUEUE_HISTORY table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS QUEUE_HISTORY (
            table_name TEXT,
            status TEXT,
            timestamp TIMESTAMP,
            priority INTEGER
        )
    ''')

    # Insert sample data into QUEUE table
    sample_data = [
        ('aditya.table_1', datetime.now() - timedelta(minutes=10), None, 'Q', 0),
        ('database_1.table_2', datetime.now() - timedelta(minutes=5), None, 'Q', 1),
        ('database_3.table_1', datetime.now(), None, 'Q', 99),
    ]

    cursor.executemany('''
        INSERT INTO QUEUE (table_name, insert_time, trigger_time, status, priority)
        VALUES (?, ?, ?, ?, ?)
    ''', sample_data)

    # Insert sample data into QUEUE_HISTORY table
    sample_history_data = [
        ('database_1.table_1', 'Q', datetime.now() - timedelta(minutes=10), 0),
        ('database_1.table_2', 'Q', datetime.now() - timedelta(minutes=5), 1),
        ('database_3.table_1', 'Q', datetime.now(), 99),
    ]

    cursor.executemany('''
        INSERT INTO QUEUE_HISTORY (table_name, status, timestamp, priority)
        VALUES (?, ?, ?, ?)
    ''', sample_history_data)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_sample_database('sample_data/sample_queue.db')