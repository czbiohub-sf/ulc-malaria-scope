#!/usr/bin/env python
#
# Test SDL_DS3231
# John C. Shovic, SwitchDoc Labs
# 08/03/2014
#
#

# imports

import sys
import time
import datetime
import random 
import SDL_DS3231

# Main Program

print("")
print("Test SDL_DS3231 Version 1.0 - SwitchDoc Labs")
print("")
print("")
print("Program Started at:"+ time.strftime("%Y-%m-%d %H:%M:%S"))
print("")

filename = time.strftime("%Y-%m-%d%H:%M:%SRTCTest") + ".txt"
starttime = datetime.datetime.utcnow()

ds3231 = SDL_DS3231.SDL_DS3231(1, 0x68)
#comment out the next line after the clock has been initialized
ds3231.write_now()

# Main Loop - sleeps 10 seconds, then reads and prints values of all clocks
# Also reads two bytes of EEPROM and writes the next value to the two bytes 

while True:
    currenttime = datetime.datetime.utcnow()

    deltatime = currenttime - starttime
 
    print("")
    print("Raspberry Pi=\t" + time.strftime("%Y-%m-%d %H:%M:%S"))
    
    print("DS3231=\t\t%s" % ds3231.read_datetime())

    print("DS3231 Temp=", ds3231.getTemp())
    time.sleep(10.0)