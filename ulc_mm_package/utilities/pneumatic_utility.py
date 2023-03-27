# Tools for calibrating and simple usage of the pneumatic module on lfm-scope

# It has two functions so far:
#   1. Stabilize: simply stabilizes the pressure at a setpoint (cmd line input).
#       Used as a basic tool for applying a known pressure to the flow cell.

#   2. Sweep: sweep the PWM duty ratio over a pre-defined range in order to
#       discover the pressure as a function of duty ratio. Calibration values
#       are computed, corresponding to lower and upper bounds of the useful range.
#       A configuration file is written to record the upper and lower duty ratio bounds.

#       Note: a sealed flow cell must be installed on the scope in order to hold vacuum.

# Uses LFM scope pneumatic module w/ PWM controlled servo and MPRLS sensor


import os
import argparse
import socket
import time
from pathlib import Path
from os import system

import numpy as np
import matplotlib.pyplot as plt

from ulc_mm_package.hardware.dtoverlay_pwm import dtoverlay_PWM, PWM_CHANNEL
from ulc_mm_package.hardware.real.pneumatic_module import AdafruitMPRLS

PWM_FREQ = 100
DUTY_MAX = 21.2 / 100
DUTY_MIN = 15.5 / 100
DUTY_MIN_WIDE = 14 / 100
DUTY_MAX_WIDE = 22.5 / 100
P_GAIN = 0.001
P_SET_DEF = 950
LOOP_DELAY = 0.1
N_SWEEP_POINTS = 100
PERC_LOWER = 2
PERC_UPPER = 98


def init_argparse() -> argparse.ArgumentParser:
    # Not sure if this is done well, but it works

    parser = argparse.ArgumentParser(
        usage="%(prog)s [ACTION] [optional: PRESSURE SETPOINT (mbar)]",
        description="Pneumatic module testing and calibration utiliy.",
    )
    parser.add_argument("action", nargs=1)
    parser.add_argument("-p", default=P_SET_DEF, type=int)

    return parser


def calibrate_range(mpr: AdafruitMPRLS, pwm: dtoverlay_PWM) -> None:
    # Sweeps the PWM duty ratio over a wider range in order
    # to generate a pressure vs. duty ratio plot for calibration purposes

    duty_vec = np.linspace(DUTY_MAX_WIDE, DUTY_MIN_WIDE, N_SWEEP_POINTS)
    step_size = abs(np.diff(duty_vec)[0])
    press_vec = np.zeros_like(duty_vec)

    try:
        init(mpr, pwm, initial=DUTY_MAX_WIDE)

        for count, value in enumerate(duty_vec):
            pwm.setDutyCycle(value)
            time.sleep(0.25)
            press_vec[count] = int(mpr.getPressureMaxReadAttempts()[0])
            system("clear")
            print("Sweeping: duty = " + str(value) + "%")
            print("Pressure = " + str(press_vec[count]) + " mbar")
    except KeyboardInterrupt:
        pass

    finally:
        pwm.setDutyCycle(DUTY_MAX)
        time.sleep(0.5)

        mpr.close()

    p_max = max(press_vec)
    p_min = min(press_vec)
    press_range = p_max - p_min
    press_lower_bound = p_min + (PERC_LOWER / 100) * press_range
    press_upper_bound = p_min + (PERC_UPPER / 100) * press_range

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
    cal["step_size"] = step_size

    print(cal)

    create_calibration_file(cal)

    plt.plot(duty_vec, press_vec, "o-b")
    plt.plot(duty_lower_bound, press_lower_bound, "o-r")
    plt.plot(duty_upper_bound, press_upper_bound, "o-r")
    plt.show()

    return duty_vec, press_vec


def create_calibration_file(cal) -> None:
    # Writes upper and lower duty ratio bounds to a configuration file

    host = socket.gethostname()
    parent_dir = Path(__file__).resolve().parents[1]

    # Attempt to make config dir if not already there
    try:
        os.mkdir(f"{parent_dir / 'configs'}")
    except:
        pass
    save_path = Path(parent_dir / "configs" / (host + "-config.ini"))
    with open(save_path, "w") as f:
        f.write("[SYRINGE]" + "\n")
        f.write("MIN_DUTY_CYCLE = " + str(cal["duty_lower_bound"]) + "\n")
        f.write("MAX_DUTY_CYCLE = " + str(cal["duty_upper_bound"]) + "\n")
        f.write("DUTY_CYCLE_STEP = " + str(cal["step_size"]) + "\n")


def init(mpr: AdafruitMPRLS, pwm: dtoverlay_PWM, initial=DUTY_MAX) -> None:
    # Takes initial pressure measurement; pauses to wait for user to install
    # a sealed flow cell.

    # Initial pressure reading
    p_read = int(mpr.getPressureMaxReadAttempts()[0])
    print("Starting pressure -", p_read, "mb")

    # Max is no vacuum. Set initially to max
    pwm.setDutyCycle(initial)

    input("Press enter to start after loading a sealed flow cell")


def stabilize_pressure(mpr: AdafruitMPRLS, pwm: dtoverlay_PWM, p_set) -> None:
    # Stabilizes pressure using proportional feedback
    # Assumes the user installs a flow cell or otherwise seals
    # the flow path into a dead end.
    # CTRL-C to exit

    duty = DUTY_MAX

    try:
        init(mpr, pwm)

        # CTRL-C out
        while True:
            p_read = int(mpr.getPressureMaxReadAttempts()[0])
            system("clear")
            print("CTRL-C to exit...")
            print("Setpoint = " + str(p_set) + " mbar")
            print("Pressure = " + str(p_read) + " mbar")
            duty = duty + (p_set - p_read) * P_GAIN
            duty = max(duty, DUTY_MIN)
            duty = min(duty, DUTY_MAX)

            print("Duty = " + str(duty) + "%")
            pwm.setDutyCycle(duty)
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        pass

    finally:
        pwm.setDutyCycle(DUTY_MAX)
        time.sleep(0.5)


def main() -> None:
    # Parse input arguments and decide which function to call

    parser = init_argparse()
    args = parser.parse_args()

    # Instantiate pressure sensor
    mpr = AdafruitMPRLS()

    # Set up PWM output to servo
    pwm = dtoverlay_PWM(PWM_CHANNEL.PWM1)
    pwm.setFreq(PWM_FREQ)

    if args.action[0] == "stabilize":
        # Simply stabilize pressure at the setpoint
        if not args.p:
            p_set = P_SET_DEF
        else:
            p_set = int(args.p)

        stabilize_pressure(mpr, pwm, p_set)

    elif args.action[0] == "sweep":
        # Perform a sweep of the PWM range, returning pressure vs. PWM duty ratio
        calibrate_range(mpr, pwm)

    else:
        print("Argument " + str(args.action[0] + " not recognized"))


if __name__ == "__main__":
    main()
