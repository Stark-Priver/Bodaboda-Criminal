import os
import sqlite3
import face_recognition
import numpy as np
import pickle # For serializing/deserializing numpy arrays (face encodings)
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename

# --- App Configuration ---
# Assuming the script is in 'dashboard/app.py'
# So, '..' goes to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_NAME = "facial_recognition.db"
DATABASE_PATH = os.path.join(PROJECT_ROOT, "data", DATABASE_NAME) # DB remains in data

# Configure UPLOAD_FOLDER_NAME to be a subdirectory within the main static folder
UPLOAD_FOLDER_NAME = "criminal_photos"
STATIC_FOLDER_PATH = os.path.join(PROJECT_ROOT, 'static')
UPLOAD_FOLDER_PATH = os.path.join(STATIC_FOLDER_PATH, UPLOAD_FOLDER_NAME) # e.g., static/criminal_photos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists within the static directory
os.makedirs(UPLOAD_FOLDER_PATH, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, 'templates'), static_folder=STATIC_FOLDER_PATH)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_for_development') # Change in production!
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_PATH # This is the absolute path for saving files
app.config['DATABASE'] = DATABASE_PATH


# --- Database Helper Functions ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row # Access columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(sql, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, args)
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

# --- Utility Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_face_encoding(image_path):
    """Loads an image, finds the face, and returns its encoding."""
    try:
        image = face_recognition.load_image_file(image_path)
        # Assuming one face per photo for criminals, take the first one found.
        # For better UX, one might want to handle cases with no faces or multiple faces.
        face_encodings = face_recognition.face_encodings(image)

        if face_encodings:
            return face_encodings[0] # Return the first encoding
        else:
            return None
    except Exception as e:
        print(f"Error generating face encoding for {image_path}: {e}")
        return None

# --- Utility Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_face_encoding(image_path):
    """Loads an image, finds the face, and returns its encoding."""
    try:
        image = face_recognition.load_image_file(image_path)
        # Assuming one face per photo for criminals, take the first one found.
        # For better UX, one might want to handle cases with no faces or multiple faces.
        face_encodings = face_recognition.face_encodings(image)

        if face_encodings:
            return face_encodings[0] # Return the first encoding
        else:
            return None
    except Exception as e:
        print(f"Error generating face encoding for {image_path}: {e}")
        return None

@app.context_processor
def utility_processor():
    # This makes 'in_app_url_rules' available in all templates
    # It contains a list of all registered URL rules in the application
    # Useful for conditionally rendering links if a route might not be registered yet
    return dict(in_app_url_rules=[rule.endpoint for rule in app.url_map.iter_rules()])

# --- Routes ---
@app.route('/')
def index():
    return redirect(url_for('list_criminals'))

@app.route('/criminals')
def list_criminals():
    criminals_data = query_db("SELECT id, name, description, photo_path FROM criminals ORDER BY name")
    return render_template('criminals/list.html', criminals=criminals_data)

@app.route('/criminals/add', methods=['GET', 'POST'])
def add_criminal():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        photo = request.files.get('photo')

        if not name:
            flash('Name is required.', 'danger')
            return redirect(request.url)
        if not photo or photo.filename == '':
            flash('Photo is required.', 'danger')
            return redirect(request.url)

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            # To avoid overwrites and ensure unique filenames, append a timestamp or UUID
            # For simplicity now, just using secure_filename. Consider unique name generation.
            # Check if file with same name already exists, if so, append a number or timestamp
            base, ext = os.path.splitext(filename)
            counter = 1
            unique_filename = filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                unique_filename = f"{base}_{counter}{ext}"
                counter += 1

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(filepath)

            # Generate face encoding
            face_encoding_array = generate_face_encoding(filepath)

            if face_encoding_array is None:
                flash('Could not detect a face in the uploaded image or an error occurred. Please try another photo.', 'danger')
                os.remove(filepath) # Clean up the saved photo if encoding fails
                return redirect(request.url)

            # Serialize numpy array for database storage
            serialized_encoding = pickle.dumps(face_encoding_array)

            try:
                # photo_path for DB should be relative to the static folder, e.g., "criminal_photos/image.jpg"
                db_photo_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename)
                execute_db("INSERT INTO criminals (name, description, photo_path, face_encoding) VALUES (?, ?, ?, ?)",
                           (name, description, db_photo_path, serialized_encoding))
                flash(f'Criminal "{name}" added successfully with face encoding!', 'success')
            except sqlite3.IntegrityError as e: # e.g. if photo_path was somehow not unique
                 flash(f'Error adding criminal: {e}. The photo path might already exist or another integrity constraint failed.', 'danger')
                 os.remove(filepath) # Clean up
                 return redirect(request.url)
            except Exception as e:
                flash(f'An unexpected error occurred: {e}', 'danger')
                os.remove(filepath) # Clean up
                return redirect(request.url)

            return redirect(url_for('list_criminals'))
        else:
            flash('Invalid file type. Allowed types are: png, jpg, jpeg, gif.', 'danger')
            return redirect(request.url)

    return render_template('criminals/add.html')


@app.route('/criminals/edit/<int:criminal_id>', methods=['GET', 'POST'])
def edit_criminal(criminal_id):
    criminal = query_db("SELECT * FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        new_photo = request.files.get('photo')

        if not name:
            flash('Name is required.', 'danger')
            return render_template('criminals/edit.html', criminal=criminal)

        current_photo_path_db = criminal['photo_path'] # This is relative to static dir, e.g., "criminal_photos/img.jpg"
        # Absolute path for file operations (e.g. deletion, checking existence)
        current_photo_path_absolute = os.path.join(STATIC_FOLDER_PATH, current_photo_path_db) if current_photo_path_db else None

        new_db_photo_path = current_photo_path_db # By default, keep old photo path
        new_serialized_encoding = criminal['face_encoding'] # Keep old encoding if photo not changed

        if new_photo and new_photo.filename != '':
            if allowed_file(new_photo.filename):
                # Delete old photo if it exists and a new one is being uploaded
                if current_photo_path_absolute and os.path.exists(current_photo_path_absolute):
                    try:
                        os.remove(current_photo_path_absolute)
                        flash("Old photo removed.", "info")
                    except OSError as e:
                        flash(f"Error deleting old photo: {e}", "warning")

                filename = secure_filename(new_photo.filename)
                base, ext = os.path.splitext(filename)
                counter = 1
                unique_filename = filename
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                    unique_filename = f"{base}_{counter}{ext}"
                    counter += 1

                new_photo_filepath_absolute = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename) # app.config['UPLOAD_FOLDER'] is static/criminal_photos
                new_photo.save(new_photo_filepath_absolute)
                new_db_photo_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename) # Relative path for DB (e.g. criminal_photos/new.jpg)

                # Generate new face encoding
                face_encoding_array = generate_face_encoding(new_photo_filepath_absolute)
                if face_encoding_array is None:
                    flash('Could not detect a face in the new uploaded image or an error occurred. Criminal not updated with new photo.', 'danger')
                    # Don't remove the new photo yet, user might want to retry with same info
                    # Or, decide to remove it: os.remove(new_photo_filepath_absolute)
                    return render_template('criminals/edit.html', criminal=criminal) # Show form again

                new_serialized_encoding = pickle.dumps(face_encoding_array)
            else:
                flash('Invalid file type for new photo. Allowed types are: png, jpg, jpeg, gif.', 'danger')
                return render_template('criminals/edit.html', criminal=criminal) # Show form again

        try:
            execute_db("UPDATE criminals SET name = ?, description = ?, photo_path = ?, face_encoding = ? WHERE id = ?",
                       (name, description, new_db_photo_path, new_serialized_encoding, criminal_id))
            flash(f'Criminal "{name}" updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating criminal: {e}', 'danger')
            # If a new photo was saved but the DB update failed, clean up the newly saved photo
            if new_photo and new_photo.filename != '' and 'new_photo_filepath_absolute' in locals() and os.path.exists(new_photo_filepath_absolute):
                # Check if this new photo path is different from the original one (if any)
                # to avoid deleting an existing photo if the new upload failed but was named the same (unlikely with unique names)
                if new_db_photo_path != current_photo_path_db:
                    try:
                        os.remove(new_photo_filepath_absolute)
                        flash('Cleaned up newly uploaded photo due to database error.', 'info')
                    except OSError as e_del:
                        flash(f'Could not clean up new photo: {e_del}', 'warning')
            return render_template('criminals/edit.html', criminal=criminal)


        return redirect(url_for('list_criminals'))

    return render_template('criminals/edit.html', criminal=criminal)


@app.route('/criminals/delete/<int:criminal_id>', methods=['POST']) # Use POST for deletion
def delete_criminal(criminal_id):
    criminal = query_db("SELECT id, name, photo_path FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    try:
        # First, delete associated alerts to maintain referential integrity if ON DELETE CASCADE is not set (it's not by default in our setup)
        execute_db("DELETE FROM alerts WHERE criminal_id = ?", (criminal_id,))

        # Then, delete the criminal record
        execute_db("DELETE FROM criminals WHERE id = ?", (criminal_id,))

        # Delete the photo file
        # criminal['photo_path'] is relative to static folder, e.g., "criminal_photos/img.jpg"
        if criminal['photo_path']:
            photo_to_delete_absolute = os.path.join(STATIC_FOLDER_PATH, criminal['photo_path'])
            if os.path.exists(photo_to_delete_absolute):
                try:
                    os.remove(photo_to_delete_absolute)
                except OSError as e:
                    flash(f"Error deleting photo file {criminal['photo_path']}: {e}. Record deleted from DB.", "warning")
            else:
                flash(f"Photo file {criminal['photo_path']} not found in static directory. Record deleted from DB.", "warning")

        flash(f'Criminal "{criminal["name"]}" and associated alerts deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting criminal: {e}', 'danger')

    return redirect(url_for('list_criminals'))


# --- Alert Management Routes ---
DETECTED_FACES_DIR_NAME = "detected_faces" # as defined in detector.py, relative to data/
DATA_DIR_PATH = os.path.join(PROJECT_ROOT, "data") # data directory

@app.route('/data/detected_faces/<filename>')
def serve_detected_face_image(filename):
    # Serves images from the data/detected_faces directory
    # This is necessary because this directory is outside the 'static' folder.
    # Security consideration: Ensure 'filename' is sanitized or only allows expected patterns
    # For now, Werkzeug's secure_filename is not directly applicable here as we're matching,
    # but be mindful if constructing paths from user input. Here, it's from DB.
    return send_from_directory(os.path.join(DATA_DIR_PATH, DETECTED_FACES_DIR_NAME), filename)

@app.route('/alerts')
def view_alerts():
    # Query to fetch alerts, joining with criminals table to get the criminal's name
    # Orders by timestamp descending to show newest alerts first
    alerts_data = query_db("""
        SELECT
            a.id,
            a.timestamp,
            a.detected_face_photo_path,
            a.terminal_id,
            c.name as criminal_name,
            c.photo_path as criminal_photo_path
        FROM alerts a
        JOIN criminals c ON a.criminal_id = c.id
        ORDER BY a.timestamp DESC
    """)
    return render_template('alerts/view.html', alerts=alerts_data)


# --- Main execution ---
if __name__ == '__main__':
    # Ensure the database exists and tables are created if not already
    # This is more for robust local development; in production, you'd manage DB setup separately.
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please run `python database_setup.py` from the project root.")
        # You could try to run it:
        # import subprocess
        # try:
        #     subprocess.run(['python', os.path.join(PROJECT_ROOT, 'database_setup.py')], check=True)
        #     print("Database setup script executed.")
        # except Exception as e:
        #     print(f"Failed to run database_setup.py: {e}")
        #     exit(1) # Exit if DB setup fails

    app.run(debug=True, host='0.0.0.0', port=5001) # Use a different port if 5000 is common
    # For deployment, use a production WSGI server like Gunicorn or Waitress.
    # Example: gunicorn -w 4 dashboard.app:app
    # Or for Windows: waitress-serve --listen=*:5001 dashboard.app:app
