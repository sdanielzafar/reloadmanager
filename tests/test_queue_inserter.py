import pytest
import sqlite3

from src.reloadmanager.queue_inserter import QueueInserter
from src import TablePriorities

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'test_queue.db'

@pytest.fixture
def table_priorities():
    return TablePriorities('tests/data/tables.json')

@pytest.fixture
def queue_inserter(db_path, table_priorities):
    return QueueInserter(db_path, table_priorities)


def test_insert_table(queue_inserter, db_path):
    queue_inserter.insert_table('database_1.table_1')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM QUEUE WHERE table_name = "database_1.table_1"')
    result = cursor.fetchone()
    assert result is not None
    conn.close()

def test_query_teradata(queue_inserter):
    tables = queue_inserter.query_teradata()
    assert isinstance(tables, list) and len(tables) > 0

def test_run(queue_inserter, db_path):
    queue_inserter.run()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM QUEUE')
    result = cursor.fetchall()
    assert len(result) > 0
    conn.close()