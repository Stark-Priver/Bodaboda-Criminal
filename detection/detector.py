# detection/detector.py

import cv2
import face_recognition
import numpy as np
import os
import time
import platform
from datetime import datetime

# Database utilities
from db_utils import get_known_face_encodings, save_alert, get_criminal_id_by_name

# GPIO settings
BUZZER_PIN = 26  # GPIO pin for the buzzer (BCM mode)
MOTION_SENSOR_PIN = 4 # GPIO pin for the motion sensor (BCM mode)
BUZZER_DURATION = 5  # seconds
MOTION_DETECT_DELAY = 1 # seconds to wait after motion stops before checking again
FACE_DETECTION_DURATION = 30 # seconds to run face detection after motion is detected

# Attempt to import RPi.GPIO, fallback to mock if not available or not on RPi
try:
    if platform.system() == "Linux" and os.uname().nodename == 'raspberrypi': # crude check for RPi
        import RPi.GPIO as GPIO
        IS_RASPBERRY_PI = True
        print("RPi.GPIO loaded successfully.")
    else:
        raise ImportError("Not on a Raspberry Pi or RPi.GPIO not available, using mock.")
except ImportError:
    from gpio_mock import GPIO  # Import the mock GPIO interface
    IS_RASPBERRY_PI = False
    print("Using GPIO mock.")

# Paths
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETECTED_FACES_DIR = os.path.join(PARENT_DIR, "data", "detected_faces")
os.makedirs(DETECTED_FACES_DIR, exist_ok=True)

# --- Buzzer Control ---
def setup_buzzer():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
    if IS_RASPBERRY_PI:
        print(f"Buzzer setup on GPIO pin {BUZZER_PIN} (Actual RPi)")
    else:
        print(f"Buzzer setup on GPIO pin {BUZZER_PIN} (Mocked)")

# --- Motion Sensor Control ---
def setup_motion_sensor():
    GPIO.setwarnings(False) # Already called in setup_buzzer, but good practice if called independently
    GPIO.setmode(GPIO.BCM)  # Ensure BCM mode is set
    GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Assuming sensor outputs HIGH on detection, use pull-down
    if IS_RASPBERRY_PI:
        print(f"Motion sensor setup on GPIO pin {MOTION_SENSOR_PIN} (Actual RPi)")
    else:
        print(f"Motion sensor setup on GPIO pin {MOTION_SENSOR_PIN} (Mocked)")

def is_motion_detected():
    return GPIO.input(MOTION_SENSOR_PIN) == GPIO.HIGH

def trigger_buzzer():
    print(f"MATCH FOUND! Triggering buzzer for {BUZZER_DURATION} seconds.")
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(BUZZER_DURATION)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    print("Buzzer finished.")

def cleanup_gpio():
    GPIO.cleanup()
    if IS_RASPBERRY_PI:
        print("GPIO cleanup done (Actual RPi).")
    else:
        print("GPIO cleanup done (Mocked).")

# --- Face Recognition Processing Function ---
def process_frame_for_faces(frame, known_face_encodings, known_criminal_names, last_match_time):
    """
    Processes a single frame for face detection and recognition.
    Returns the frame with detections drawn and a dictionary of match details.
    Updates last_match_time in place.
    """
    scale_factor = 0.5
    small_frame = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    detected_match_details = [] # To store info about matches in this frame

    for (top_s, right_s, bottom_s, left_s), face_encoding in zip(face_locations, face_encodings):
        name_match = "Unknown"
        top = int(top_s / scale_factor)
        right = int(right_s / scale_factor)
        bottom = int(bottom_s / scale_factor)
        left = int(left_s / scale_factor)

        if known_face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

            if True in matches:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    name_match = known_criminal_names[best_match_index]
                    current_time = time.time()

                    is_new_match = False
                    if name_match not in last_match_time or \
                       (current_time - last_match_time[name_match]) >= COOLDOWN_PERIOD:
                        print(f"MATCH FOUND: {name_match}")
                        last_match_time[name_match] = current_time
                        is_new_match = True
                    else:
                        print(f"Matched {name_match} again within cooldown period. Displaying, but not re-triggering actions.")

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
                            save_alert(criminal_id, filepath)
                        elif not criminal_id:
                            print(f"Could not find criminal ID for {name_match}. Alert not saved to DB.")

                        trigger_buzzer() # Trigger buzzer for new, confirmed match

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
    detection_active_this_motion = False # Tracks if current motion event has initiated a detection phase

    try:
        while True:
            current_time = time.time()

            if is_motion_detected():
                if not detection_active_this_motion: # First time motion is seen in this cycle
                    print(f"{datetime.now()}: Motion detected! Starting face detection for {FACE_DETECTION_DURATION} seconds.")
                    active_detection_end_time = current_time + FACE_DETECTION_DURATION
                    detection_active_this_motion = True
                # If motion continues, active_detection_end_time is not reset here,
                # allowing the current detection window to complete.
                # Or, optionally, extend it: active_detection_end_time = current_time + FACE_DETECTION_DURATION

            if current_time < active_detection_end_time:
                ret, frame = video_capture.read()
                if not ret:
                    print("Error: Failed to capture frame.")
                    time.sleep(0.1)
                    continue

                processed_frame = process_frame_for_faces(frame, known_face_encodings, known_criminal_names, last_match_time)
                cv2.imshow('Video Feed - Criminal Detection', processed_frame)

            else: # Current time is past the active detection end time
                if detection_active_this_motion: # If it *was* active
                    print(f"{datetime.now()}: Face detection period ended. Waiting for new motion.")
                    detection_active_this_motion = False # Reset for next motion event
                    # Optionally, close the OpenCV window or display an idle message
                    # cv2.destroyWindow('Video Feed - Criminal Detection') # Example: Close window
                    # Or display a static "waiting" frame:
                    # idle_frame = np.zeros((video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT), video_capture.get(cv2.CAP_PROP_FRAME_WIDTH), 3), dtype=np.uint8)
                    # cv2.putText(idle_frame, "Waiting for motion...", (50, int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT)/2)), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
                    # cv2.imshow('Video Feed - Criminal Detection', idle_frame)


                # print(f"{datetime.now()}: No motion / detection period over. Sleeping for {MOTION_DETECT_DELAY}s")
                time.sleep(MOTION_DETECT_DELAY) # Brief pause before checking motion again

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Quitting detection loop...")
                break
            # elif key != 255: # Optional: handle other keys
            #     pass

    except KeyboardInterrupt:
        print("Detection interrupted by user (Ctrl+C).")
    finally:
        # Release handle to the webcam and clean up
        if video_capture.isOpened():
            video_capture.release()
        cv2.destroyAllWindows()
        cleanup_gpio()
        print("Detection system shut down.")


if __name__ == '__main__':
    setup_buzzer()
    setup_motion_sensor() # Setup motion sensor
    try:
        run_detection()
    except Exception as e:
        print(f"An error occurred during detection setup or runtime: {e}")
    finally:
        # Ensure cleanup happens even if run_detection fails early
        # Note: cleanup_gpio() is also called inside run_detection's finally block.
        # GPIO.cleanup() can be called multiple times, it's safe.
        # However, to avoid duplicate messages, we can rely on the one in run_detection.
        print("Main script finished.")
