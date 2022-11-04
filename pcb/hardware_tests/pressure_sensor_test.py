# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import digitalio
import adafruit_mprls
import RPi.GPIO as GPIO

pwr_pin = 22
rst_pin = 10
# Scope fan = 5, cam fan 1 = 23, cam fan 2 = 24

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(pwr_pin, GPIO.OUT)
GPIO.setup(rst_pin, GPIO.OUT)

time.sleep(0.5)
GPIO.output(pwr_pin, GPIO.LOW)
time.sleep(1)
GPIO.output(rst_pin, GPIO.HIGH)
#reset = digitalio.DigitalInOut(board.D25)
i2c = board.I2C()

# Simplest use, connect to default over I2C
mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)

# You can also specify both reset and eoc pins
"""
import digitalio
reset = digitalio.DigitalInOut(board.D5)
eoc = digitalio.DigitalInOut(board.D6)
mpr = adafruit_mprls.MPRLS(i2c, eoc_pin=eoc, reset_pin=reset,
                           psi_min=0, psi_max=25)
"""
try:
    while True:
        print((mpr.pressure,))
        time.sleep(1)
except:
    GPIO.output(rst_pin, GPIO.LOW)
    GPIO.output(pwr_pin, GPIO.HIGH)
    GPIO.cleanup()
