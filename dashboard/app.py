import os
import sqlite3
import numpy as np
import pickle
import socket
from flask import Flask, render_template, request, redirect, url_for, flash, g, send_from_directory
from werkzeug.utils import secure_filename

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_face_encoding(image_path):
    print(f"SIMULATOR: Simulating face encoding for image: {image_path}")
    return np.random.rand(128)

@app.context_processor
def utility_processor():
    return dict(in_app_url_rules=[rule.endpoint for rule in app.url_map.iter_rules()])

# --- Routes (No Authentication) ---
@app.context_processor
def inject_user():
    class DummyUser:
        is_authenticated = True
        username = "admin"
    return dict(current_user=DummyUser())
@app.route('/logout')
def logout():
    # Just redirect to homepage or criminals list
    return redirect(url_for('list_criminals'))


@app.route('/')
def index():
    return redirect(url_for('list_criminals'))

@app.route('/criminals')
def list_criminals():
    criminals_data = query_db("SELECT id, name, description, photo_path FROM criminals ORDER BY name")
    return render_template('criminals/list.html', title='Manage Criminals', criminals=criminals_data)

@app.route('/criminals/add', methods=['GET', 'POST'])
def add_criminal():
    from flask_wtf import FlaskForm
    from wtforms import StringField, FileField, TextAreaField, SubmitField
    from wtforms.validators import DataRequired, Length, Optional

    class CriminalForm(FlaskForm):
        name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
        description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
        photo = FileField('Photo')
        submit = SubmitField('Submit Criminal')

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
def serve_detected_face_image(filename):
    return send_from_directory(os.path.join(PROJECT_ROOT, "data", "detected_faces"), filename)

# --- Helper to create default admin user ---
def ensure_admin():
    admin = query_db("SELECT * FROM admin_users WHERE username = 'admin'", one=True)
    if not admin:
        print("Creating default admin user with username 'admin' and password 'admin'. Please change this password immediately.")
        from werkzeug.security import generate_password_hash
        hashed_pw = generate_password_hash("admin")
        execute_db("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", ("admin", hashed_pw))

# --- Helper to get local IP ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Unknown IP"

# --- LCD Display Setup (optional) ---
LCD_ENABLED = True
lcd = None
try:
    from RPLCD.i2c import CharLCD
    if LCD_ENABLED:
        lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2)
except ModuleNotFoundError:
    print("LCD not enabled: No module named 'RPLCD'")

def display_ip_on_lcd(ip):
    if lcd:
        lcd.clear()
        lcd.write_string("RPI IP Address:")
        lcd.crlf()
        lcd.write_string(ip)
    else:
        print("LCD not initialized, skipping IP display")

if __name__ == '__main__':
    if not os.path.exists(DATABASE_PATH):
        print(f"Database not found at {DATABASE_PATH}. Please run `python database_setup.py` from the project root.")

    with app.app_context():
        ensure_admin()
        local_ip = get_local_ip()
        if LCD_ENABLED:
            display_ip_on_lcd(local_ip)
        else:
            print(f"Raspberry Pi IP: {local_ip}")

    app.run(debug=True, host='0.0.0.0', port=5001)
