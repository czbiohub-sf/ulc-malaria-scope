from time import perf_counter
from datetime import datetime
import pickle
from ulc_mm_package.hardware.pressure_control import *
import numpy as np

if __name__ == "__main__":
    pc = PressureControl()
    pc.setDutyCycle(pc.getMaxDutyCycle())
    max_pressure = pc.getMaxDutyCycle()
    min_pressure = pc.getMinDutyCycle()
    runtime_s = 1200 # 20 minutes
    pressure_readings = []
    start = perf_counter()
    prev_change = perf_counter()

    while perf_counter() - start < runtime_s:
        reading = pc.getPressure()
        print(f"{perf_counter() - start:.2f}s ({(perf_counter() - start) / runtime_s}), {reading}hPa")
        pressure_readings.append(reading)
        
        if int(perf_counter() - start) % 120 == 0 and (perf_counter() - prev_change) > 10:
            prev_change = perf_counter()
            new_pos = pc.getCurrentDutyCycle() - 100
            pc.setDutyCycle(new_pos)
            print(f"Syringe moved to: {new_pos}")

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    with open(f"var_pressure_readings_{timestamp}.pkl", 'wb') as f:
        pickle.dump(pressure_readings, f)