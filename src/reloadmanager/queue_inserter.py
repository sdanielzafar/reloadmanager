from datetime import datetime
from reloadmanager.clients.sqlite_client import SQLiteClient
from reloadmanager.clients.teradata_client import TeradataClient


class QueueInserter:
    def __init__(self, db_path, table_priorities):
        self.table_priorities = table_priorities
        self.td_client: TeradataClient = TeradataClient()
        self.sqlite_client: SQLiteClient = SQLiteClient(db_path)
        self.create_tables()

    def create_tables(self):
        self.sqlite_client.execute('''
            CREATE TABLE IF NOT EXISTS QUEUE (
                table_name TEXT PRIMARY KEY,
                inserted_ts TIMESTAMP,
                trigger_ts TIMESTAMP,
                status CHAR(1),
                priority INTEGER
            )
        ''')
        self.sqlite_client.execute('''
            CREATE TABLE IF NOT EXISTS QUEUE_HIST (
                table_name TEXT,
                status CHAR(1),
                ts TIMESTAMP,
                priority INTEGER
            )
        ''')
        self.sqlite_client.commit()

    def insert_table(self, table_name):
        table_info = self.table_priorities.get_table_info(table_name)
        if table_info:
            priority = int(table_info['priority'])
            insert_time = datetime.now()
            self.sqlite_client.execute('''
                INSERT INTO QUEUE (table_name, insert_time, status, priority)
                VALUES (?, ?, ?, ?)
            ''', (table_name, insert_time, 'Q', priority))
            self.sqlite_client.commit()

    def query_teradata(self):
        self.td_client.query(f"""
        SELECT 
            ObjectDatabaseName || '.' || ObjectTableName as tbl, 
            LoadCompletionTS as reload_ts 
        FROM BACKUPDB.EBI_LOAD_COMPLETION_TS_GOLD 
        WHERE LoadCompletionTS > '2025-03-18 05:15:00'
        """)
        return ["database_1.table_1", "database_1.table_2", "database_3.table_1"]

    def run(self):
        tables_to_reload = self.query_teradata()
        for table in tables_to_reload:
            self.insert_table(table)
