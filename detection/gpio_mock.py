# detection/gpio_mock.py

# This script provides a mock for RPi.GPIO for development on non-Raspberry Pi systems (e.g., Windows)

BCM = "BCM_MODE"
OUT = "OUTPUT_MODE"
HIGH = 1
LOW = 0
PUD_UP = "PULL_UP_MODE" # Placeholder, not used in current buzzer logic but good to have
PUD_DOWN = "PULL_DOWN_MODE" # Placeholder

# GPIO pin for the buzzer (example, can be configured)
BUZZER_PIN = 18 # Example GPIO pin

def setmode(mode):
    print(f"[GPIO_MOCK] Set GPIO mode to {mode}")

def setup(channel, mode, initial=LOW, pull_up_down=None):
    if isinstance(channel, list):
        for ch in channel:
            print(f"[GPIO_MOCK] Setup GPIO pin {ch} to mode {mode}, initial state {initial}")
            if pull_up_down:
                print(f"[GPIO_MOCK] Pin {ch} pull_up_down set to {pull_up_down}")
    else:
        print(f"[GPIO_MOCK] Setup GPIO pin {channel} to mode {mode}, initial state {initial}")
        if pull_up_down:
            print(f"[GPIO_MOCK] Pin {channel} pull_up_down set to {pull_up_down}")


def output(channel, state):
    pin_name = "BUZZER" if channel == BUZZER_PIN else f"PIN_{channel}"
    status = "ON" if state == HIGH else "OFF"
    print(f"[GPIO_MOCK] Set {pin_name} (GPIO {channel}) to {status} ({state})")

def cleanup(channel=None):
    if channel:
        if isinstance(channel, list):
            for ch in channel:
                print(f"[GPIO_MOCK] Cleanup GPIO pin {ch}")
        else:
            print(f"[GPIO_MOCK] Cleanup GPIO pin {channel}")
    else:
        print("[GPIO_MOCK] Cleanup all GPIO pins")

def setwarnings(flag):
    print(f"[GPIO_MOCK] Set warnings to {flag}")

# --- Potentially add more mock functions if needed by other parts of the project ---
# For example, if PWM is needed:
# class PWM:
#     def __init__(self, channel, frequency):
#         self.channel = channel
#         self.frequency = frequency
#         print(f"[GPIO_MOCK] PWM initialized on channel {self.channel} with frequency {self.frequency} Hz")

#     def start(self, duty_cycle):
#         print(f"[GPIO_MOCK] PWM started on channel {self.channel} with duty cycle {duty_cycle}%")

#     def stop(self):
#         print(f"[GPIO_MOCK] PWM stopped on channel {self.channel}")

#     def ChangeDutyCycle(self, duty_cycle):
#         print(f"[GPIO_MOCK] PWM duty cycle changed on channel {self.channel} to {duty_cycle}%")

#     def ChangeFrequency(self, frequency):
#         self.frequency = frequency
#         print(f"[GPIO_MOCK] PWM frequency changed on channel {self.channel} to {self.frequency} Hz")

# GPIO = type('GPIO', (object,), {'BCM': BCM, 'OUT': OUT, 'HIGH': HIGH, 'LOW': LOW,
#                                'setmode': setmode, 'setup': setup, 'output': output,
#                                'cleanup': cleanup, 'setwarnings': setwarnings, 'PWM': PWM})

# To make it behave more like the RPi.GPIO module, you can assign functions to a class instance
# However, for simple use cases, direct function imports are fine.
# We will conditionally import this or the real RPi.GPIO in the main detection script.

if __name__ == '__main__':
    # Example usage of the mock
    setwarnings(False)
    setmode(BCM)
    setup(BUZZER_PIN, OUT)
    print(f"Simulating turning buzzer ON (GPIO {BUZZER_PIN})")
    output(BUZZER_PIN, HIGH)
    # time.sleep(1) # Requires import time
    print(f"Simulating turning buzzer OFF (GPIO {BUZZER_PIN})")
    output(BUZZER_PIN, LOW)
    cleanup()
