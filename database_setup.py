import sqlite3
import os

DATABASE_NAME = "facial_recognition.db"
DATABASE_DIR = "data"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        # Ensure the data directory exists
        os.makedirs(DATABASE_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        print(f"Successfully connected to SQLite database at {DATABASE_PATH}")
    except sqlite3.Error as e:
        print(f"Error connecting to SQLite database: {e}")
    return conn

def create_tables(conn):
    """Create tables in the SQLite database."""
    if conn is None:
        print("Cannot create tables: database connection is not established.")
        return

    try:
        cursor = conn.cursor()

        # Criminals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criminals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                photo_path TEXT UNIQUE,
                face_encoding BLOB NOT NULL
            );
        """)
        print("Table 'criminals' created successfully or already exists.")

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                criminal_id INTEGER NOT NULL,
                detected_face_photo_path TEXT NOT NULL,
                terminal_id TEXT DEFAULT 'bodaboda_terminal_01',
                FOREIGN KEY (criminal_id) REFERENCES criminals (id)
            );
        """)
        print("Table 'alerts' created successfully or already exists.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")
    finally:
        if conn:
            conn.close()
            print("SQLite connection closed.")

if __name__ == '__main__':
    db_conn = create_connection()
    if db_conn:
        create_tables(db_conn)
    else:
        print("Failed to establish database connection. Tables not created.")
