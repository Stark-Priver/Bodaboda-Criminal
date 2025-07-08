# --- General Configuration ---
DATABASE_NAME = "facial_recognition.db" # In 'data/' subdirectory
UPLOAD_FOLDER_NAME = "criminal_photos" # In 'static/' subdirectory for criminal profile images
DETECTED_FACES_SUBDIR = "detected_faces" # In 'data/' subdirectory for faces captured during alerts

# --- Detection Script Configuration (detector.py) ---
TERMINAL_ID = "BDR_TERM_01" # Unique ID for this detection terminal

# GPIO Pins (BCM Mode)
BUZZER_PIN = 26
MOTION_SENSOR_PIN = 4

# Durations and Delays (seconds)
BUZZER_DURATION = 5
MOTION_DETECT_DELAY = 1      # Time to wait after motion stops before checking again or idling
FACE_DETECTION_DURATION = 30 # How long to run face detection after motion is initially detected
COOLDOWN_PERIOD = 30         # Seconds before re-triggering alert for the same detected person

# Frame processing
DETECTOR_SCALE_FACTOR = 0.5 # Factor to resize frames for faster processing in detector.py

# --- LCD Configuration (lcd_utils.py) ---
LCD_ENABLED = True # Master switch for LCD features
# I2C Settings for LCD
LCD_I2C_EXPANDER = 'PCF8574'
LCD_I2C_ADDRESS = 0x27  # Common I2C address, check with 'sudo i2cdetect -y 1'
LCD_I2C_PORT = 1        # Raspberry Pi I2C port (0 for older Pis, 1 for newer)
# LCD Dimensions
LCD_COLS = 16
LCD_ROWS = 2
LCD_AUTO_LINEBREAKS = True

# Path for the flag file to check if IP has been displayed on LCD
IP_DISPLAYED_FLAG_FILENAME = ".ip_displayed_flag" # Will be stored in 'data/' subdirectory

# --- Dashboard Configuration (dashboard/app.py) ---
# SECRET_KEY is best set via environment variable (see DEPLOYMENT_RASPBERRY_PI.md)
# For development, a default is used in app.py if ENV var is not set.
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# --- Database Setup (database_setup.py) ---
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "password" # User will be prompted to change this.
DEFAULT_ALERT_TERMINAL_ID = "UNKNOWN_TERMINAL" # Default terminal_id in alerts table schema

# Note: Absolute paths for UPLOAD_FOLDER_PATH, DATABASE_PATH etc. are constructed
# dynamically in the respective scripts (app.py, db_utils.py) using PROJECT_ROOT.
# This config file stores relative names or settings.
