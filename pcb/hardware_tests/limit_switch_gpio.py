import RPi.GPIO as GPIO
import time

ls1 = 18
# LS1 = 18, LS2 = 15


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(ls1, GPIO.IN,pull_up_down=GPIO.PUD_UP)

try:
    while True:
        if not GPIO.input(ls1):
            print("Pressed")
        time.sleep(0.25)
except KeyboardInterrupt:
    GPIO.cleanup()