import subprocess
import sys
import os
import signal
import time

# Paths to the scripts to be run
DASHBOARD_SCRIPT = os.path.join("dashboard", "app.py")
DETECTOR_SCRIPT = os.path.join("detection", "detector.py")

# Store subprocesses globally to terminate them on exit
processes = []

def start_script(script_path, script_name):
    """Starts a Python script as a subprocess."""
    try:
        # Ensure paths are correct relative to this script's location (project root)
        abs_script_path = os.path.abspath(script_path)
        if not os.path.exists(abs_script_path):
            print(f"Error: Script not found at {abs_script_path}")
            return None

        # Using sys.executable to ensure the same Python interpreter is used
        # This helps with virtual environments.
        process = subprocess.Popen(
            [sys.executable, abs_script_path],
            stdout=sys.stdout, # Pipe to main stdout
            stderr=sys.stderr, # Pipe to main stderr
            text=True # Ensures stdout/stderr are strings
        )
        print(f"{script_name} started successfully (PID: {process.pid}).")
        return process
    except Exception as e:
        print(f"Error starting {script_name} ({script_path}): {e}")
        return None

def signal_handler(sig, frame):
    """Handles Ctrl+C and other termination signals."""
    print("\nShutting down all processes...")
    for p_info in processes:
        if p_info["process"].poll() is None: # Check if process is still running
            print(f"Terminating {p_info['name']} (PID: {p_info['process'].pid})...")
            try:
                # Try to terminate gracefully first
                p_info["process"].terminate()
                # Wait a bit for graceful termination
                try:
                    p_info["process"].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"{p_info['name']} did not terminate gracefully, killing...")
                    p_info["process"].kill() # Force kill if terminate doesn't work
                print(f"{p_info['name']} terminated.")
            except Exception as e:
                print(f"Error terminating {p_info['name']}: {e}. Attempting kill...")
                try:
                    p_info["process"].kill()
                    print(f"{p_info['name']} killed.")
                except Exception as e_kill:
                     print(f"Error killing {p_info['name']}: {e_kill}")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler) # Handle kill/system shutdown signals

    print("Starting BodaBoda Criminal Detection System...")

    # Start the Dashboard
    dashboard_process = start_script(DASHBOARD_SCRIPT, "Dashboard")
    if dashboard_process:
        processes.append({"name": "Dashboard", "process": dashboard_process})
    else:
        print("Failed to start Dashboard. Exiting.")
        sys.exit(1)

    # Small delay before starting the next script, can be helpful
    time.sleep(2)

    # Start the Detector
    detector_process = start_script(DETECTOR_SCRIPT, "Detector")
    if detector_process:
        processes.append({"name": "Detector", "process": detector_process})
    else:
        print("Failed to start Detector. Terminating Dashboard and exiting.")
        signal_handler(None, None) # Trigger cleanup
        sys.exit(1)

    print("\nBoth Dashboard and Detector scripts are running.")
    print("Press Ctrl+C to stop all processes.")

    # Keep the main script alive while subprocesses are running
    # and periodically check their status.
    try:
        while True:
            all_stopped = True
            for p_info in processes:
                if p_info["process"].poll() is None:
                    all_stopped = False
                    break # At least one process is still running

            if all_stopped:
                print("All subprocesses have stopped. Exiting main script.")
                break

            time.sleep(1) # Check every second
    except Exception as e: # Catch any other exception during the wait loop
        print(f"Main loop error: {e}")
    finally:
        # Ensure cleanup happens if loop exits for any reason other than signal
        if any(p["process"].poll() is None for p in processes): # If any process is still running
            print("Main loop exited. Cleaning up any running subprocesses...")
            signal_handler(None, None)
