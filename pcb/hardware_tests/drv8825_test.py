import RPi.GPIO as GPIO
import time

en = 6
sleep = 26
reset = 21
step = 19
dire = 16
fault = 20
loops = 500
# The motor is 500 steps on full stepping mode


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(en, GPIO.OUT)
GPIO.setup(sleep, GPIO.OUT)
GPIO.setup(reset, GPIO.OUT)
GPIO.setup(fault, GPIO.IN)
GPIO.setup(dire, GPIO.OUT) #direction pin 20
GPIO.setup(step, GPIO.OUT) #step pin

GPIO.output(en, GPIO.LOW)
GPIO.output(sleep, GPIO.HIGH)
GPIO.output(reset, GPIO.HIGH)
GPIO.output(dire, GPIO.HIGH) # direction
time.sleep(2)
for x in range(1, loops):
    print(x)
    GPIO.output(step, GPIO.HIGH) #step pin low
    time.sleep(0.01) #wait 0.1 secs
    GPIO.output(step, GPIO.LOW) #step pin high
    time.sleep(0.01) #wait

time.sleep(2)
print("Going the other direction")
GPIO.output(dire, GPIO.LOW)
time.sleep(2)

for x in range(1, loops):
    print(x)
    GPIO.output(step, GPIO.HIGH) #step pin low
    time.sleep(0.01) #wait 0.1 secs
    GPIO.output(step, GPIO.LOW) #step pin high
    time.sleep(0.01) #wait

GPIO.output(en, GPIO.LOW)
GPIO.output(sleep, GPIO.LOW)
GPIO.output(reset, GPIO.LOW)
GPIO.cleanup()