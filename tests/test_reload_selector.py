import pytest
import sqlite3
from src.reload_selector import ReloadSelector
from src.table_priorities import TablePriorities
from src.sqlite_mixin import SQLiteMixin
from datetime import datetime, timedelta

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'test_queue.db'

@pytest.fixture
def table_priorities():
    return TablePriorities('tests/data/tables.json')

@pytest.fixture
def reload_selector(db_path, table_priorities):
    return ReloadSelector(db_path, table_priorities)

def test_update_priorities(reload_selector, db_path):
    reload_selector.execute('''
        INSERT INTO QUEUE (table_name, insert_time, status, priority)
        VALUES ("database_1.table_1", "2023-10-10 10:00:00", "Q", 0)
    ''')
    reload_selector.commit()
    reload_selector.update_priorities()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT priority FROM QUEUE WHERE table_name = "database_1.table_1"')
    priority = cursor.fetchone()[0]
    assert priority > 0
    conn.close()
    
def test_calculate_score(reload_selector):
    assert reload_selector.calculate_score(70) == 0
    assert reload_selector.calculate_score(50) == 1
    assert reload_selector.calculate_score(40) == 2
    assert reload_selector.calculate_score(20) == 3
    assert reload_selector.calculate_score(12) == 4
    assert reload_selector.calculate_score(8) == 5
    assert reload_selector.calculate_score(4) == 6
    assert reload_selector.calculate_score(2) == 7
    
def test_run(reload_selector, db_path):
    reload_selector.execute('''
        INSERT INTO QUEUE (table_name, insert_time, status, priority)
        VALUES ("database_1.table_1", "2023-10-10 10:00:00", "Q", 0)
    ''')
    reload_selector.commit()
    reload_selector.run()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM QUEUE')
    result = cursor.fetchall()
    assert len(result) == 0
    conn.close()
    
