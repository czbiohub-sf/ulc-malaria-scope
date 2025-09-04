import RPi.GPIO as GPIO
import time

pin = int(input("Enter pin: "))
valid_pins = {
    'LS1': 18,
    'LS2': 15,
}
if pin not in valid_pins.values:
    raise ValueError(f"Invalid pin, expected one of {valid_pins}")


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(pin, GPIO.IN,pull_up_down=GPIO.PUD_UP)

try:
    while True:
        if not GPIO.input(pin):
            print("Pressed")
        time.sleep(0.25)
except KeyboardInterrupt:
    GPIO.cleanup()