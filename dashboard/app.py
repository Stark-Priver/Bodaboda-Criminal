import os
import sqlite3
import face_recognition
import numpy as np
import pickle
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename

# --- App Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = "facial_recognition.db"
DATABASE_PATH = os.path.join(PROJECT_ROOT, "data", DATABASE_NAME)
UPLOAD_FOLDER_NAME = "criminal_photos"
STATIC_FOLDER_PATH = os.path.join(PROJECT_ROOT, 'static')
UPLOAD_FOLDER_PATH = os.path.join(STATIC_FOLDER_PATH, UPLOAD_FOLDER_NAME)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER_PATH, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, 'templates'), static_folder=STATIC_FOLDER_PATH)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_for_development')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_PATH
app.config['DATABASE'] = DATABASE_PATH

# --- Database Helper Functions ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
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
    try:
        image = face_recognition.load_image_file(image_path)
        face_encodings = face_recognition.face_encodings(image)
        if face_encodings:
            return face_encodings[0]
        else:
            return None
    except Exception as e:
        print(f"Error generating face encoding for {image_path}: {e}")
        return None

@app.context_processor
def utility_processor():
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

        if not name or not photo or photo.filename == '':
            flash('Name and photo are required.', 'danger')
            return redirect(request.url)

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            base, ext = os.path.splitext(filename)
            counter, unique_filename = 1, filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                unique_filename = f"{base}_{counter}{ext}"
                counter += 1

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(filepath)
            face_encoding_array = generate_face_encoding(filepath)

            if face_encoding_array is None:
                flash('No face detected. Try another photo.', 'danger')
                os.remove(filepath)
                return redirect(request.url)

            serialized_encoding = pickle.dumps(face_encoding_array)
            db_photo_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename)
            try:
                execute_db("INSERT INTO criminals (name, description, photo_path, face_encoding) VALUES (?, ?, ?, ?)",
                           (name, description, db_photo_path, serialized_encoding))
                flash(f'Criminal "{name}" added successfully!', 'success')
            except Exception as e:
                flash(f'Error adding criminal: {e}', 'danger')
                os.remove(filepath)
                return redirect(request.url)

            return redirect(url_for('list_criminals'))

    return render_template('criminals/add.html')

@app.route('/criminals/edit/<int:criminal_id>', methods=['GET', 'POST'])
def edit_criminal(criminal_id):
    criminal = query_db("SELECT * FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    if request.method == 'POST':
        name, description = request.form.get('name'), request.form.get('description', '')
        new_photo = request.files.get('photo')

        if not name:
            flash('Name is required.', 'danger')
            return render_template('criminals/edit.html', criminal=criminal)

        current_photo_path_db = criminal['photo_path']
        current_photo_path_absolute = os.path.join(STATIC_FOLDER_PATH, current_photo_path_db) if current_photo_path_db else None
        new_db_photo_path, new_serialized_encoding = current_photo_path_db, criminal['face_encoding']

        if new_photo and new_photo.filename != '' and allowed_file(new_photo.filename):
            if current_photo_path_absolute and os.path.exists(current_photo_path_absolute):
                os.remove(current_photo_path_absolute)

            filename = secure_filename(new_photo.filename)
            base, ext, counter, unique_filename = os.path.splitext(filename)[0], os.path.splitext(filename)[1], 1, filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                unique_filename = f"{base}_{counter}{ext}"
                counter += 1

            new_photo_filepath_absolute = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            new_photo.save(new_photo_filepath_absolute)
            new_db_photo_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename)

            face_encoding_array = generate_face_encoding(new_photo_filepath_absolute)
            if face_encoding_array is None:
                flash('No face detected in new photo.', 'danger')
                return render_template('criminals/edit.html', criminal=criminal)

            new_serialized_encoding = pickle.dumps(face_encoding_array)

        try:
            execute_db("UPDATE criminals SET name = ?, description = ?, photo_path = ?, face_encoding = ? WHERE id = ?",
                       (name, description, new_db_photo_path, new_serialized_encoding, criminal_id))
            flash(f'Criminal "{name}" updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating criminal: {e}', 'danger')

        return redirect(url_for('list_criminals'))

    return render_template('criminals/edit.html', criminal=criminal)

@app.route('/criminals/delete/<int:criminal_id>', methods=['POST'])
def delete_criminal(criminal_id):
    criminal = query_db("SELECT id, name, photo_path FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    try:
        execute_db("DELETE FROM alerts WHERE criminal_id = ?", (criminal_id,))
        execute_db("DELETE FROM criminals WHERE id = ?", (criminal_id,))

        if criminal['photo_path']:
            photo_to_delete_absolute = os.path.join(STATIC_FOLDER_PATH, criminal['photo_path'])
            if os.path.exists(photo_to_delete_absolute):
                os.remove(photo_to_delete_absolute)

        flash(f'Criminal "{criminal["name"]}" and alerts deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting criminal: {e}', 'danger')

    return redirect(url_for('list_criminals'))

@app.route('/data/detected_faces/<filename>')
def serve_detected_face_image(filename):
    return send_from_directory(os.path.join(PROJECT_ROOT, "data", "detected_faces"), filename)

@app.route('/alerts')
def view_alerts():
    alerts_data = query_db("""
        SELECT a.id, a.timestamp, a.detected_face_photo_path, a.terminal_id,
               c.name as criminal_name, c.photo_path as criminal_photo_path
        FROM alerts a
        JOIN criminals c ON a.criminal_id = c.id
        ORDER BY a.timestamp DESC
    """)
    return render_template('alerts/view.html', alerts=alerts_data)

if __name__ == '__main__':
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please run `python database_setup.py` from the project root.")
    app.run(debug=True, host='0.0.0.0', port=5001)
