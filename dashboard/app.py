import os
import sqlite3
import socket
import numpy as np
import pickle
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

# --- LCD (Optional) ---
try:
    from RPLCD.i2c import CharLCD
    lcd = CharLCD('PCF8574', 0x27)
    lcd.clear()
    lcd.write_string("Starting server...")
    LCD_ENABLED = True
except Exception as e:
    print("LCD not enabled:", e)
    LCD_ENABLED = False

# --- App Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DATABASE_PATH = os.path.join(DATA_DIR, "facial_recognition.db")
STATIC_FOLDER_PATH = os.path.join(PROJECT_ROOT, 'static')
UPLOAD_FOLDER_NAME = "criminal_photos"
UPLOAD_FOLDER_PATH = os.path.join(STATIC_FOLDER_PATH, UPLOAD_FOLDER_NAME)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER_PATH, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(PROJECT_ROOT, 'templates'), static_folder=STATIC_FOLDER_PATH)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_MUST_BE_CHANGED_123!')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_PATH
app.config['DATABASE'] = DATABASE_PATH

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
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

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CriminalForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    photo = FileField('Photo')
    submit = SubmitField('Submit Criminal')

# --- DB Helpers ---
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

# --- Init Admin ---
def ensure_admin():
    admin = query_db("SELECT * FROM admin_users WHERE username = 'admin'", one=True)
    if not admin:
        hashed_pw = generate_password_hash("admin")
        execute_db("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", ('admin', hashed_pw))
        print("Admin user created with username 'admin' and password 'admin'")

# --- LCD IP Display ---
def show_ip_on_lcd():
    if not LCD_ENABLED:
        return
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        lcd.clear()
        lcd.write_string("IP: " + ip[:16])
    except Exception as e:
        print("Could not get IP:", e)

# --- Utility Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_face_encoding(image_path):
    print(f"SIMULATOR: Simulating face encoding for image: {image_path}")
    return np.random.rand(128)

@app.context_processor
def utility_processor():
    return dict(in_app_url_rules=[rule.endpoint for rule in app.url_map.iter_rules()])

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
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        photo = request.files.get('photo')

        if not photo or photo.filename == '':
            flash('Photo is required for new criminal.', 'danger')
            return render_template('criminals/add.html', title='Add Criminal', form=form)

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
                flash('No face detected in uploaded photo.', 'danger')
                os.remove(filepath)
                return render_template('criminals/add.html', title='Add Criminal', form=form)

            serialized_encoding = pickle.dumps(face_encoding_array)
            db_photo_path = os.path.join(UPLOAD_FOLDER_NAME, unique_filename)

            try:
                execute_db("INSERT INTO criminals (name, description, photo_path, face_encoding) VALUES (?, ?, ?, ?)",
                           (name, description, db_photo_path, serialized_encoding))
                flash(f'Criminal "{name}" added successfully!', 'success')
                return redirect(url_for('list_criminals'))
            except Exception as e:
                flash(f'Database error: {e}', 'danger')
                os.remove(filepath)
        else:
            flash('Invalid file type.', 'danger')

    return render_template('criminals/add.html', title='Add Criminal', form=form)

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

@app.route('/data/detected_faces/<filename>')
@login_required
def serve_detected_face_image(filename):
    return send_from_directory(os.path.join(PROJECT_ROOT, "data", "detected_faces"), filename)

if __name__ == '__main__':
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please run `python database_setup.py`.")
    else:
        ensure_admin()
        show_ip_on_lcd()
    app.run(debug=True, host='0.0.0.0', port=5001)
