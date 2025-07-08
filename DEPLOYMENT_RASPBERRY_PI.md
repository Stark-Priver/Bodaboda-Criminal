# Deploying the Border Criminal Detection System on Raspberry Pi

## 1. Introduction

This guide provides step-by-step instructions for deploying the Real-time Border Criminal Detection System on a Raspberry Pi (specifically Model 3B+, though a Raspberry Pi 4 is recommended for better performance). The system uses a camera to detect faces, compares them against a database of known individuals, and triggers alerts (buzzer, LCD message) if a match is found. A web-based admin dashboard allows for managing criminal records and viewing alerts.

**Key Components:**
*   **Detection Script (`detection/detector.py`):** Handles real-time video capture, face detection/recognition, hardware interactions (camera, buzzer, LCD, motion sensor).
*   **Admin Dashboard (`dashboard/app.py`):** A Flask web application for managing criminal profiles and viewing detection alerts. Requires login.
*   **SQLite Database (`data/facial_recognition.db`):** Stores criminal data (including face encodings), admin user credentials, and alert logs.

## 2. Hardware Requirements

*   **Raspberry Pi:** Model 3B+ or newer. Raspberry Pi 4 (2GB or more) is recommended for smoother performance.
*   **MicroSD Card:** Minimum 16GB, Class 10 or faster.
*   **Power Supply:** A suitable USB power supply for your Raspberry Pi model (e.g., 5V 2.5A for Pi 3B+, 5V 3A USB-C for Pi 4).
*   **Raspberry Pi Camera Module:** v1, v2, or HQ Camera. Ensure it's compatible with your Pi.
*   **Active Buzzer:** Standard 5V active buzzer.
*   **PIR Motion Sensor:** HC-SR501 or similar.
*   **I2C LCD Display:** 16x2 or 20x4 character LCD, typically with a PCF8574 I2C backpack.
*   **Jumper Wires:** Assorted male-to-female and male-to-male jumper wires.
*   **(Optional) Breadboard:** For neater wiring of components.
*   **(Optional) Heatsinks:** For the Raspberry Pi CPU, especially if running in a warm environment or for extended periods.

## 3. Hardware Setup & Wiring

**IMPORTANT:** Always shut down and unplug your Raspberry Pi before connecting or disconnecting components. Refer to [pinout.xyz](https://pinout.xyz/) for your specific Raspberry Pi model's GPIO layout.

*   **Camera Module:**
    *   Connect the camera ribbon cable to the Raspberry Pi's CSI (Camera Serial Interface) port. Ensure the blue tab on the cable faces away from the black clip, and the metal contacts face the PCB of the camera port. Secure the clip.

*   **Buzzer (Active):**
    *   Connect the longer leg (usually positive, marked '+') to **GPIO 26 (Physical Pin 37)**.
    *   Connect the shorter leg (usually negative, marked '-') to a **Ground Pin (GND)** (e.g., Physical Pin 39).

*   **PIR Motion Sensor (e.g., HC-SR501):**
    *   **VCC Pin:** To **5V Pin** on Raspberry Pi (e.g., Physical Pin 2 or 4).
    *   **GND Pin:** To a **Ground Pin (GND)** on Raspberry Pi (e.g., Physical Pin 6).
    *   **OUT Pin (Signal):** To **GPIO 4 (Physical Pin 7)**.

*   **I2C LCD Display (with PCF8574 backpack):**
    *   **VCC Pin:** To **5V Pin** on Raspberry Pi.
    *   **GND Pin:** To a **Ground Pin (GND)** on Raspberry Pi.
    *   **SDA Pin:** To **GPIO 2 (SDA) (Physical Pin 3)**.
    *   **SCL Pin:** To **GPIO 3 (SCL) (Physical Pin 5)**.
    *   *Note: Some LCDs may operate at 3.3V. Check your LCD's specifications. The PCF8574 backpack usually handles 5V input well.*

## 4. Software Setup - Raspberry Pi OS

1.  **Install Raspberry Pi OS:**
    *   Download the Raspberry Pi Imager from the [official website](https://www.raspberrypi.com/software/).
    *   Use the imager to flash "Raspberry Pi OS Lite" (for a headless setup) or "Raspberry Pi OS with desktop" onto your microSD card. The Lite version is recommended for better performance if you don't need a graphical interface on the Pi itself.
    *   Enable SSH and configure Wi-Fi credentials in the imager's advanced options if using headless setup.

2.  **Initial Boot and Configuration:**
    *   Insert the microSD card into the Pi and power it on.
    *   Connect via SSH (if headless) or open a terminal.
    *   Run `sudo raspi-config`:
        *   **Interface Options:**
            *   Enable `Camera`.
            *   Enable `I2C`.
        *   **Localisation Options:** Set your Locale, Timezone, and Keyboard Layout.
        *   **Advanced Options (Optional):** Expand Filesystem (usually done automatically now).
        *   Finish and reboot if prompted.

3.  **Update System Packages:**
    ```bash
    sudo apt update
    sudo apt full-upgrade -y # Use full-upgrade to handle changed dependencies
    sudo apt autoremove -y
    sudo reboot # Recommended after a major upgrade
    ```

## 5. System Dependencies Installation

Install necessary packages for Python, OpenCV, dlib, and other libraries:
```bash
sudo apt install -y python3-pip python3-venv libopenblas-dev liblapack-dev libjpeg-dev cmake build-essential python3-dev python3-numpy git
```
*   `build-essential` provides tools like C/C++ compilers.
*   `libatlas-base-dev` can sometimes be an alternative for `libopenblas-dev` / `liblapack-dev` if you encounter issues.
*   The `dlib` library (a dependency of `face_recognition`) will be compiled from source by `pip` later, which can take a significant amount of time (30 minutes to over an hour on a Pi 3B+). Ensure your Pi has adequate cooling and a stable power supply during this process.

## 6. Project Code Setup

1.  **Clone the Repository:**
    Replace `<repository_url>` with the actual URL of your Git repository.
    ```bash
    git clone <repository_url>
    cd your_project_directory_name # Navigate into the cloned project folder
    ```

## 7. Python Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

1.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv venv
    ```

2.  **Activate the Virtual Environment:**
    ```bash
    source venv/bin/activate
    ```
    You should see `(venv)` at the beginning of your command prompt. To deactivate later, simply type `deactivate`.

## 8. Install Python Dependencies

1.  **Install Libraries:**
    While the virtual environment is active:
    ```bash
    pip install --upgrade pip # Upgrade pip itself
    pip install -r requirements.txt
    ```
    This step will download and install all Python libraries listed in `requirements.txt`, including `Flask`, `face_recognition`, `opencv-python`, `RPLCD`, `Flask-Login`, `Flask-WTF`.
    *   **`dlib` Compilation:** This is the most time-consuming part. Be patient. If it fails due to memory issues (less common on Pi 3B+ with 1GB RAM if OS Lite is used, but possible), you might need to temporarily increase swap space:
        ```bash
        # Check current swap
        free -h
        # Temporarily increase swap (e.g., to 1GB or 2GB)
        # sudo dphys-swapfile swapoff
        # sudo nano /etc/dphys-swapfile
        # # Change: CONF_SWAPSIZE=100 to CONF_SWAPSIZE=1024 (for 1GB) or 2048 (for 2GB)
        # sudo dphys-swapfile setup
        # sudo dphys-swapfile swapon
        # # After dlib installation, revert swap to original size and reboot or turn swap off/on
        ```

## 9. Database Initialization

1.  **Run the Database Setup Script:**
    Ensure your virtual environment is active. From the project's root directory:
    ```bash
    python database_setup.py
    ```
    This will create the `data/facial_recognition.db` file with the necessary tables (`criminals`, `alerts`, `admin_users`) and create a default admin user.

2.  **IMPORTANT: Change Default Admin Password!**
    The `database_setup.py` script creates a default admin user with credentials:
    *   **Username:** `admin`
    *   **Password:** `password`
    **You MUST change this password immediately for security.**
    Currently, there isn't an in-app way to change the password. You can do this by:
    *   **Option A (Recommended for now): Manually update via SQLite CLI:**
        1.  Install SQLite command-line tool: `sudo apt install sqlite3`
        2.  Open the database: `sqlite3 data/facial_recognition.db`
        3.  Generate a new password hash. You can do this with a simple Python script on your Pi or another machine:
            ```python
            # In a Python interpreter (ensure werkzeug is installed: pip install werkzeug)
            from werkzeug.security import generate_password_hash
            new_password = "your_new_strong_password"
            hashed_password = generate_password_hash(new_password)
            print(hashed_password)
            ```
        4.  Copy the generated hash.
        5.  In the SQLite CLI, update the password:
            ```sql
            UPDATE admin_users SET password_hash = 'paste_your_new_hashed_password_here' WHERE username = 'admin';
            .quit
            ```
    *   **Option B (Future):** A dedicated password change script or dashboard feature would be ideal.

## 10. Application Configuration

1.  **Flask Secret Key:**
    The Flask application requires a `SECRET_KEY` for session management and security. The default key in `dashboard/app.py` is for development only. For production, set a strong, random secret key as an environment variable.
    *   Generate a strong key (e.g., `python -c 'import secrets; print(secrets.token_hex(24))'`).
    *   This key will be passed to the application when running it as a service (see Systemd section).

2.  **Terminal ID (Optional Customization):**
    The detection script uses a `TERMINAL_ID` (default: `"BDR_TERM_01"`) in `detection/detector.py`. If deploying multiple devices, you should change this ID for each Pi to uniquely identify alerts. This will be moved to a central configuration file in future updates.

3.  **LCD Configuration (If Necessary):**
    The `detection/lcd_utils.py` script uses default I2C address (`0x27`) and port (`1`) for the LCD. If your LCD uses a different address or if you are using an older Pi (which might use I2C port `0`), you may need to adjust these values in `lcd_utils.py` or, ideally, move them to a configuration file (future update). You can find your LCD's I2C address using `sudo i2cdetect -y 1` (or `-y 0` for old Pis).

## 11. Running the Application Manually (for Testing)

Ensure your virtual environment (`venv`) is active.

1.  **Run the Admin Dashboard:**
    ```bash
    python dashboard/app.py
    ```
    The dashboard should be accessible from a web browser on another computer on the same network at `http://<RaspberryPi_IP_Address>:5001`. Find your Pi's IP using `hostname -I`.

2.  **Run the Detection Script:**
    Open another terminal session on the Pi (or use a tool like `screen` or `tmux`), activate the virtual environment, and run:
    ```bash
    python detection/detector.py
    ```
    *   On the first run, the Pi's IP address should be displayed on the LCD.
    *   The script will then start monitoring for motion and performing face detection.

## 12. Running as Services on Boot (systemd)

To ensure the dashboard and detection script start automatically on boot and restart if they crash, set them up as `systemd` services.

1.  **Create Service File for the Detection Script:**
    `sudo nano /etc/systemd/system/boda_detector.service`
    Paste the following content, **making sure to replace `/home/pi/your_project_directory` with the absolute path to your project's root folder** and `pi` with your actual username if different.

    ```ini
    [Unit]
    Description=Border Criminal Detection Service
    After=network.target multi-user.target # Ensure network and basic system is up

    [Service]
    User=pi
    Group=pi
    WorkingDirectory=/home/pi/your_project_directory
    # Ensure the Python from your virtual environment is used:
    ExecStart=/home/pi/your_project_directory/venv/bin/python /home/pi/your_project_directory/detection/detector.py

    Restart=always
    RestartSec=10s
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=boda-detector

    [Install]
    WantedBy=multi-user.target
    ```

2.  **Create Service File for the Flask Dashboard:**
    `sudo nano /etc/systemd/system/boda_dashboard.service`
    Again, **replace paths and username**.

    ```ini
    [Unit]
    Description=Border Criminal Dashboard Service
    After=network.target # Needs network to be accessible

    [Service]
    User=pi
    Group=pi
    WorkingDirectory=/home/pi/your_project_directory
    # Pass the FLASK_SECRET_KEY as an environment variable:
    Environment="FLASK_SECRET_KEY=your_strong_random_secret_key_here"
    ExecStart=/home/pi/your_project_directory/venv/bin/python /home/pi/your_project_directory/dashboard/app.py

    Restart=always
    RestartSec=10s
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=boda-dashboard

    [Install]
    WantedBy=multi-user.target
    ```
    **IMPORTANT:** Replace `your_strong_random_secret_key_here` in the `Environment` line with the actual strong secret key you generated.

3.  **Enable and Start the Services:**
    ```bash
    sudo systemctl daemon-reload        # Reload systemd to recognize new service files
    sudo systemctl enable boda_detector.service boda_dashboard.service # Enable them to start on boot
    sudo systemctl start boda_detector.service  # Start them immediately
    sudo systemctl start boda_dashboard.service
    ```

4.  **Check Service Status:**
    ```bash
    sudo systemctl status boda_detector.service
    sudo systemctl status boda_dashboard.service
    ```
    To view live logs:
    ```bash
    sudo journalctl -fu boda_detector.service
    sudo journalctl -fu boda_dashboard.service
    ```

## 13. First Time Use & Operation

1.  **Access Dashboard:** Open `http://<RaspberryPi_IP_Address>:5001` in your browser.
2.  **Login:** Use the default credentials (`admin`/`password`) or the new ones if you changed the password.
3.  **CHANGE ADMIN PASSWORD:** If you haven't already, this is critical.
4.  **Add Criminals:** Navigate to "Manage Criminals" and add individuals with clear facial photos.
5.  **Detector Script:**
    *   The LCD should show the Pi's IP on its first startup (after the IP flag file is created, it will skip this).
    *   Subsequently, it will display "System Ready" or "Monitoring...".
    *   When motion is detected, it will show "Motion Detected!", "Scanning...".
    *   If a registered criminal is detected, the buzzer will sound, and the LCD will display "CRIMINAL DETECTED!" with the name.
6.  **View Alerts:** Check the "View Alerts" page on the dashboard to see logs of detected criminals.

## 14. Troubleshooting

*   **Camera Not Detected:**
    *   Ensure camera is enabled in `raspi-config`.
    *   Check ribbon cable connections on both ends (Pi and camera module).
    *   Test with `libcamera-still -o test.jpg` (for newer OS versions) or `raspistill -o test.jpg` (for older).
*   **I2C LCD Not Working:**
    *   Ensure I2C is enabled in `raspi-config`.
    *   Check wiring (SDA, SCL, VCC, GND).
    *   Verify I2C address: `sudo i2cdetect -y 1` (or `0`). If it's not `0x27`, update `detection/lcd_utils.py` (or future config file).
*   **Python Script Errors:**
    *   Check logs: `sudo journalctl -u boda_detector` or `sudo journalctl -u boda_dashboard`.
    *   Ensure virtual environment is active if running manually.
    *   Verify all dependencies in `requirements.txt` installed correctly.
*   **`dlib` Compilation Errors:**
    *   Ensure all system dependencies from section 5 are installed.
    *   Try increasing swap space (see section 8).
    *   Ensure sufficient power supply.
*   **Performance Issues (Pi 3B+):**
    *   Use Raspberry Pi OS Lite.
    *   Ensure good cooling.
    *   The system is demanding; a Pi 4 will offer a much better experience. Frame scaling is already used in `detector.py` to help.

This concludes the deployment guide. Remember to keep your system and dependencies updated for security and stability.
```
