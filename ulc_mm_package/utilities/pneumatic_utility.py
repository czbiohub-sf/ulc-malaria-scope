# Quick and dirty stabilized pressure generator
# Uses LFM scope pneumatic module w/ PWM controlled servo
# and MPRLS sensor

import argparse
import socket
from os import system
from typing import List
import RPi.GPIO as GPIO
import board
import busio
import time
import adafruit_mprls
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

PWM_PIN = 12
PWM_FREQ = 100
#20.5 is 1.5mm off end, 21.2 is fully empty. 15.2 is the physical limit before the servo arm crashes, therefore 18.2 is the center
DUTY_MAX = 21.2
DUTY_MIN = 15.5
DUTY_MIN_WIDE = 14
DUTY_MAX_WIDE = 22.5
P_GAIN = 0.001
P_SET_DEF = 950
LOOP_DELAY = 0.1
N_SWEEP_POINTS = 100
PERC_LOWER = 4
PERC_UPPER = 96


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [ACTION] [optional: PRESSURE SETPOINT (mbar)]",
        description="Pneumatic module testing and calibration utiliy.",
        )
    parser.add_argument("action", nargs=1)
    parser.add_argument("-p", default=P_SET_DEF, type=int)

    return parser

def calibrate_range(mpr, pwm)-> None:
    # Sweeps the PWM duty ratio over a wider range in order
    # to generate a pressure vs. duty ratio plot for calibration purposes
    
    duty_vec = np.linspace(DUTY_MAX_WIDE, DUTY_MIN_WIDE, N_SWEEP_POINTS)
    press_vec = np.zeros_like(duty_vec)
    
    try:
        init(mpr, pwm, initial=DUTY_MAX_WIDE)

        for count, value in enumerate(duty_vec):
            pwm.ChangeDutyCycle(value)
            time.sleep(0.25)
            press_vec[count] = int(mpr.pressure)
            system('clear')
            print("Sweeping: duty = " + str(value) + '%')
            print( "Pressure = " + str(press_vec[count]) + " mbar")
    except KeyboardInterrupt:
        pass
    
    finally:
        pwm.ChangeDutyCycle(DUTY_MAX)
        time.sleep(.5)
        GPIO.cleanup()

    p_max = max(press_vec)
    p_min = min(press_vec)
    press_range = p_max - p_min
    press_lower_bound = p_min + (PERC_LOWER/100)*press_range
    press_upper_bound = p_min + (PERC_UPPER/100)*press_range
    
    # Using < works as the vector is in decending order
    duty_lower_bound = duty_vec[np.where(press_vec < press_lower_bound)[0][0]]
    duty_upper_bound = duty_vec[np.where(press_vec < press_upper_bound)[0][0]]

    cal = dict()
    cal["press_range"] = press_range
    cal["p_max"] = p_max
    cal["p_min"] = p_min
    cal["press_lower_bound"] = press_lower_bound
    cal["press_upper_bound"] = press_upper_bound
    cal["duty_lower_bound"] = duty_lower_bound
    cal["duty_upper_bound"] = duty_upper_bound

    print(cal)

    create_calibration_file(cal)

    plt.plot(duty_vec, press_vec,'o-b')
    plt.plot(duty_lower_bound, press_lower_bound, 'o-r')
    plt.plot(duty_upper_bound, press_upper_bound, 'o-r')
    plt.show()
    
    return duty_vec, press_vec

def create_calibration_file(cal)->None:

    host = socket.gethostname()
    with open(host + '-config.ini', 'w') as f:
        f.write('[SYRINGE]' + '\n')
        f.write("MIN_DUTY_CYCLE = " + str(cal["duty_lower_bound"]) + '\n')
        f.write("MAX_DUTY_CYCLE = " + str(cal["duty_upper_bound"]) + '\n')
        
def init(mpr, pwm, initial=DUTY_MAX)->None:

    # Initial pressure reading
    p_read = int(mpr.pressure,)
    print('Starting pressure -', p_read, 'mb')
    
    # Max is no vacuum. Set initially to max
    pwm.start(DUTY_MAX)
    
    input('Press enter to start after loading a sealed consumable ')


def stabilize_pressure(mpr, pwm, p_set) -> None:
    # Stabilizes pressure using proportional feedback
    # Assumes the user installs a flow cell or otherwise seals
    # the flow path into a dead end. 
    #CTRL-C to exit

    duty = DUTY_MAX
    
    try:

        init(mpr, pwm)

        # CTRL-C out
        while True:
            p_read=(int(mpr.pressure,))
            system('clear')
            print('CTRL-C to exit...')
            print('Setpoint = ' + str(p_set) + ' mbar')
            print( "Pressure = " + str(p_read) + " mbar")
            duty = duty + (p_set-p_read)*P_GAIN
            duty = max(duty, DUTY_MIN)
            duty = min(duty, DUTY_MAX)
            
            print( "Duty = " + str(duty) + "%")
            pwm.ChangeDutyCycle(duty)
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        pass
        
    finally:
        pwm.ChangeDutyCycle(DUTY_MAX)
        time.sleep(.5)
        GPIO.cleanup()
    

def main()-> None:
    parser = init_argparse()
    args = parser.parse_args()

    # Connect to sensor over I2C
    i2c = busio.I2C(board.SCL, board.SDA)
    mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)

    # Set up PWM output to servo
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PWM_PIN, GPIO.OUT) # was 18
    pwm = GPIO.PWM(PWM_PIN, PWM_FREQ) # was port18, 100hz


    if args.action[0] == "stabilize":
        # Simply stabilize pressure at the setpoint
        if not args.p:
            p_set = P_SET_DEF
        else:
            p_set = int(args.p)

        stabilize_pressure(mpr, pwm, p_set)

    
    elif args.action[0] == 'sweep':
        # Perform a sweep of the PWM range, returning pressure vs. PWM duty ratio
        duty, press = calibrate_range(mpr, pwm)

    else:
        print("Argument " + str(args.action[0] + " not recognized"))    

    
if __name__ == "__main__":
    main()
    
    
    
