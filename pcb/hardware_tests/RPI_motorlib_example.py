import RPi.GPIO as GPIO
import time

# import the library
from RpiMotorLib import RpiMotorLib

# define GPIO pins
en = 26
sleep = 6
reset = 21
GPIO_pins = (-1, -1, -1)  # Microstep Resolution MS1-MS3 -> GPIO Pin
direction = 20  # Direction -> GPIO Pin
step = 19  # Step -> GPIO Pin
fault = 16

# Declare an named instance of class pass GPIO pins numbers
mymotortest = RpiMotorLib.A4988Nema(direction, step, GPIO_pins, "DRV8825")
# Enable the driver
print("Enabling driver")
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(en, GPIO.OUT)
GPIO.setup(sleep, GPIO.OUT)
GPIO.setup(reset, GPIO.OUT)
GPIO.setup(fault, GPIO.IN)
GPIO.output(en, GPIO.LOW)
GPIO.output(sleep, GPIO.HIGH)
GPIO.output(reset, GPIO.HIGH)

time.sleep(3)
# call the function, pass the arguments
# motor_go(clockwise, steptype, steps, stepdelay, verbose, initdelay)
mymotortest.motor_go(True, "Full", 250, 0.01, True, 0.01)

# print("Going the opposite direction")
time.sleep(2)
mymotortest.motor_go(False, "Full", 250, 0.01, True, 0.01)

# good practise to cleanup GPIO at some point before exit
GPIO.cleanup()
