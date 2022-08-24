import RPi.GPIO as GPIO
import time

pin = 24
# Scope fan = 5, cam fan 1 = 23, cam fan 2 = 24

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