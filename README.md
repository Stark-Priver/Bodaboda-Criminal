# Criminal Detection at Congested Bodaboda Stations Using Raspberry Pi

This project is a facial recognition system designed to run on a Raspberry Pi (or a Windows PC for development/testing). It detects faces in real-time from a camera feed, compares them against a local database of known individuals (e.g., wanted criminals), and triggers alerts if a match is found. Alerts include saving a record to a database, saving an image of the detected face, and activating a buzzer on Raspberry Pi. A web-based dashboard allows for managing individuals and viewing alerts.

## Features

-   **Real-time Face Detection & Recognition:** Uses `opencv-python` and `face_recognition` libraries.
-   **Local SQLite Database:** Stores criminal profiles (including face encodings) and alert logs.
-   **Web Admin Dashboard:** Built with Flask for:
    -   Managing criminal records (add, edit, delete with photo uploads and automatic face encoding).
    -   Viewing detailed alert logs with images.
-   **GPIO Buzzer Alert:** Activates a buzzer on Raspberry Pi when a match is found.
-   **Cross-Platform Development:**
    -   Supports webcam input on Windows and Raspberry Pi.
    -   Automatic GPIO mocking for running the detection script on non-Raspberry Pi systems (like Windows) without hardware errors.
-   **Performance Optimized:** Frame resizing implemented in the detection script for better performance on Raspberry Pi.
-   **Offline Capability:** Designed to run entirely offline once deployed on the Raspberry Pi (internet needed only for initial setup/dependency download).

## Folder Structure

```
/
|-- dashboard/                # Flask web application (app.py)
|-- data/                     # Data files
|   |-- facial_recognition.db # SQLite database (created automatically if not present)
|   |-- detected_faces/       # Images of faces that triggered alerts (created automatically)
|   |-- sample_criminals/     # Sample images for testing (you can add more)
|-- detection/                # Face detection scripts
|   |-- detector.py           # Main detection script
|   |-- db_utils.py           # Database utilities for the detector
|   |-- gpio_mock.py          # GPIO mocking for non-RPi systems
|-- static/                   # Static files for the web dashboard
|   |-- css/style.css         # Custom stylesheets
|   |-- images/placeholder.png # Placeholder image
|   |-- criminal_photos/      # Uploaded photos of criminals (created automatically)
|-- templates/                # HTML templates for the web dashboard
|   |-- layout.html           # Base layout
|   |-- criminals/            # Templates for criminal management
|   |-- alerts/               # Templates for alert viewing
|-- requirements.txt          # Python dependencies
|-- database_setup.py         # Script to initialize/reset the database schema
|-- README.md                 # This file
```

## System Requirements

### Common for All Systems
-   Python 3.7+
-   Pip package installer
-   Webcam (for Windows/PC testing) or Raspberry Pi Camera Module

### Windows Specific
-   **CMake:** Required for `dlib` installation. Download from [cmake.org](https://cmake.org/download/). Make sure to add CMake to your system PATH during installation.
-   **C++ Compiler:** `dlib` also needs a C++ compiler. Visual Studio Build Tools are recommended.
    -   Go to the [Visual Studio Downloads page](https://visualstudio.microsoft.com/downloads/).
    -   Under "Tools for Visual Studio", download "Build Tools for Visual Studio".
    -   During installation, select "C++ build tools" and ensure the latest MSVC and Windows SDK are included.

### Raspberry Pi Specific
-   Raspberry Pi 3B+ or newer (Raspberry Pi 4 recommended for better performance).
-   Raspberry Pi OS (Legacy or newer, 32-bit or 64-bit).
-   Raspberry Pi Camera Module (correctly configured via `raspi-config`).
-   Buzzer (and jumper wires to connect to GPIO pins).
-   Required system libraries for building `dlib` and `OpenCV` dependencies:
    ```bash
    sudo apt-get update
    sudo apt-get install -y cmake libopenblas-dev liblapack-dev libjpeg-dev python3-dev
    # For OpenCV, python3-opencv from apt might be older. If issues arise or specific features are needed,
    # compiling OpenCV from source or using a specific wheel might be necessary.
    # For face_recognition, numpy is also a core dependency, usually handled by pip.
    sudo apt-get install -y python3-numpy # Often good to have the system version aligned
    ```

## Installation and Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    This step can take a while, especially `dlib` and `face_recognition`.
    ```bash
    pip install -r requirements.txt
    ```
    **Troubleshooting `dlib` installation:**
    -   **Windows:** Ensure CMake is installed and in PATH, and C++ Build Tools are installed. If errors persist, try installing `dlib` via a pre-compiled wheel if available for your Python version/architecture, or install it manually first: `pip install dlib` then `pip install -r requirements.txt --no-deps face_recognition` (this is a bit hacky, better to ensure build environment is correct).
    -   **Raspberry Pi:** Ensure all system libraries listed under "Raspberry Pi Specific" requirements are installed. If memory issues occur during `dlib` compilation, try increasing swap space temporarily.
        ```bash
        # Example to temporarily increase swap on RPi (if needed during dlib build)
        # sudo dphys-swapfile swapoff
        # sudo nano /etc/dphys-swapfile # Change CONF_SWAPSIZE to 1024 or 2048
        # sudo dphys-swapfile setup
        # sudo dphys-swapfile swapon
        # # Remember to revert after installation if desired
        ```

4.  **Initialize the Database:**
    Run the database setup script from the project root directory:
    ```bash
    python database_setup.py
    ```
    This will create `data/facial_recognition.db` and the necessary tables.

## Running the System

The system has two main components that are run separately: the Web Dashboard and the Detection Script.

### 1. Running the Web Admin Dashboard

The dashboard is used to manage criminals and view alerts.
```bash
python dashboard/app.py
```
-   By default, it runs on `http://localhost:5001` (or `http://<RaspberryPi_IP>:5001`).
-   You should see output indicating the Flask server is running.
-   **GPIO Mocking on Windows:** The dashboard itself doesn't use GPIO. The `RPi.GPIO` library is only relevant for the detection script.

### 2. Adding Criminals via the Dashboard

-   Open your web browser and navigate to `http://localhost:5001`.
-   You will be redirected to the "Manage Criminals" page.
-   Click "Add New Criminal".
-   Fill in the name, an optional description, and upload a clear photo of the person's face.
    -   **Important:** The system will attempt to detect one face in the uploaded photo. If no face is found, or multiple faces are present and it cannot determine the primary one, the criminal might not be added correctly or face encoding might fail. Use clear, passport-style photos if possible.
-   Click "Add Criminal". The system will save the photo, generate a face encoding, and store it in the database.

### 3. Running the Detection Script

This script activates the camera, detects faces, compares them to the database, and triggers alerts.

-   **Before running:** Ensure you have added at least one criminal via the dashboard.
-   Run the script from the project root:
    ```bash
    python detection/detector.py
    ```
-   A window will appear showing the camera feed.
-   If a known criminal (added via the dashboard) is detected:
    -   Their name will be displayed on the video feed.
    -   A message "MATCH FOUND: [Criminal Name]" will appear in the console.
    -   An image of the detected face will be saved in `data/detected_faces/`.
    -   An alert record will be saved to the database.
    -   **On Raspberry Pi:** The buzzer connected to GPIO 18 will sound for 5 seconds (configurable in `detector.py`).
    -   **On Windows/Other:** Mock GPIO messages will be printed to the console simulating buzzer activation.
-   Press 'q' in the OpenCV window to quit the detection script.

### 4. Viewing Alerts

-   Go to the "View Alerts" tab on the web dashboard (`http://localhost:5001/alerts`).
-   You will see a log of all detected matches, including timestamps, criminal details, and images of both the registered criminal photo and the actual detected face.
-   The alerts page automatically refreshes every 30 seconds.

## Hardware Setup (Raspberry Pi)

### Camera
-   Ensure your Raspberry Pi Camera Module is securely connected to the CSI port.
-   Enable the camera interface using `sudo raspi-config` (Interfacing Options -> Camera -> Enable).
-   Reboot if prompted.

### Buzzer
-   The system is configured to use **GPIO Pin 18 (BCM numbering)** for the buzzer.
-   Connect one leg of your buzzer to GPIO 18.
-   Connect the other leg of the buzzer to a Ground pin (GND) on the Raspberry Pi.
    (E.g., Pin 18 is physical pin 12, and a common Ground is physical pin 6, 14, 20, etc.)
-   Refer to [pinout.xyz](https://pinout.xyz/) for Raspberry Pi pin diagrams.

## Performance Considerations (Raspberry Pi)

-   **Frame Resizing:** `detector.py` resizes camera frames before processing (default scale factor 0.5). This significantly improves performance. You can adjust `scale_factor` in `detector.py` if needed (smaller values improve speed but might reduce detection range/accuracy).
-   **Face Detection Model:** The `face_recognition` library uses a HOG-based model by default, which is faster than the CNN model and suitable for Raspberry Pi.
-   **Lighting:** Good, consistent lighting is crucial for reliable face detection and recognition.
-   **Camera Focus:** Ensure your Pi camera is correctly focused.

## Running on Boot (Raspberry Pi - using systemd)

To make the detection script and web dashboard run automatically when the Raspberry Pi boots, you can create `systemd` service files.

1.  **Create a service file for the detection script:**
    `sudo nano /etc/systemd/system/boda_detector.service`

    ```ini
    [Unit]
    Description=BodaBoda Criminal Detection Service
    After=network.target # Or multi-user.target if no network needed initially by script

    [Service]
    User=pi # Replace 'pi' with the user you run the script as
    WorkingDirectory=/home/pi/your_project_directory # IMPORTANT: Update this path
    ExecStart=/home/pi/your_project_directory/venv/bin/python /home/pi/your_project_directory/detection/detector.py # IMPORTANT: Update paths
    Restart=always
    RestartSec=5s
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=boda-detector

    [Install]
    WantedBy=multi-user.target
    ```
    **Make sure to:**
    -   Replace `pi` with your actual username if different.
    -   Replace `/home/pi/your_project_directory` with the absolute path to your project's root folder.
    -   Ensure the path to python within your virtual environment (`venv/bin/python`) is correct.

2.  **Create a service file for the Flask dashboard:**
    `sudo nano /etc/systemd/system/boda_dashboard.service`

    ```ini
    [Unit]
    Description=BodaBoda Dashboard Service
    After=network.target

    [Service]
    User=pi # Replace 'pi' with your user
    WorkingDirectory=/home/pi/your_project_directory # IMPORTANT: Update this path
    ExecStart=/home/pi/your_project_directory/venv/bin/python /home/pi/your_project_directory/dashboard/app.py # IMPORTANT: Update paths
    Restart=always
    RestartSec=10s
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=boda-dashboard

    [Install]
    WantedBy=multi-user.target
    ```
    **Again, update user and paths.**

3.  **Enable and Start the Services:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable boda_detector.service
    sudo systemctl start boda_detector.service
    sudo systemctl enable boda_dashboard.service
    sudo systemctl start boda_dashboard.service
    ```

4.  **Check Status:**
    ```bash
    sudo systemctl status boda_detector.service
    sudo systemctl status boda_dashboard.service
    ```
    To view logs: `sudo journalctl -u boda_detector -f` or `sudo journalctl -u boda_dashboard -f`.

## Further Development / Potential Improvements
-   **Advanced Real-time Dashboard Updates:** Use WebSockets or Server-Sent Events for instant alert notifications on the dashboard instead of polling.
-   **Configuration File:** Move settings (GPIO pins, durations, camera index, paths) to a `config.py` or JSON/YAML file.
-   **Enhanced Logging:** Use Python's `logging` module more extensively for better diagnostics.
-   **Multiple Camera Support:** Extend the system to handle feeds from multiple cameras.
-   **User Authentication:** Add login/authentication to the web dashboard.
-   **Alert Actions:** Implement more alert actions (e.g., email notifications, SMS).
-   **Database Backups:** Implement a strategy for backing up the SQLite database.
```
