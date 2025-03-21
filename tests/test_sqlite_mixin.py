import pytest
from src.sqlite_mixin import SQLiteMixin
import sqlite3

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / 'test_db.db'

@pytest.fixture
def sqlite_mixin(db_path):
    return SQLiteMixin(db_path)

def test_execute(sqlite_mixin):
    sqlite_mixin.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    sqlite_mixin.commit()
    conn = sqlite3.connect(sqlite_mixin.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
    assert cursor.fetchone() is not None
    conn.close()

def test_commit(sqlite_mixin):
    sqlite_mixin.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    sqlite_mixin.commit()
    conn = sqlite3.connect(sqlite_mixin.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
    assert cursor.fetchone() is not None
    conn.close()

def test_close(sqlite_mixin):
    sqlite_mixin.close()
    assert sqlite_mixin.conn.closed

def test_fetchall(sqlite_mixin):
    sqlite_mixin.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    sqlite_mixin.execute("INSERT INTO test (value) VALUES ('test_value')")
    sqlite_mixin.commit()
    result = sqlite_mixin.fetchall()
    assert len(result) == 1

def test_fetchone(sqlite_mixin):
    sqlite_mixin.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    sqlite_mixin.execute("INSERT INTO test (value) VALUES ('test_value')")
    sqlite_mixin.commit()
    result = sqlite_mixin.fetchone()
    assert result[1] == 'test_value'