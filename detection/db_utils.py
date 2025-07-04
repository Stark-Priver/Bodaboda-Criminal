# detection/db_utils.py

import sqlite3
import numpy as np
import os
import pickle # Using pickle for numpy array serialization

# Assuming database_setup.py is in the parent directory
# and defines DATABASE_PATH or similar
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = "facial_recognition.db"
DATABASE_DIR = os.path.join(PARENT_DIR, "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)


def get_known_face_encodings():
    """
    Retrieves all known criminal names and their face encodings from the database.
    Returns:
        tuple: (list of known face encodings, list of known criminal names)
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
        cursor.execute("SELECT name, face_encoding FROM criminals")
        rows = cursor.fetchall()

        for row in rows:
            name = row[0]
            try:
                # Deserialize the face encoding (assuming it's stored as a pickled numpy array)
                encoding_blob = row[1]
                encoding = pickle.loads(encoding_blob)
                known_face_encodings.append(encoding)
                known_criminal_names.append(name)
            except pickle.UnpicklingError as e:
                print(f"Error unpickling encoding for {name}: {e}. Skipping this entry.")
            except Exception as e:
                print(f"An unexpected error occurred while processing encoding for {name}: {e}. Skipping.")

        print(f"Loaded {len(known_face_encodings)} known face encodings from the database.")

    except sqlite3.Error as e:
        print(f"Database error while fetching known faces: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

    return known_face_encodings, known_criminal_names


def save_alert(criminal_id, detected_face_photo_path, terminal_id="bodaboda_terminal_01"):
    """
    Saves an alert into the alerts table.
    Args:
        criminal_id (int): The ID of the matched criminal.
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
    Retrieves the ID of a criminal by their name.
    Args:
        name (str): The name of the criminal.
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
    # Example usage:
    # Make sure you have run database_setup.py first
    # And potentially added some criminals via a yet-to-be-created admin interface or manually

    # To test, you might need to manually insert a criminal with a pickled encoding.
    # For now, this will likely return empty lists or print an error if DB is empty/not found.
    print("Attempting to load known face encodings...")
    encodings, names = get_known_face_encodings()
    if names:
        print(f"Loaded names: {names}")
        # Example: try to get ID of the first loaded criminal
        first_criminal_name = names[0]
        criminal_id = get_criminal_id_by_name(first_criminal_name)
        if criminal_id:
            print(f"ID for {first_criminal_name}: {criminal_id}")
            # Example: try to save a dummy alert
            # dummy_photo_path = os.path.join(PARENT_DIR, "data", "detected_faces", "dummy_face.jpg")
            # os.makedirs(os.path.join(PARENT_DIR, "data", "detected_faces"), exist_ok=True)
            # with open(dummy_photo_path, "w") as f: f.write("dummy image data") # Create dummy file
            # save_alert(criminal_id, dummy_photo_path)
        else:
            print(f"Could not find ID for {first_criminal_name}")
    else:
        print("No known faces loaded. Database might be empty or inaccessible.")

    # Test saving an alert (requires a criminal with ID 1 to exist)
    # print("\nAttempting to save a test alert...")
    # test_photo_path = os.path.join(PARENT_DIR, "data", "detected_faces", "test_detection.jpg")
    # # Ensure directory exists
    # os.makedirs(os.path.dirname(test_photo_path), exist_ok=True)
    # # Create a dummy file for testing
    # with open(test_photo_path, 'w') as f: f.write("This is a test image.")
    # if get_criminal_id_by_name("Test Criminal"): # Assuming a "Test Criminal" exists with some ID
    #     cid = get_criminal_id_by_name("Test Criminal")
    #     save_alert(cid, test_photo_path)
    # else:
    #     print("Cannot save test alert: 'Test Criminal' not found or database issue.")
    #     print("Consider adding a criminal manually or through the dashboard first for full testing.")

    print("\nDB Utils Test Complete.")
