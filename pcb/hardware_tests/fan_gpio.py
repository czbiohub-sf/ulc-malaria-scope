import RPi.GPIO as GPIO
import time

pin = int(input("Enter pin: "))
valid_pins = {
    'scope fan': 5,
    'cam fan 1': 23,
    'cam fan 2': 24,
}
if pin not in valid_pins.values:
    raise ValueError(f"Invalid pin, expected one of {valid_pins}")

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(pin, GPIO.OUT)


print("Turning high")
GPIO.output(pin, GPIO.HIGH) # direction
time.sleep(10)
print("Turning low")
GPIO.output(pin, GPIO.LOW)
time.sleep(5)
GPIO.cleanup()