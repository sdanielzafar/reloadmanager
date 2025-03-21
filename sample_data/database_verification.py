import sqlite3
import os

def verify_database(db_path):
    # Check if the database file exists
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        return

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query the QUEUE table
    print("QUEUE Table:")
    cursor.execute('SELECT * FROM QUEUE')
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("No data found in QUEUE table.")

    # Query the QUEUE_HISTORY table
    print("\nQUEUE_HISTORY Table:")
    cursor.execute('SELECT * FROM QUEUE_HISTORY')
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("No data found in QUEUE_HISTORY table.")

    # Close the connection
    conn.close()

if __name__ == '__main__':
    # Ensure the sample_data directory exists
    if not os.path.exists('sample_data'):
        os.makedirs('sample_data')

    # Path to the database file
    db_path = 'sample_data/sample_queue.db'

    # Verify the database
    verify_database(db_path)