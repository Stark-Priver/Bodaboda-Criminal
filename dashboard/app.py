import os
import sqlite3
import face_recognition
import numpy as np
import pickle # For serializing/deserializing numpy arrays (face encodings)
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

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

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Name of the login route
login_manager.login_message_category = 'info' # Flash message category

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    db_user = query_db("SELECT id, username FROM users WHERE id = ?", (user_id,), one=True)
    if db_user:
        return User(id=db_user['id'], username=db_user['username'])
    return None

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

# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('list_criminals'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))

        existing_user = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        try:
            execute_db("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration failed: {e}', 'danger')
            return redirect(url_for('register'))
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('list_criminals'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('login'))

        user_data = query_db("SELECT id, username, password_hash FROM users WHERE username = ?", (username,), one=True)

        if user_data and check_password_hash(user_data['password_hash'], password):
            user_obj = User(id=user_data['id'], username=user_data['username'])
            login_user(user_obj) # Add remember=True if you want "remember me" functionality
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('list_criminals'))
        else:
            flash('Login unsuccessful. Please check username and password.', 'danger')
            return redirect(url_for('login'))
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Main Application Routes (Protected) ---
@app.route('/')
@login_required
def index():
    return redirect(url_for('list_criminals'))

@app.route('/criminals')
@login_required
def list_criminals():
    # Fetch criminals and their first associated image path for display
    # Using a subquery to get the path of one image per criminal (e.g., the one with the min ID for that criminal)
    # SQLite's rowid or id can be used if criminal_images.id is an auto-incrementing PK.
    # Or, more simply, group by criminal and pick one image path (e.g. MIN(ci.image_path))
    # For simplicity, let's use a common table expression (CTE) or a subquery if simpler.

    # This query gets the criminal info and the path of one of their images.
    # It uses a subquery in the SELECT list, which can be inefficient on large datasets but is fine for moderate numbers.
    # A LEFT JOIN with a GROUP BY and MIN/MAX on image_id would be more robust.
    criminals_data = query_db("""
        SELECT
            c.id,
            c.name,
            c.description,
            (SELECT ci.image_path
             FROM criminal_images ci
             WHERE ci.criminal_id = c.id
             ORDER BY ci.id ASC
             LIMIT 1) as display_image_path
        FROM criminals c
        ORDER BY c.name
    """)
    return render_template('criminals/list.html', criminals=criminals_data)

@app.route('/criminals/add', methods=['GET', 'POST'])
@login_required
def add_criminal():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        photos = request.files.getlist('photos') # Use getlist for multiple files

        if not name:
            flash('Name is required.', 'danger')
            return redirect(request.url)

        if not photos or all(p.filename == '' for p in photos):
            flash('At least one photo is required.', 'danger')
            return redirect(request.url)

        processed_images_info = [] # To store info about successfully processed images for this criminal
        any_errors = False

        # First, try to insert the criminal basic info. Name must be unique.
        criminal_id = None
        try:
            criminal_id = execute_db("INSERT INTO criminals (name, description) VALUES (?, ?)",
                                     (name, description))
            if not criminal_id: # Should not happen if execute_db is correct and no exception
                raise sqlite3.Error("Failed to get criminal ID after insert.")
        except sqlite3.IntegrityError: # Handles UNIQUE constraint on name
            flash(f'Criminal name "{name}" already exists. Please choose a different name.', 'danger')
            return redirect(request.url)
        except Exception as e:
            flash(f'Error creating criminal record: {e}', 'danger')
            return redirect(request.url)

        # Now process uploaded photos
        for photo_file_storage in photos:
            if photo_file_storage and allowed_file(photo_file_storage.filename):
                original_filename = secure_filename(photo_file_storage.filename)
                base, ext = os.path.splitext(original_filename)
                counter = 1
                # Ensure unique filename within the criminal_photos folder
                unique_filename = original_filename
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                    unique_filename = f"{base}_{counter}{ext}"
                    counter += 1

                filepath_absolute = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                photo_file_storage.save(filepath_absolute)

                face_encoding_array = generate_face_encoding(filepath_absolute)

                if face_encoding_array is None:
                    flash(f'Could not detect a face in "{original_filename}" or an error occurred. This image was not saved.', 'warning')
                    os.remove(filepath_absolute) # Clean up
                    any_errors = True
                    continue # Skip this image

                serialized_encoding = pickle.dumps(face_encoding_array)
                db_image_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename) # Relative to static/

                try:
                    execute_db("INSERT INTO criminal_images (criminal_id, image_path, face_encoding) VALUES (?, ?, ?)",
                               (criminal_id, db_image_path, serialized_encoding))
                    processed_images_info.append({'path': db_image_path, 'original_name': original_filename})
                except Exception as e:
                    flash(f'Error saving image "{original_filename}" to database: {e}', 'danger')
                    os.remove(filepath_absolute) # Clean up
                    any_errors = True
            elif photo_file_storage.filename != '': # If a file was selected but not allowed
                flash(f'Invalid file type for "{photo_file_storage.filename}". Allowed types are: png, jpg, jpeg, gif.', 'warning')
                any_errors = True

        if not processed_images_info:
            # No images were successfully processed and saved for this criminal
            # Rollback: delete the criminal record if no images were associated
            if criminal_id:
                execute_db("DELETE FROM criminals WHERE id = ?", (criminal_id,))
            flash('No images were successfully processed. Criminal record not created or rolled back. Please ensure images contain clear faces and are of allowed types.', 'danger')
            return redirect(request.url)

        flash(f'Criminal "{name}" added with {len(processed_images_info)} image(s).', 'success' if not any_errors else 'warning')
        return redirect(url_for('list_criminals'))

    return render_template('criminals/add.html')


@app.route('/criminals/edit/<int:criminal_id>', methods=['GET', 'POST'])
@login_required
def edit_criminal(criminal_id):
    # Fetch basic criminal info (name, description)
    criminal_main_info = query_db("SELECT id, name, description FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal_main_info:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    if request.method == 'GET':
        # Fetch all images associated with this criminal for display
        criminal_images_data = query_db("SELECT id, image_path FROM criminal_images WHERE criminal_id = ? ORDER BY id ASC", (criminal_id,))
        return render_template('criminals/edit.html', criminal=criminal_main_info, images=criminal_images_data)

    # --- POST request handling for editing criminal ---
    if request.method == 'POST':
        action = request.form.get('action')

        # --- Action: Update basic details (name, description) ---
        if action == 'update_details':
            new_name = request.form.get('name', '').strip()
            new_description = request.form.get('description', '').strip()

            if not new_name:
                flash('Name cannot be empty.', 'danger')
            elif new_name != criminal_main_info['name']: # Check uniqueness only if name changed
                existing_criminal = query_db("SELECT id FROM criminals WHERE name = ? AND id != ?", (new_name, criminal_id), one=True)
                if existing_criminal:
                    flash(f'Another criminal with the name "{new_name}" already exists.', 'danger')
                else:
                    try:
                        execute_db("UPDATE criminals SET name = ?, description = ? WHERE id = ?",
                                   (new_name, new_description, criminal_id))
                        flash('Criminal details updated successfully.', 'success')
                        # Update criminal_main_info for the current request context (though redirect happens next)
                        # criminal_main_info = query_db("SELECT id, name, description FROM criminals WHERE id = ?", (criminal_id,), one=True)
                    except Exception as e:
                        flash(f'Error updating criminal details: {e}', 'danger')
            else: # Name didn't change, just update description
                 try:
                    execute_db("UPDATE criminals SET description = ? WHERE id = ?",
                               (new_description, criminal_id))
                    flash('Criminal description updated successfully.', 'success')
                    # criminal_main_info = query_db("SELECT id, name, description FROM criminals WHERE id = ?", (criminal_id,), one=True)
                 except Exception as e:
                    flash(f'Error updating criminal description: {e}', 'danger')
            return redirect(url_for('edit_criminal', criminal_id=criminal_id))

        # --- Action: Add new images ---
        elif action == 'add_images':
            new_photos = request.files.getlist('new_photos_input') # Ensure input name matches template
            any_upload_errors = False
            newly_added_images_count = 0

            if not new_photos or all(p.filename == '' for p in new_photos):
                flash('No files selected for upload.', 'warning')
                return redirect(url_for('edit_criminal', criminal_id=criminal_id))

            for photo_file_storage in new_photos:
                if photo_file_storage and allowed_file(photo_file_storage.filename):
                    original_filename = secure_filename(photo_file_storage.filename)
                    base, ext = os.path.splitext(original_filename)
                    counter = 1
                    unique_filename = original_filename
                    # Ensure unique filename within the criminal_photos folder
                    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                        unique_filename = f"{base}_{counter}{ext}"
                        counter += 1

                    filepath_absolute = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    photo_file_storage.save(filepath_absolute)

                    face_encoding_array = generate_face_encoding(filepath_absolute)
                    if face_encoding_array is None:
                        flash(f'No face detected in new image "{original_filename}". Not saved.', 'warning')
                        try:
                            if os.path.exists(filepath_absolute): os.remove(filepath_absolute)
                        except Exception as e_rem: print(f"Error removing temp file {filepath_absolute}: {e_rem}")
                        any_upload_errors = True
                        continue

                    serialized_encoding = pickle.dumps(face_encoding_array)
                    db_image_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename) # Relative to static/
                    try:
                        execute_db("INSERT INTO criminal_images (criminal_id, image_path, face_encoding) VALUES (?, ?, ?)",
                                   (criminal_id, db_image_path, serialized_encoding))
                        newly_added_images_count += 1
                    except Exception as e:
                        flash(f'Error saving new image "{original_filename}" to database: {e}', 'danger')
                        try:
                            if os.path.exists(filepath_absolute): os.remove(filepath_absolute)
                        except Exception as e_rem: print(f"Error removing temp file {filepath_absolute}: {e_rem}")
                        any_upload_errors = True
                elif photo_file_storage.filename != '': # File selected but not allowed type
                     flash(f'Invalid file type for new image "{photo_file_storage.filename}". Not saved.', 'warning')
                     any_upload_errors = True

            if newly_added_images_count > 0:
                flash(f'{newly_added_images_count} new image(s) added successfully.', 'success')

            if any_upload_errors and newly_added_images_count == 0 : # Only show this if no images were good
                 flash('No new images were successfully processed and saved.', 'danger')
            elif any_upload_errors: # Some errors, but some successes
                flash('Some new images could not be processed or saved. See other messages.', 'warning')

            if not any_upload_errors and newly_added_images_count == 0 and (new_photos and not all(p.filename == '' for p in new_photos)):
                # This case means files were selected, but none were valid or had faces, and no specific errors were caught for type or face.
                # This might indicate all selected files were empty filenames after secure_filename or other edge cases.
                flash('No valid images were processed from the selection.', 'warning')


            return redirect(url_for('edit_criminal', criminal_id=criminal_id))

        # --- Action: Delete a specific image ---
        elif action == 'delete_image':
            image_id_to_delete = request.form.get('image_id')
            if not image_id_to_delete:
                flash('Image ID not provided for deletion.', 'danger')
            else:
                image_to_delete = query_db("SELECT image_path FROM criminal_images WHERE id = ? AND criminal_id = ?",
                                           (image_id_to_delete, criminal_id), one=True)
                if image_to_delete:
                    # Check if this is the last image for the criminal
                    image_count_for_criminal = query_db("SELECT COUNT(*) as count FROM criminal_images WHERE criminal_id = ?", (criminal_id,), one=True)
                    if image_count_for_criminal and image_count_for_criminal['count'] <= 1:
                        flash('Cannot delete the last image of a criminal. Add another image first, or delete the entire criminal profile.', 'warning')
                    else:
                        # Delete file from filesystem
                        image_file_path_absolute = os.path.join(STATIC_FOLDER_PATH, image_to_delete['image_path'])
                        try:
                            if os.path.exists(image_file_path_absolute):
                                os.remove(image_file_path_absolute)
                        except Exception as e:
                            flash(f"Error deleting image file {image_to_delete['image_path']}: {e}", "warning")

                        # Delete record from database
                        try:
                            execute_db("DELETE FROM criminal_images WHERE id = ?", (image_id_to_delete,))
                            flash('Image deleted successfully.', 'success')
                        except Exception as e:
                            flash(f'Error deleting image record from database: {e}', 'danger')
                else:
                    flash('Image not found or does not belong to this criminal.', 'danger')
            return redirect(url_for('edit_criminal', criminal_id=criminal_id))

        else: # Unknown action
            flash('Invalid action specified.', 'danger')
            return redirect(url_for('edit_criminal', criminal_id=criminal_id))

    # Fallback for GET if not explicitly handled or after POST actions (should not be reached if POST actions redirect)
    # This is mainly to satisfy linters or structure, actual GET is handled at the top.
    criminal_images_data = query_db("SELECT id, image_path FROM criminal_images WHERE criminal_id = ? ORDER BY id ASC", (criminal_id,))
    return render_template('criminals/edit.html', criminal=criminal_main_info, images=criminal_images_data)


@app.route('/criminals/delete/<int:criminal_id>', methods=['POST']) # Use POST for deletion
@login_required
def delete_criminal(criminal_id):
    # This route will also need updating to delete all associated images from criminal_images and their files.
    # The ON DELETE CASCADE will handle DB records in criminal_images and alerts.
    # We need to manually delete files.

    # Get all image paths for this criminal before deleting the criminal record
    images_to_delete = query_db("SELECT image_path FROM criminal_images WHERE criminal_id = ?", (criminal_id,))

    criminal_info = query_db("SELECT name FROM criminals WHERE id = ?", (criminal_id,), one=True) # Fetched for name in flash message
    if not criminal_info: # Check if criminal exists before proceeding
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    # Get all image paths for this criminal BEFORE deleting the criminal record from DB
    images_to_delete_paths = query_db("SELECT image_path FROM criminal_images WHERE criminal_id = ?", (criminal_id,))

    try:
        # Delete the criminal record from 'criminals' table.
        # ON DELETE CASCADE will handle deleting related records in 'criminal_images' and 'alerts'.
        execute_db("DELETE FROM criminals WHERE id = ?", (criminal_id,))

        # Now, delete the actual image files from the filesystem
        for img_record in images_to_delete_paths:
            image_file_to_delete_abs = os.path.join(STATIC_FOLDER_PATH, img_record['image_path'])
            if os.path.exists(image_file_to_delete_abs):
                try:
                    os.remove(image_file_to_delete_abs)
                except OSError as e:
                    flash(f"Error deleting image file {img_record['image_path']}: {e}", "warning")
            # else: # Optionally log if a file listed in DB wasn't found, though not critical
            #     flash(f"Image file {img_record['image_path']} listed in DB but not found on disk.", "warning")

        flash(f'Criminal "{criminal_info["name"]}" and all associated data/images deleted successfully.', 'success')
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
@login_required
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
            (SELECT ci.image_path
             FROM criminal_images ci
             WHERE ci.criminal_id = c.id
             ORDER BY ci.id ASC
             LIMIT 1) as criminal_display_image_path
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
