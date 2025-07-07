# detection/db_utils.py

import sqlite3
import numpy as np
import os
import pickle

# Database path (assuming this script is in detection/, and data/ is in parent dir)
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = "facial_recognition.db"
DATABASE_DIR = os.path.join(PARENT_DIR, "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)


def get_known_face_encodings():
    """
    Retrieves all known face encodings from the 'criminal_images' table
    and their associated criminal names from the 'criminals' table.
    Returns:
        tuple: (list of known face encodings, list of corresponding criminal names)
               A criminal's name will appear multiple times if they have multiple images/encodings.
    """
    known_face_encodings = []
    known_criminal_names = []

    if not os.path.exists(DATABASE_PATH):
        print(f"Database file not found at {DATABASE_PATH}. Please run database_setup.py.")
        return known_face_encodings, known_criminal_names

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        # Query joins criminal_images with criminals to get the name for each encoding
        cursor.execute("""
            SELECT c.name, ci.face_encoding
            FROM criminal_images ci
            JOIN criminals c ON ci.criminal_id = c.id
        """)
        rows = cursor.fetchall()

        for row in rows:
            name = row[0]
            encoding_blob = row[1]
            try:
                encoding = pickle.loads(encoding_blob)
                known_face_encodings.append(encoding)
                known_criminal_names.append(name)
            except pickle.UnpicklingError as e:
                print(f"Error unpickling encoding for an image of {name}: {e}. Skipping this entry.")
            except Exception as e:
                print(f"An unexpected error occurred while processing an encoding for {name}: {e}. Skipping.")

        count = len(known_face_encodings)
        unique_criminals_count = len(set(known_criminal_names))
        print(f"Loaded {count} known face encodings from {unique_criminals_count} unique criminals in the database.")

    except sqlite3.Error as e:
        print(f"Database error while fetching known faces: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in get_known_face_encodings: {e}")
    finally:
        if conn:
            conn.close()

    return known_face_encodings, known_criminal_names


def save_alert(criminal_id, detected_face_photo_path, terminal_id="bodaboda_terminal_01"):
    """
    Saves an alert into the alerts table.
    Args:
        criminal_id (int): The ID of the matched criminal (from the 'criminals' table).
        detected_face_photo_path (str): Path to the image of the detected face.
        terminal_id (str): The ID of the terminal where the detection occurred.
    Returns:
        int: The ID of the newly inserted alert, or None if failed.
    """
    if not os.path.exists(DATABASE_PATH):
        print(f"Database file not found at {DATABASE_PATH}. Cannot save alert.")
        return None

    conn = None
    alert_id = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        # Ensure foreign key pragma is enabled for this connection if not globally (it is in create_connection)
        # conn.execute("PRAGMA foreign_keys = ON")
        cursor.execute("""
            INSERT INTO alerts (criminal_id, detected_face_photo_path, terminal_id)
            VALUES (?, ?, ?)
        """, (criminal_id, detected_face_photo_path, terminal_id))
        conn.commit()
        alert_id = cursor.lastrowid
        print(f"Alert saved successfully. Alert ID: {alert_id}, Criminal ID: {criminal_id}")
    except sqlite3.Error as e:
        print(f"Database error while saving alert: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving alert: {e}")
    finally:
        if conn:
            conn.close()
    return alert_id

def get_criminal_id_by_name(name):
    """
    Retrieves the ID of a criminal by their name from the 'criminals' table.
    Args:
        name (str): The name of the criminal. (Assumes names are unique in 'criminals' table)
    Returns:
        int: The ID of the criminal, or None if not found.
    """
    if not os.path.exists(DATABASE_PATH):
        print(f"Database file not found at {DATABASE_PATH}.")
        return None

    conn = None
    criminal_id = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM criminals WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            criminal_id = row[0]
    except sqlite3.Error as e:
        print(f"Database error while fetching criminal ID by name: {e}")
    finally:
        if conn:
            conn.close()
    return criminal_id


if __name__ == '__main__':
    # Example usage (for testing this module directly):
    # Ensure database_setup.py has been run with the new schema.
    # You would need to manually add some data or use the dashboard (once updated) to test fully.

    print("Attempting to load known face encodings...")
    encodings, names = get_known_face_encodings()
    if names:
        print(f"Loaded {len(encodings)} encodings for names: {names}")

        # Example: try to get ID of the first loaded criminal name
        if names:
            first_criminal_name = names[0]
            criminal_id = get_criminal_id_by_name(first_criminal_name)
            if criminal_id:
                print(f"ID for '{first_criminal_name}': {criminal_id}")
                # To test save_alert, you'd need a valid criminal_id and a dummy photo path
                # dummy_photo_path = os.path.join(PARENT_DIR, "data", "detected_faces", "dummy_face.jpg")
                # os.makedirs(os.path.join(PARENT_DIR, "data", "detected_faces"), exist_ok=True)
                # with open(dummy_photo_path, "w") as f: f.write("dummy image data") # Create dummy file
                # saved_alert_id = save_alert(criminal_id, dummy_photo_path)
                # print(f"Dummy alert saved with ID: {saved_alert_id}" if saved_alert_id else "Failed to save dummy alert.")
            else:
                print(f"Could not find ID for '{first_criminal_name}'.")
    else:
        print("No known faces loaded. Database might be empty or schema might not match expectations.")

    print("\nDB Utils Test Complete (manual verification needed for full test).")
