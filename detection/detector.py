# detection/detector.py

import cv2
# import face_recognition # Removed
import numpy as np
import os
import time
import platform
from datetime import datetime

# Database utilities
from .db_utils import get_known_face_encodings, save_alert, get_criminal_id_by_name
# LCD utilities
from . import lcd_utils
import config # Import the new config file

# GPIO settings from config
BUZZER_PIN = config.BUZZER_PIN
MOTION_SENSOR_PIN = config.MOTION_SENSOR_PIN
BUZZER_DURATION = config.BUZZER_DURATION
MOTION_DETECT_DELAY = config.MOTION_DETECT_DELAY
FACE_DETECTION_DURATION = config.FACE_DETECTION_DURATION
COOLDOWN_PERIOD = config.COOLDOWN_PERIOD
TERMINAL_ID = config.TERMINAL_ID

# Attempt to import RPi.GPIO, fallback to mock if not available or not on RPi
try:
    # A more robust check for Raspberry Pi might involve checking '/proc/cpuinfo' or '/sys/firmware/devicetree/base/model'
    # For now, platform.system() and os.uname() are kept from original
    is_rpi_env = False
    if platform.system() == "Linux":
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as f:
                if 'raspberry pi' in f.read().lower():
                    is_rpi_env = True
        except FileNotFoundError: # model file might not exist on all Linux, fallback
            if os.uname().nodename == 'raspberrypi': # Original check
                 is_rpi_env = True

    if is_rpi_env:
        import RPi.GPIO as GPIO
        IS_RASPBERRY_PI = True
        print("DETECTOR: RPi.GPIO loaded successfully.")
    else:
        raise ImportError("Not on a Raspberry Pi or RPi.GPIO not available, using mock.")
except ImportError:
    from .gpio_mock import GPIO  # Import the mock GPIO interface
    IS_RASPBERRY_PI = False
    print("DETECTOR: Using GPIO mock.")

# Paths
# Get project root assuming detector.py is in a subdirectory of the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DETECTED_FACES_DIR = os.path.join(DATA_DIR, config.DETECTED_FACES_SUBDIR)
IP_DISPLAYED_FLAG_FILE = os.path.join(DATA_DIR, config.IP_DISPLAYED_FLAG_FILENAME)
os.makedirs(DETECTED_FACES_DIR, exist_ok=True)

# --- Hardware Setup and Control ---
def setup_hardware():
    """Sets up Buzzer, Motion Sensor and LCD."""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Buzzer
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    print(f"DETECTOR: Buzzer setup on GPIO pin {BUZZER_PIN} ({'Actual RPi' if IS_RASPBERRY_PI else 'Mocked'})")

    # Motion Sensor
    GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    print(f"DETECTOR: Motion sensor setup on GPIO pin {MOTION_SENSOR_PIN} ({'Actual RPi' if IS_RASPBERRY_PI else 'Mocked'})")

    # LCD
    if not lcd_utils.init_lcd():
        print("DETECTOR: LCD initialization failed. Continuing without LCD.")
    else:
        # First run IP display logic
        if not os.path.exists(IP_DISPLAYED_FLAG_FILE):
            lcd_utils.display_message("Fetching IP...", "")
            lcd_utils.display_ip_address(clear_after_delay=10) # Display IP for 10s
            try:
                with open(IP_DISPLAYED_FLAG_FILE, 'w') as f:
                    f.write(datetime.now().isoformat())
                print(f"DETECTOR: IP address displayed. Flag file created: {IP_DISPLAYED_FLAG_FILE}")
                lcd_utils.display_message("System Ready", "Monitoring...", duration=2)
            except IOError as e:
                print(f"DETECTOR: Error creating IP flag file: {e}")
                lcd_utils.display_message("IP Flag Error", "", duration=2)
        else:
            print(f"DETECTOR: IP flag file found. Skipping IP display on LCD.")
            lcd_utils.display_message("System Ready", "Monitoring...", duration=2)

def old_setup_buzzer():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    # These print statements are now in setup_hardware
    # if IS_RASPBERRY_PI:
    #     print(f"Buzzer setup on GPIO pin {BUZZER_PIN} (Actual RPi)")
    # else:
    #     print(f"Buzzer setup on GPIO pin {BUZZER_PIN} (Mocked)")

# --- Motion Sensor Control (now part of setup_hardware) ---
# def setup_motion_sensor():
#     GPIO.setwarnings(False) # Already called in setup_buzzer, but good practice if called independently
#     GPIO.setmode(GPIO.BCM)  # Ensure BCM mode is set
#     GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Assuming sensor outputs HIGH on detection, use pull-down
#     if IS_RASPBERRY_PI:
#         print(f"Motion sensor setup on GPIO pin {MOTION_SENSOR_PIN} (Actual RPi)")
#     else:
#         print(f"Motion sensor setup on GPIO pin {MOTION_SENSOR_PIN} (Mocked)")

def is_motion_detected():
    return GPIO.input(MOTION_SENSOR_PIN) == GPIO.HIGH

# --- Face Detection Simulation ---
FRAME_COUNT_FOR_SIMULATION = 0 # Global counter for simulation
SIMULATE_DETECTION_INTERVAL = 150 # Simulate a detection roughly every 5 seconds (30fps * 5s)

def simulate_face_locations(frame):
    """
    Simulates face locations. Returns a predefined bounding box periodically.
    A real implementation would detect faces in the frame.
    """
    global FRAME_COUNT_FOR_SIMULATION
    FRAME_COUNT_FOR_SIMULATION += 1

    # Simulate a detection periodically
    if FRAME_COUNT_FOR_SIMULATION % SIMULATE_DETECTION_INTERVAL == 0:
        # Return a fixed bounding box (top, right, bottom, left)
        # These are coordinates for the *small_frame*
        h, w, _ = frame.shape
        # Simulate a face in the center of the frame
        # Ensure box is within frame dimensions if they are very small
        top = max(0, h // 4)
        right = min(w, w * 3 // 4)
        bottom = min(h, h * 3 // 4)
        left = max(0, w // 4)
        if top >= bottom or left >= right: # if frame is too small, make a tiny valid box
             return [(0,1,1,0)] if h > 0 and w > 0 else []
        print("SIMULATOR: Simulating face detection.")
        return [(top, right, bottom, left)]
    return []

# --- Face Comparison Simulation ---
SIMULATE_MATCH_CHANCE = 0.05 # 5% chance to simulate a match with a known criminal per detected face

def simulate_compare_faces(known_encodings, current_encoding):
    """
    Simulates comparing a detected face encoding against known encodings.
    Randomly decides if a match occurs and with which known encoding.
    Returns:
        tuple: (match_index, distance)
               match_index is the index in known_encodings if a match occurs, else None.
               distance is a random float (0.0-1.0) if match_index is not None, else 1.0.
    """
    if not known_encodings:
        return None, 1.0

    # Check for a simulated match
    if np.random.rand() < SIMULATE_MATCH_CHANCE:
        # If match, pick a random known criminal to be the "match"
        match_index = np.random.randint(0, len(known_encodings))
        simulated_distance = np.random.uniform(0.1, 0.5) # Simulate a "good" match distance
        print(f"SIMULATOR: Simulated a match with known_criminal_index {match_index} (distance: {simulated_distance:.2f})")
        return match_index, simulated_distance

    return None, 1.0 # No match


def trigger_buzzer_and_lcd_alert(criminal_name: str):
    print(f"SIMULATOR: MATCH FOUND FOR: {criminal_name}! Triggering buzzer and LCD alert.") # Updated print
    lcd_utils.display_message("CRIMINAL DETECTED!", criminal_name[:lcd_utils.DEFAULT_LCD_COLS], duration=BUZZER_DURATION) # Display for buzzer duration

    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(BUZZER_DURATION) # Buzzer sounds while LCD shows message
    GPIO.output(BUZZER_PIN, GPIO.LOW)

    print("Buzzer finished.")
    # After alert, LCD can revert to a general status or be cleared by next state
    # For now, let the main loop handle subsequent LCD messages.


def cleanup_resources():
    GPIO.cleanup()
    print(f"DETECTOR: GPIO cleanup done ({'Actual RPi' if IS_RASPBERRY_PI else 'Mocked'}).")
    lcd_utils.close_lcd()
    print("DETECTOR: LCD resources closed.")

# --- Face Recognition Processing Function ---
def process_frame_for_faces(frame, known_face_encodings, known_criminal_names, last_match_time):
    """
    Processes a single frame for face detection and recognition.
    Returns the frame with detections drawn and a dictionary of match details.
    Updates last_match_time in place.
    """
    # scale_factor = 0.5 # Now from config
    small_frame = cv2.resize(frame, (0, 0), fx=config.DETECTOR_SCALE_FACTOR, fy=config.DETECTOR_SCALE_FACTOR)
    # rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB) # Not needed for simulation

    # Simulate face locations
    face_locations = simulate_face_locations(small_frame)
    # Simulate face encodings (will be done in the next step, for now, let's prepare for it)
    # face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
    face_encodings = [np.random.rand(128) for _ in face_locations] # Placeholder for simulated encodings

    detected_match_details = [] # To store info about matches in this frame
    scale_factor = config.DETECTOR_SCALE_FACTOR # Define scale_factor locally

    for (top_s, right_s, bottom_s, left_s), face_encoding in zip(face_locations, face_encodings):
        name_match = "Unknown"
        top = int(top_s / scale_factor)
        right = int(right_s / scale_factor)
        bottom = int(bottom_s / scale_factor)
        left = int(left_s / scale_factor)

        if known_face_encodings:
            # Simulate comparing the current face_encoding with all known_face_encodings
            match_index, distance = simulate_compare_faces(known_face_encodings, face_encoding)

            if match_index is not None: # If a simulated match occurred
                name_match = known_criminal_names[match_index]
                current_time = time.time()

                is_new_match = False
                if name_match not in last_match_time or \
                   (current_time - last_match_time[name_match]) >= COOLDOWN_PERIOD:
                    # This print is now inside trigger_buzzer_and_lcd_alert
                    # print(f"MATCH FOUND: {name_match}")
                    last_match_time[name_match] = current_time
                    is_new_match = True
                else:
                    print(f"SIMULATOR: Matched {name_match} again within cooldown period. Displaying, but not re-triggering actions.")

                # Save image and alert only for new matches
                if is_new_match:
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{name_match.replace(' ', '_')}_{timestamp_str}.jpg"
                        filepath = os.path.join(DETECTED_FACES_DIR, filename)

                        h, w, _ = frame.shape
                        face_image = frame[max(0,top):min(h,bottom), max(0,left):min(w,right)]

                        if face_image.size > 0:
                            cv2.imwrite(filepath, face_image)
                            print(f"Saved detected face image to {filepath}")
                        else:
                            print(f"Could not save face image for {name_match} - cropped image is empty.")
                            filepath = None

                        criminal_id = get_criminal_id_by_name(name_match)
                        if criminal_id and filepath:
                            save_alert(criminal_id, filepath, terminal_id=TERMINAL_ID)
                        elif not criminal_id:
                            print(f"DETECTOR: Could not find criminal ID for {name_match}. Alert not saved to DB.")

                        trigger_buzzer_and_lcd_alert(name_match) # Trigger buzzer and update LCD

        # Draw visuals on the frame
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
        cv2.rectangle(frame, (left, bottom - 25), (right, bottom), (0, 0, 255), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name_match, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

    return frame


# --- Main Detection Loop ---
def run_detection():
    known_face_encodings, known_criminal_names = get_known_face_encodings()
    if not known_face_encodings:
        print("No known faces loaded. Detection will be ineffective.")

    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        video_capture = cv2.VideoCapture(1)
        if not video_capture.isOpened():
            print("Error: Could not open video stream from any camera. Exiting.")
            return
        print("Successfully opened camera 1.")
    else:
        print("Successfully opened camera 0.")

    print("\nSystem ready. Waiting for motion. Press 'q' to quit.")
    last_match_time = {}
    active_detection_end_time = 0
    detection_active_this_motion = False
    last_lcd_update_time = 0
    lcd_update_interval = 5 # Update LCD status every 5 seconds if nothing else is happening

    try:
        # Initial LCD message if not handled by IP display
        if os.path.exists(IP_DISPLAYED_FLAG_FILE): # If IP was not shown, this is the first "ready" message
             lcd_utils.display_message("System Ready", "Monitoring...", duration=2)

        while True:
            current_time = time.time()
            motion_now = is_motion_detected()

            if motion_now:
                if not detection_active_this_motion:
                    print(f"{datetime.now()}: Motion detected! Starting face detection for {FACE_DETECTION_DURATION}s.")
                    lcd_utils.display_message("Motion Detected!", "Scanning...", duration=1) # Short message
                    active_detection_end_time = current_time + FACE_DETECTION_DURATION
                    detection_active_this_motion = True
                # Optional: If motion continues, extend active_detection_end_time
                # active_detection_end_time = current_time + FACE_DETECTION_DURATION

            if current_time < active_detection_end_time:
                ret, frame = video_capture.read()
                if not ret:
                    print("DETECTOR: Error: Failed to capture frame.")
                    time.sleep(0.1)
                    continue

                processed_frame = process_frame_for_faces(frame, known_face_encodings, known_criminal_names, last_match_time)
                cv2.imshow('Video Feed - Criminal Detection', processed_frame)
                # LCD is updated by trigger_buzzer_and_lcd_alert on match
                # Could add a "Scanning..." message here if desired, but might be too frequent

            else: # Current time is past the active detection end time or no motion started it
                if detection_active_this_motion: # If detection period just ended
                    print(f"{datetime.now()}: Face detection period ended. Waiting for new motion.")
                    lcd_utils.display_message("Scan Complete", "Monitoring...", duration=3)
                    detection_active_this_motion = False

                # Display "Monitoring..." periodically if LCD is free and not showing a recent alert
                if current_time - last_lcd_update_time > lcd_update_interval and not detection_active_this_motion:
                    # Avoid overwriting a recent alert message from trigger_buzzer_and_lcd_alert
                    # The duration on that function handles its display time.
                    # This logic is a bit tricky to ensure alerts are not immediately overwritten.
                    # For simplicity, let's assume any call to display_message should be seen.
                    # The 'duration' parameter in display_message handles temporary messages.
                    # If a message has no duration, it persists.
                    # So, if no motion and no active detection, periodically show "Monitoring"
                    lcd_utils.display_message("Status: Idle", "Monitoring...", duration=0) # Persistent until next event
                    last_lcd_update_time = current_time

                # print(f"{datetime.now()}: No motion / detection period over. Sleeping for {MOTION_DETECT_DELAY}s")
                # Hide the OpenCV window when not actively detecting to save resources / be less intrusive
                # cv2.destroyWindow('Video Feed - Criminal Detection') # This might be too aggressive
                time.sleep(MOTION_DETECT_DELAY)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("DETECTOR: Quitting detection loop...")
                lcd_utils.display_message("System Quitting", "", duration=2)
                break

    except KeyboardInterrupt:
        print("DETECTOR: Detection interrupted by user (Ctrl+C).")
        lcd_utils.display_message("System Halted", "User Interrupt", duration=2)
    finally:
        if video_capture.isOpened():
            video_capture.release()
        cv2.destroyAllWindows()
        cleanup_resources() # Cleans GPIO and LCD
        print("DETECTOR: Detection system shut down.")


if __name__ == '__main__':
    setup_hardware() # Initialize Buzzer, Motion Sensor, and LCD (including IP display logic)
    try:
        run_detection()
    except Exception as e:
        print(f"DETECTOR: An error occurred: {e}")
        # Try to display on LCD if available
        lcd_utils.display_message("FATAL ERROR", str(e)[:lcd_utils.DEFAULT_LCD_COLS], duration=5)
    finally:
        # cleanup_resources is called within run_detection's finally block.
        # Calling it again here would be redundant but safe.
        print("DETECTOR: Main script finished.")
