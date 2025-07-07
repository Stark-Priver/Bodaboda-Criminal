# Criminal Detection at Congested Bodaboda Stations Using Raspberry Pi

This project is a facial recognition system designed to run on a Raspberry Pi (or a Windows PC for development/testing). It detects faces in real-time from a camera feed, compares them against a local database of known individuals, and triggers alerts if a match is found. Alerts include saving a record to a database, saving an image of the detected face, and activating a buzzer on Raspberry Pi. A web-based dashboard, protected by user authentication, allows for managing individuals (with multiple images per person) and viewing alerts.

## Features

-   **Real-time Face Detection & Recognition:** Uses `opencv-python` and `face_recognition` libraries.
-   **Local SQLite Database:** Stores criminal profiles (supporting multiple images and face encodings per criminal), user accounts, and alert logs.
-   **Secure Web Admin Dashboard:** Built with Flask and protected by User Authentication (Login/Register). Allows for:
    -   Managing criminal records (add name/description, upload multiple images, edit details, delete specific images, delete entire criminal profile). Face encodings are automatically generated for each uploaded image.
    -   Viewing detailed alert logs with images.
-   **GPIO Buzzer Alert:** Activates a buzzer on Raspberry Pi when a match is found.
-   **Cross-Platform Development:**
    -   Supports webcam input on Windows and Raspberry Pi.
    -   Automatic GPIO mocking for running the detection script on non-Raspberry Pi systems.
-   **Single Command Execution:** A `run_project.py` script to easily start both the web dashboard and detection services.
-   **Performance Optimized:** Frame resizing implemented in the detection script for better performance on Raspberry Pi.
-   **Offline Capability:** Designed to run entirely offline once deployed on the Raspberry Pi (internet needed only for initial setup/dependency download).

## Folder Structure

```
/
|-- dashboard/                # Flask web application (app.py)
|-- data/                     # Data files
|   |-- facial_recognition.db # SQLite database
|   |-- detected_faces/       # Images of faces that triggered alerts
|   |-- sample_criminals/     # Sample images for testing
|-- detection/                # Face detection scripts
|   |-- detector.py           # Main detection script
|   |-- db_utils.py           # Database utilities for the detector
|   |-- gpio_mock.py          # GPIO mocking for non-RPi systems
|-- static/                   # Static files for the web dashboard
|   |-- css/style.css
|   |-- images/placeholder.png
|   |-- criminal_photos/      # Uploaded photos of criminals
|-- templates/                # HTML templates for the web dashboard
|   |-- layout.html
|   |-- criminals/            # Templates for criminal management
|   |-- alerts/               # Templates for alert viewing
|   |-- auth/                 # Templates for login/registration
|-- requirements.txt          # Python dependencies
|-- database_setup.py         # Script to initialize/reset the database schema
|-- run_project.py            # Main script to run both dashboard and detector
|-- README.md                 # This file
```

## System Requirements

### Common for All Systems
-   Python 3.7+
-   Pip package installer
-   Webcam (for Windows/PC testing) or Raspberry Pi Camera Module
-   Modern Web Browser

### Windows Specific
-   **CMake:** Required for `dlib` installation. Download from [cmake.org](https://cmake.org/download/). Add CMake to system PATH.
-   **C++ Compiler:** Visual Studio Build Tools recommended (select "C++ build tools" during installation).

### Raspberry Pi Specific
-   Raspberry Pi 3B+ or newer (RPi 4 recommended).
-   Raspberry Pi OS.
-   Raspberry Pi Camera Module (enabled via `raspi-config`).
-   Buzzer and jumper wires.
-   System libraries: `sudo apt-get update && sudo apt-get install -y cmake libopenblas-dev liblapack-dev libjpeg-dev python3-dev python3-numpy`

## Installation and Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Windows: venv\Scripts\activate
    # macOS/Linux: source venv/bin/activate
    ```

3.  **Install Dependencies:** (This can take time, especially `dlib`)
    ```bash
    pip install -r requirements.txt
    ```
    **Troubleshooting `dlib`:** See previous `README.md` sections or official `dlib` documentation for detailed troubleshooting if issues arise (ensure CMake and C++ compiler are correctly set up on Windows; sufficient memory/swap on RPi).

4.  **Initialize the Database:**
    Run from the project root:
    ```bash
    python database_setup.py
    ```
    This creates `data/facial_recognition.db` with the necessary tables, including `users`, `criminals`, and `criminal_images`.

## Running the System

To run the entire application (Web Dashboard and Detection Script concurrently), use the main execution script from the project root:
```bash
python run_project.py
```
This will start both components. Output from both will be displayed in your console.
-   The Web Dashboard will typically be available at `http://localhost:5001`.
-   The Detection Script will open a window showing the camera feed (if not configured for headless operation).
-   Press `Ctrl+C` in the console where `run_project.py` is running to stop both processes gracefully.

### 1. User Registration and Login

-   On first visiting `http://localhost:5001`, you will be redirected to the Login page.
-   If you don't have an account, click "Register here".
-   Complete the registration form (username, password).
-   After successful registration, you will be redirected to the Login page.
-   Log in with your new credentials.

### 2. Adding Criminals via the Dashboard (Post-Login)

-   Once logged in, navigate to "Manage Criminals" (usually the default page after login).
-   Click "Add New Criminal".
-   Fill in the name and an optional description.
-   Upload one or more clear photos of the person's face using the "Photos" file input. You can select multiple image files at once.
    -   **Important:** The system will attempt to detect one face in each uploaded photo. If no face is detected in an image, that specific image will be skipped. Use clear, well-lit photos where the face is prominent for best results.
-   Click "Add Criminal". The system will save the criminal's details. For each successfully processed photo, it will save the image file, generate a face encoding, and associate it with the criminal.

### 3. Managing Criminals

-   **Listing:** The "Manage Criminals" page lists all added individuals, showing one of their photos as a thumbnail.
-   **Editing:** Click "Edit" for a criminal to:
    -   Update their name or description.
    -   View all their associated images. Each image can be deleted individually (a criminal must retain at least one image).
    -   Upload additional images for that criminal.
-   **Deleting:** Click "Delete" on the main list to remove a criminal. This action will delete the criminal's main record, all their associated images (both database records and files), and any alerts linked to them.

### 4. Detection Script Operation

The detection script is started automatically by `run_project.py`. Its console output will appear in the same terminal as `run_project.py`.
-   **Ensure you have added at least one criminal with one or more images via the dashboard.**
-   If not running headless, a window will appear showing the camera feed.
-   If a known criminal (whose face encoding matches one stored from their images) is detected:
    -   Their name will be displayed on the video feed.
    -   A message "MATCH FOUND: [Criminal Name]" will appear in the console.
    -   An image of the detected face will be saved in `data/detected_faces/`.
    -   An alert record will be saved to the database.
    -   **On Raspberry Pi:** The buzzer connected to GPIO 18 will sound for 5 seconds.
    -   **On Windows/Other:** Mock GPIO messages will simulate buzzer activation.
-   To stop the detection script (and the dashboard), press `Ctrl+C` in the terminal where `run_project.py` is running. If the OpenCV window is active, 'q' might also stop the detection script, but `Ctrl+C` in the main terminal is the recommended way to stop everything.

### 5. Viewing Alerts

-   In the web dashboard, navigate to the "View Alerts" tab (e.g., `http://localhost:5001/alerts`).
-   You will see a log of all detected matches, including timestamps, criminal details, an image of the criminal (one of their registered photos), and the actual photo of the face that triggered the alert.
-   The alerts page automatically refreshes every 30 seconds.

## Hardware Setup (Raspberry Pi)

### Camera
-   Ensure your Raspberry Pi Camera Module is securely connected. Enable via `sudo raspi-config`. Reboot if needed.

### Buzzer
-   Connect one leg of your buzzer to **GPIO Pin 18 (BCM numbering)** and the other to a **Ground pin (GND)**. Refer to [pinout.xyz](https://pinout.xyz/).

## Performance Considerations (Raspberry Pi)

-   **Frame Resizing:** `detector.py` resizes frames (default scale factor 0.5). Adjust `scale_factor` if needed.
-   **Lighting & Focus:** Good lighting and correct camera focus are crucial.

## Running on Boot (Raspberry Pi - using systemd)

To make `run_project.py` (which starts both services) run on boot:

1.  **Create a service file:**
    `sudo nano /etc/systemd/system/boda_crime_detection_system.service`

    ```ini
    [Unit]
    Description=BodaBoda Criminal Detection System (Dashboard and Detector)
    After=network.target multi-user.target # Ensure network and user session available

    [Service]
    User=pi # Replace 'pi' with the user you run the script as
    WorkingDirectory=/home/pi/your_project_directory # IMPORTANT: Update this path
    # Ensure the venv Python is used and it's python3 explicitly if default python is 2.x
    ExecStart=/home/pi/your_project_directory/venv/bin/python3 /home/pi/your_project_directory/run_project.py
    Restart=always
    RestartSec=10s
    StandardOutput=syslog # Or append:/var/log/boda_system.log
    StandardError=syslog  # Or append:/var/log/boda_system.error.log
    SyslogIdentifier=boda-system

    [Install]
    WantedBy=multi-user.target
    ```
    **Important:**
    -   Update `User`, `WorkingDirectory`, and `ExecStart` paths to match your setup.
    -   Ensure `ExecStart` points to the Python interpreter within your virtual environment.

2.  **Enable and Start the Service:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable boda_crime_detection_system.service
    sudo systemctl start boda_crime_detection_system.service
    ```

3.  **Check Status:**
    ```bash
    sudo systemctl status boda_crime_detection_system.service
    # To view logs (if using syslog):
    # sudo journalctl -u boda_crime_detection_system -f
    ```

## Further Development / Potential Improvements
-   **Configuration File:** Centralize settings (GPIO pins, paths, etc.).
-   **Enhanced Logging:** Use Python's `logging` module more robustly.
-   **UI/UX Polish:** Improve dashboard aesthetics and user experience.
-   **More Robust Face Encoding Strategy:** For multiple images, explore averaging encodings or other techniques.
-   **Advanced Alerting:** Email/SMS notifications.
```
