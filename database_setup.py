import sqlite3
import os

DATABASE_NAME = "facial_recognition.db"
DATABASE_DIR = "data"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)

def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        os.makedirs(DATABASE_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        # Enable foreign key constraint enforcement
        conn.execute("PRAGMA foreign_keys = ON")
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

        # Criminals table (Modified: stores only main info)
        # Names should ideally be unique if they are used as identifiers in some places.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criminals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );
        """)
        print("Table 'criminals' created/updated successfully.")

        # Criminal Images table (New: stores individual images and their encodings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS criminal_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criminal_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                face_encoding BLOB NOT NULL,
                FOREIGN KEY (criminal_id) REFERENCES criminals (id) ON DELETE CASCADE
            );
        """)
        print("Table 'criminal_images' created successfully or already exists.")
        # Index for faster lookup of images by criminal_id
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_criminal_images_criminal_id ON criminal_images (criminal_id);")


        # Alerts table (Unchanged schema, but ensure FK constraint is noted)
        # The criminal_id here refers to the id in the 'criminals' table.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                criminal_id INTEGER NOT NULL,
                detected_face_photo_path TEXT NOT NULL,
                terminal_id TEXT DEFAULT 'bodaboda_terminal_01',
                FOREIGN KEY (criminal_id) REFERENCES criminals (id) ON DELETE CASCADE
            );
        """) # Added ON DELETE CASCADE for alerts too
        print("Table 'alerts' created/updated successfully.")

        # Users table (New: for dashboard authentication)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        print("Table 'users' created successfully or already exists.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating/updating tables: {e}")
    finally:
        if conn:
            conn.close()
            print("SQLite connection closed after table creation.")

def drop_all_tables_for_reset(conn):
    """Drops all known tables for a clean reset. USE WITH CAUTION."""
    if conn is None:
        print("Cannot drop tables: database connection is not established.")
        return

    cursor = conn.cursor()
    tables = ["criminal_images", "alerts", "criminals", "users"] # Order matters for FK constraints if not using CASCADE for drops

    # Temporarily disable foreign key constraints to drop tables easily
    cursor.execute("PRAGMA foreign_keys = OFF")
    conn.commit()

    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Table '{table}' dropped successfully.")
        except sqlite3.Error as e:
            print(f"Error dropping table {table}: {e}")

    # Re-enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print("All known tables dropped for reset.")


if __name__ == '__main__':
    db_conn = create_connection()
    if db_conn:
        # For development, you might want to reset the DB structure easily.
        # Uncomment the next line to drop tables before creating them.
        # print("Attempting to drop all tables for a fresh start...")
        # drop_all_tables_for_reset(db_conn) # Call this before create_tables if you want a clean slate

        create_tables(db_conn) # This will re-create them
    else:
        print("Failed to establish database connection. Tables not created.")

    # Example of how to verify schema (manual check)
    # db_verify_conn = create_connection()
    # if db_verify_conn:
    #     print("\nVerifying schema...")
    #     cursor = db_verify_conn.cursor()
    #     cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    #     tables = cursor.fetchall()
    #     print("Tables found:", tables)
    #     for table_name_tuple in tables:
    #         table_name = table_name_tuple[0]
    #         print(f"\nSchema for {table_name}:")
    #         cursor.execute(f"PRAGMA table_info({table_name});")
    #         columns = cursor.fetchall()
    #         for col in columns:
    #             print(col)
    #     db_verify_conn.close()
