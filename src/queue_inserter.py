from .sqlite_mixin import SQLiteMixin
from .table_priorities import TablePriorities
from datetime import datetime

class QueueInserter(SQLiteMixin):
    def __init__(self, db_path, table_priorities):
        super().__init__(db_path)
        self.table_priorities = table_priorities
        self.create_tables()

    def create_tables(self):
        self.execute('''
            CREATE TABLE IF NOT EXISTS QUEUE (
                table_name TEXT PRIMARY KEY,
                insert_time TIMESTAMP,
                trigger_time TIMESTAMP,
                status TEXT,
                priority INTEGER
            )
        ''')
        self.commit()

    def insert_table(self, table_name):
        table_info = self.table_priorities.get_table_info(table_name)
        if table_info:
            priority = int(table_info['priority'])
            insert_time = datetime.now()
            self.execute('''
                INSERT INTO QUEUE (table_name, insert_time, status, priority)
                VALUES (?, ?, ?, ?)
            ''', (table_name, insert_time, 'Q', priority))
            self.commit()

    def query_teradata(self):
        # Placeholder for actual Teradata query logic
        return ["database_1.table_1", "database_1.table_2", "database_3.table_1"]

    def run(self):
        tables_to_reload = self.query_teradata()
        for table in tables_to_reload:
            self.insert_table(table)