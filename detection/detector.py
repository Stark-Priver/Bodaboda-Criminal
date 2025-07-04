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
BUZZER_PIN = 18  # GPIO pin for the buzzer (BCM mode)
BUZZER_DURATION = 5  # seconds

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

# --- Face Recognition Core ---
def run_detection():
    # Load known faces and encodings from the database
    known_face_encodings, known_criminal_names = get_known_face_encodings()

    if not known_face_encodings:
        print("No known faces loaded from database. Detection will not be effective.")
        # Optionally, you could decide to exit or wait here.
        # For now, it will proceed but won't find any matches.

    # Initialize webcam
    # Try different camera indices if 0 doesn't work.
    # On Windows, it's usually 0 or 1. On Pi, it might also be 0.
    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        print("Error: Could not open video stream from camera 0.")
        # Attempt camera 1 as a fallback
        video_capture = cv2.VideoCapture(1)
        if not video_capture.isOpened():
            print("Error: Could not open video stream from camera 1 either. Exiting.")
            return
        else:
            print("Successfully opened camera 1.")
    else:
        print("Successfully opened camera 0.")


    # Set camera properties (optional, can be tuned)
    # video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    # video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\nStarting face detection. Press 'q' to quit.")

    # Cooldown mechanism to prevent rapid re-triggering for the same person
    last_match_time = {} # Stores {name: timestamp}
    COOLDOWN_PERIOD = 30 # seconds

    try:
        while True:
            ret, frame = video_capture.read()
            if not ret:
                print("Error: Failed to capture frame.")
                time.sleep(0.1)
                continue

            # Resize frame for faster processing (recommended for RPi)
            # A common factor is 0.25 or 0.5. Let's use 0.5 for now.
            # If higher FPS is needed and detection still works, fx/fy can be reduced further.
            scale_factor = 0.5
            small_frame = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
            # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Find all the faces and face encodings in the current *small* frame of video
            # Using default 'hog' model for locations, which is faster. 'cnn' is more accurate but slower.
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            # Loop through each face found in the frame
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                name_match = "Unknown"

                # Scale back up face locations to original frame size for display
                top = int(top / scale_factor)
                right = int(right / scale_factor)
                bottom = int(bottom / scale_factor)
                left = int(left / scale_factor)

                if known_face_encodings: # Only try to match if there are known encodings
                    # See if the face is a match for the known face(s)
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.6)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

                    if True in matches:
                        best_match_index = np.argmin(face_distances)
                        if matches[best_match_index]:
                            name_match = known_criminal_names[best_match_index]

                            current_time = time.time()
                            if name_match in last_match_time and (current_time - last_match_time[name_match]) < COOLDOWN_PERIOD:
                                print(f"Matched {name_match} again within cooldown period. Ignoring.")
                            else:
                                print(f"MATCH FOUND: {name_match}")
                                last_match_time[name_match] = current_time

                                # Save the image of the detected face
                                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                filename = f"{name_match.replace(' ', '_')}_{timestamp_str}.jpg"
                                filepath = os.path.join(DETECTED_FACES_DIR, filename)

                                # Crop the detected face from the original frame using original coordinates
                                # (top, right, bottom, left) are already scaled back to original frame dimensions
                                h, w, _ = frame.shape
                                face_image = frame[max(0,top):min(h,bottom), max(0,left):min(w,right)]

                                if face_image.size > 0:
                                    cv2.imwrite(filepath, face_image)
                                    print(f"Saved detected face image to {filepath}")
                                else:
                                    print(f"Could not save face image for {name_match} - cropped image is empty.")
                                    filepath = None # No image saved

                                # Get criminal ID and save alert to database
                                criminal_id = get_criminal_id_by_name(name_match)
                                if criminal_id and filepath: # Only save alert if image was saved
                                    save_alert(criminal_id, filepath)
                                elif not criminal_id:
                                    print(f"Could not find criminal ID for {name_match}. Alert not saved to DB.")

                                # Trigger buzzer
                                trigger_buzzer()

                # Draw a box around the face (even if unknown and no known faces are loaded)
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
                # Draw a label with a name below the face
                cv2.rectangle(frame, (left, bottom - 25), (right, bottom), (0, 0, 255), cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name_match, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

            # Display the resulting image
            cv2.imshow('Video Feed - Criminal Detection', frame)

            # Hit 'q' on the keyboard to quit!
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Quitting detection loop...")
                break

    except KeyboardInterrupt:
        print("Detection interrupted by user (Ctrl+C).")
    finally:
        # Release handle to the webcam and clean up
        video_capture.release()
        cv2.destroyAllWindows()
        cleanup_gpio()
        print("Detection system shut down.")


if __name__ == '__main__':
    setup_buzzer()
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
