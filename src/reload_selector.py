from .sqlite_mixin import SQLiteMixin
from .table_priorities import TablePriorities
from datetime import datetime, timedelta
import time

class ReloadSelector(SQLiteMixin):
    def __init__(self, db_path, table_priorities):
        super().__init__(db_path)
        self.table_priorities = table_priorities

    def update_priorities(self):
        self.execute('SELECT table_name, insert_time FROM QUEUE')
        rows = self.fetchall()
        for row in rows:
            table_name, insert_time = row
            table_info = self.table_priorities.get_table_info(table_name)
            max_staleness = int(table_info['max_staleness'])
            elapsed_minutes = (datetime.now() - insert_time).total_seconds() / 60
            remaining_minutes = max_staleness - elapsed_minutes
            score = self.calculate_score(remaining_minutes)
            priority = score * int(table_info['priority'])
            self.execute('''
                UPDATE QUEUE
                SET priority = ?
                WHERE table_name = ?
            ''', (priority, table_name))
        self.commit()

    def calculate_score(self, remaining_minutes):
        if remaining_minutes > 60:
            return 0
        elif 45 < remaining_minutes <= 60:
            return 1
        elif 30 < remaining_minutes <= 45:
            return 2
        elif 15 < remaining_minutes <= 30:
            return 3
        elif 10 < remaining_minutes <= 15:
            return 4
        elif 5 < remaining_minutes <= 10:
            return 5
        elif 3 < remaining_minutes <= 5:
            return 6
        else:
            return 7

    def run(self):
        while True:
            self.update_priorities()
            self.execute('SELECT table_name FROM QUEUE WHERE status = "Q" ORDER BY priority DESC LIMIT 1')
            row = self.fetchone()
            if row:
                table_name = row[0]
                self.execute('''
                    UPDATE QUEUE
                    SET status = "R", trigger_time = ?
                    WHERE table_name = ?
                ''', (datetime.now(), table_name))
                self.commit()
                self.run_job(table_name)
                self.execute('''
                    DELETE FROM QUEUE
                    WHERE table_name = ?
                ''', (table_name,))
                self.commit()
            else:
                time.sleep(60)

    def run_job(self, table_name):
        # Placeholder for actual job running logic
        print(f"Running job for {table_name}")