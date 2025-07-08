import sqlite3
import os
import config # Import the new config file

# Use database name from config, construct path
DATABASE_PATH = os.path.join("data", config.DATABASE_NAME)


def create_connection():
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        print(f"DATABASE_SETUP: Successfully connected to SQLite database at {DATABASE_PATH}")
    except sqlite3.Error as e:
        print(f"DATABASE_SETUP: Error connecting to SQLite database: {e}")
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
                photo_path TEXT UNIQUE, /* Relative to static folder */
                face_encoding BLOB NOT NULL
            );
        """)
        print("DATABASE_SETUP: Table 'criminals' created successfully or already exists.")

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                criminal_id INTEGER NOT NULL,
                detected_face_photo_path TEXT NOT NULL, /* Relative to data/detected_faces */
                terminal_id TEXT DEFAULT '{config.DEFAULT_ALERT_TERMINAL_ID}',
                FOREIGN KEY (criminal_id) REFERENCES criminals (id) ON DELETE CASCADE
            );
        """.format(config=config)) # Use .format to insert config value into SQL string
        print("DATABASE_SETUP: Table 'alerts' created successfully or already exists.")

        # Admin Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        """)
        print("DATABASE_SETUP: Table 'admin_users' created successfully or already exists.")

        conn.commit()
    except sqlite3.Error as e:
        print(f"DATABASE_SETUP: Error creating tables: {e}")
    # Connection is closed by the calling function if it owns it

def create_default_admin(conn):
    """Creates a default admin user using credentials from config.py if one doesn't exist."""
    if conn is None:
        print("DATABASE_SETUP: Cannot create admin: database connection is not established.")
        return

    try:
        from werkzeug.security import generate_password_hash

        admin_username = config.DEFAULT_ADMIN_USERNAME
        admin_password = config.DEFAULT_ADMIN_PASSWORD

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM admin_users WHERE username = ?", (admin_username,))
        if cursor.fetchone() is None:
            hashed_password = generate_password_hash(admin_password)
            cursor.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", (admin_username, hashed_password))
            conn.commit()
            print(f"DATABASE_SETUP: Default admin user '{admin_username}' created with password '{admin_password}'. PLEASE CHANGE THIS PASSWORD.")
        else:
            print(f"DATABASE_SETUP: Admin user '{admin_username}' already exists.")
    except ImportError:
        print("DATABASE_SETUP: Werkzeug library not found (pip install Werkzeug). Cannot hash password for default admin.")
    except sqlite3.Error as e:
        print(f"DATABASE_SETUP: Error creating default admin user: {e}")


if __name__ == '__main__':
    db_conn = create_connection()
    if db_conn:
        try:
            create_tables(db_conn)
            create_default_admin(db_conn) # Create default admin user
        finally:
            db_conn.close()
            print("DATABASE_SETUP: SQLite connection closed.")
    else:
        print("DATABASE_SETUP: Failed to establish database connection. Tables not created.")
