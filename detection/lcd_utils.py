import socket
import time

import config # Import the new config file

# Attempt to import LCD library
LCD_AVAILABLE = False
CharLCD = None # Define CharLCD globally for type hinting if needed, and for checking

if config.LCD_ENABLED:
    try:
        from RPLCD.i2c import CharLCD
        LCD_AVAILABLE = True
    except ImportError:
        print("LCD_UTILS: RPLCD library not found, but LCD is enabled in config. LCD functionality will be disabled.")
        LCD_AVAILABLE = False # Ensure it's false if import fails
else:
    print("LCD_UTILS: LCD functionality is disabled in config.py.")


# Global LCD instance
lcd = None

# --- LCD Initialization ---
def init_lcd():
    global lcd
    if not config.LCD_ENABLED or not LCD_AVAILABLE:
        if not config.LCD_ENABLED:
            print("LCD_UTILS: LCD is disabled in configuration. Skipping initialization.")
        elif not LCD_AVAILABLE:
            print("LCD_UTILS: Cannot initialize LCD, library not available (RPLCD missing).")
        return False

    if lcd is not None:
        print("LCD_UTILS: LCD already initialized.")
        return True

    try:
        lcd = CharLCD(i2c_expander=config.LCD_I2C_EXPANDER,
                      address=config.LCD_I2C_ADDRESS,
                      port=config.LCD_I2C_PORT,
                      cols=config.LCD_COLS,
                      rows=config.LCD_ROWS,
                      auto_linebreaks=config.LCD_AUTO_LINEBREAKS)
        lcd.clear()
        lcd.write_string("System Booting...")
        print(f"LCD_UTILS: LCD initialized successfully at address {hex(config.LCD_I2C_ADDRESS)} on port {config.LCD_I2C_PORT}.")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"LCD_UTILS: Error initializing LCD: {e}")
        print("LCD_UTILS: Please check I2C address, port, connections, and config.py settings.")
        lcd = None
        return False

# --- Display Functions ---
def display_message(line1: str, line2: str = "", duration: float = 0):
    """
    Displays up to two lines of text on the LCD.
    Clears previous content.
    If duration > 0, message is displayed for that time, then LCD is cleared.
    """
    if lcd is None:
        print(f"LCD_UTILS_DISABLED: Display Message: L1: '{line1}', L2: '{line2}'")
        return

    try:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(line1[:config.LCD_COLS]) # Truncate if too long
        if line2:
            lcd.cursor_pos = (1, 0)
            lcd.write_string(line2[:config.LCD_COLS]) # Truncate if too long

        if duration > 0:
            time.sleep(duration)
            lcd.clear()
    except Exception as e:
        print(f"LCD_UTILS: Error displaying message: {e}")


def display_ip_address(clear_after_delay: float = 10.0):
    """
    Fetches and displays the device's IP address on the LCD.
    """
    if lcd is None:
        print("LCD_UTILS_DISABLED: Display IP Address requested.")
        # Try to print IP to console if LCD is not available
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            print(f"LCD_UTILS_DISABLED: IP Address: {ip_address}")
        except Exception as e:
            print(f"LCD_UTILS_DISABLED: Could not get IP: {e}")
        return

    ip_address = "IP: Not found"
    try:
        # Method 1: Using socket to a known external host (doesn't require `hostname -I`)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0) # Prevent long blocking
        s.connect(("8.8.8.8", 80)) # Google DNS, doesn't actually send data
        ip_address = s.getsockname()[0]
        s.close()
        display_message("IP Address:", ip_address)
        print(f"LCD_UTILS: Displaying IP: {ip_address}")
    except socket.error as e:
        print(f"LCD_UTILS: Could not get IP via socket: {e}. Trying hostname command...")
        try:
            # Method 2: Using hostname -I (works if network is up, might give multiple IPs)
            process = socket.create_subprocess_shell("hostname -I", stdout=socket.PIPE, stderr=socket.PIPE)
            stdout, stderr = process.communicate(timeout=2)
            ips = stdout.decode().strip().split()
            if ips:
                ip_address = ips[0] # Take the first IP
                display_message("IP Address:", ip_address)
                print(f"LCD_UTILS: Displaying IP (hostname -I): {ip_address}")
            else:
                display_message("IP Not Found", "Check Network")
                print("LCD_UTILS: 'hostname -I' returned no IP.")
        except Exception as e_cmd:
            print(f"LCD_UTILS: Error getting IP via hostname: {e_cmd}")
            display_message("IP Not Found", "Cmd Error")

    if clear_after_delay > 0:
        time.sleep(clear_after_delay)
        clear_lcd()


def clear_lcd():
    """Clears the LCD screen."""
    if lcd is None:
        # print("LCD_UTILS_DISABLED: Clear LCD requested.")
        return
    try:
        lcd.clear()
    except Exception as e:
        print(f"LCD_UTILS: Error clearing LCD: {e}")

def close_lcd():
    """Closes the LCD connection and clears the screen."""
    if lcd is None:
        # print("LCD_UTILS_DISABLED: Close LCD requested.")
        return
    try:
        lcd.clear()
        # RPLCD's CharLCD doesn't have an explicit close() method for I2C resources in the way some libraries do.
        # Clearing is usually sufficient. The Python garbage collector handles the object.
        print("LCD_UTILS: LCD cleared. (Note: RPLCD typically doesn't require explicit close for I2C)")
    except Exception as e:
        print(f"LCD_UTILS: Error during LCD close sequence: {e}")

# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    print("LCD Utils Self-Test:")
    if init_lcd():
        print("LCD Initialized for test.")
        display_message("Hello!", "LCD Test Active")
        time.sleep(3)

        display_ip_address(clear_after_delay=5)

        display_message("Test Complete.", "Shutting down LCD.", duration=3)
        close_lcd()
        print("LCD self-test finished.")
    else:
        print("LCD not initialized. Self-test cannot run display functions.")
        # Test IP fetching for console even if LCD fails
        print("Attempting to fetch IP for console:")
        display_ip_address()

    print("Testing with LCD_AVAILABLE = False (simulated)")
    LCD_AVAILABLE = False
    lcd = None # Ensure lcd object is None
    init_lcd()
    display_message("This should", "print to console.")
    display_ip_address()
    clear_lcd()
    close_lcd()
    print("Simulated test finished.")
