import RPi.GPIO as GPIO
from time import sleep

pin = 12
pwr_en = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.OUT)
GPIO.setup(pwr_en, GPIO.OUT)

# Need to enable the 5V power

GPIO.output(pwr_en, GPIO.HIGH)
GPIO.output(pin, GPIO.HIGH)
sleep(3)
GPIO.output(pin, GPIO.LOW)
pwm = GPIO.PWM(pin, 100)
print("Starting PWM")
pwm.start(5.5)
duty = 10.0
print("Changing duty cycle")
pwm.ChangeDutyCycle(duty)
sleep(5)
pwm.ChangeDutyCycle(0)
sleep(2)
GPIO.output(pwr_en, GPIO.HIGH)
GPIO.cleanup()
