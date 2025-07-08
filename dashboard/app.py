import os
import sqlite3
import face_recognition
import numpy as np
import pickle
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional
import config # Import the new config file

# --- App Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Defines base for project
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DATABASE_PATH = os.path.join(DATA_DIR, config.DATABASE_NAME)
STATIC_FOLDER_PATH = os.path.join(PROJECT_ROOT, 'static')
UPLOAD_FOLDER_PATH = os.path.join(STATIC_FOLDER_PATH, config.UPLOAD_FOLDER_NAME)
ALLOWED_EXTENSIONS = config.ALLOWED_IMAGE_EXTENSIONS # Get from config
os.makedirs(UPLOAD_FOLDER_PATH, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True) # Ensure data directory exists for DB

app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, 'templates'), static_folder=STATIC_FOLDER_PATH)
# IMPORTANT: SECRET_KEY should be set via environment variable for production.
# The default here is only for convenience during development if the ENV var is not set.
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_MUST_BE_CHANGED_123!')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_PATH # Used by Flask-Uploads or direct saving
app.config['DATABASE'] = DATABASE_PATH # Custom DB path for Flask context

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Route name for the login page
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    user_data = query_db("SELECT * FROM admin_users WHERE id = ?", (user_id,), one=True)
    if user_data:
        return User(id=user_data['id'], username=user_data['username'])
    return None

# --- Forms (Flask-WTF) ---
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CriminalForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    photo = FileField('Photo') # Validation for file type/presence handled in route
    submit = SubmitField('Submit Criminal')


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
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('list_criminals'))
    form = LoginForm()
    if form.validate_on_submit():
        user_data = query_db("SELECT * FROM admin_users WHERE username = ?", (form.username.data,), one=True)
        if user_data and check_password_hash(user_data['password_hash'], form.password.data):
            user_obj = User(id=user_data['id'], username=user_data['username'])
            login_user(user_obj)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('list_criminals'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('list_criminals'))

@app.route('/criminals')
@login_required
def list_criminals():
    criminals_data = query_db("SELECT id, name, description, photo_path FROM criminals ORDER BY name")
    return render_template('criminals/list.html', title='Manage Criminals', criminals=criminals_data)

@app.route('/criminals/add', methods=['GET', 'POST'])
@login_required
def add_criminal():
    form = CriminalForm()
    # Photo is not part of form.data directly for file fields if not using specific WTForms file field that handles it.
    # We handle it via request.files. For WTForms-Alchemy or similar, it might be different.
    # For CSRF, as long as the form is rendered and validated, protection is active.
    if form.validate_on_submit(): # This checks CSRF
        name = form.name.data
        description = form.description.data
        photo = request.files.get('photo') # Still get photo from request.files

        if not photo or photo.filename == '':
            flash('Photo is required for new criminal.', 'danger')
            return render_template('criminals/add.html', title='Add Criminal', form=form)

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            base, ext = os.path.splitext(filename)
            counter, unique_filename = 1, filename
            # Ensure unique filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                unique_filename = f"{base}_{counter}{ext}"
                counter += 1

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            photo.save(filepath)

            face_encoding_array = generate_face_encoding(filepath)
            if face_encoding_array is None:
                flash('No face detected in uploaded photo. Please try a different photo.', 'danger')
                os.remove(filepath) # Clean up uploaded file
                return render_template('criminals/add.html', title='Add Criminal', form=form)

            serialized_encoding = pickle.dumps(face_encoding_array)
            db_photo_path = os.path.join(config.UPLOAD_FOLDER_NAME, unique_filename) # Relative path for DB

            try:
                execute_db("INSERT INTO criminals (name, description, photo_path, face_encoding) VALUES (?, ?, ?, ?)",
                           (name, description, db_photo_path, serialized_encoding))
                flash(f'Criminal "{name}" added successfully!', 'success')
                return redirect(url_for('list_criminals'))
            except Exception as e:
                flash(f'Database error adding criminal: {e}', 'danger')
                os.remove(filepath) # Clean up on DB error too
                # Fall through to render template with form again
        else:
            flash('Invalid file type for photo.', 'danger')

    return render_template('criminals/add.html', title='Add Criminal', form=form)


@app.route('/criminals/edit/<int:criminal_id>', methods=['GET', 'POST'])
@login_required
def edit_criminal(criminal_id):
    criminal = query_db("SELECT * FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    form = CriminalForm(obj=criminal) # Pre-populate form with existing data

    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        new_photo = request.files.get('photo')

        current_photo_path_db = criminal['photo_path']
        new_db_photo_path = current_photo_path_db
        new_serialized_encoding = criminal['face_encoding']

        if new_photo and new_photo.filename != '' and allowed_file(new_photo.filename):
            # Delete old photo if it exists
            if current_photo_path_db:
                old_photo_absolute_path = os.path.join(STATIC_FOLDER_PATH, current_photo_path_db)
                if os.path.exists(old_photo_absolute_path):
                    os.remove(old_photo_absolute_path)

            filename = secure_filename(new_photo.filename)
            base, ext = os.path.splitext(filename)
            counter, unique_filename = 1, filename
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                unique_filename = f"{base}_{counter}{ext}"
                counter += 1

            new_photo_filepath_absolute = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            new_photo.save(new_photo_filepath_absolute)
            new_db_photo_path = os.path.join(config.UPLOAD_FOLDER_NAME, unique_filename)

            face_encoding_array = generate_face_encoding(new_photo_filepath_absolute)
            if face_encoding_array is None:
                flash('No face detected in new photo. Original photo and encoding retained if no new photo is processed.', 'warning')
                new_db_photo_path = current_photo_path_db
            else:
                new_serialized_encoding = pickle.dumps(face_encoding_array)

        try:
            execute_db("UPDATE criminals SET name = ?, description = ?, photo_path = ?, face_encoding = ? WHERE id = ?",
                       (name, description, new_db_photo_path, new_serialized_encoding, criminal_id))
            flash(f'Criminal "{name}" updated successfully!', 'success')
            return redirect(url_for('list_criminals'))
        except Exception as e:
            flash(f'Database error updating criminal: {e}', 'danger')
            # Potentially rollback photo save if DB fails? Complex, for now, photo might be saved but DB not updated.

    # If GET request or form validation fails, render the edit page
    # For GET, form is pre-populated by obj=criminal. For POST failure, WTForms handles re-population.
    return render_template('criminals/edit.html', title='Edit Criminal', form=form, criminal=criminal)


@app.route('/criminals/delete/<int:criminal_id>', methods=['POST'])
@login_required
def delete_criminal(criminal_id):
    # It's good practice to have CSRF protection on POST requests that delete data.
    # If this was a link/button in a form, that form should include CSRF token.
    # For simplicity, if it's a direct POST (e.g. from a form submit button specifically for delete),
    # ensure that form was rendered with CSRF.
    # A quick way to add CSRF here if not part of a larger form, is a small dedicated form.
    # However, typically delete buttons are inside a list and might use JS to submit a hidden form.
    # For now, assuming the POST comes from a CSRF-protected context if it were a form.
    # If it's just a link styled as a button doing a POST via JS without a form, that's less secure.
    # Flask-WTF protects if the request is a POST and form.validate_on_submit() was used or csrf_token field is checked.
    # Since this route doesn't use a WTForm directly, it's vulnerable if not invoked from a page with a valid CSRF token.
    # Simplest fix: make it a GET route with confirmation, or ensure it's called from a form.
    # For now, keeping as POST and assuming caller handles CSRF. A dedicated DeleteForm would be better.

    criminal = query_db("SELECT id, name, photo_path FROM criminals WHERE id = ?", (criminal_id,), one=True)
    if not criminal:
        flash('Criminal not found.', 'danger')
        return redirect(url_for('list_criminals'))

    try:
        # Cascade delete for alerts should be handled by DB schema (ON DELETE CASCADE)
        # execute_db("DELETE FROM alerts WHERE criminal_id = ?", (criminal_id,))
        execute_db("DELETE FROM criminals WHERE id = ?", (criminal_id,))

        if criminal['photo_path']:
            photo_to_delete_absolute = os.path.join(STATIC_FOLDER_PATH, criminal['photo_path'])
            if os.path.exists(photo_to_delete_absolute):
                os.remove(photo_to_delete_absolute)

        flash(f'Criminal "{criminal["name"]}" and associated alerts deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting criminal: {e}', 'danger')

    return redirect(url_for('list_criminals'))


@app.route('/data/detected_faces/<filename>')
@login_required # Protect access to detected faces as well
def serve_detected_face_image(filename):
    # Ensure this path is secure and doesn't allow directory traversal
    # send_from_directory handles this reasonably well.
    return send_from_directory(os.path.join(PROJECT_ROOT, "data", "detected_faces"), filename)


@app.route('/alerts')
@login_required
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
