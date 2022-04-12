from time import perf_counter
import pickle
from ulc_mm_package.hardware.pressure_control import *

if __name__ == "__main__":
    pc = PressureControl()
    runtime_s = 1200 # 20 minutes
    pressure_readings = []
    start = perf_counter()

    while perf_counter() - start < runtime_s:
        reading = pc.getPressure()
        print(f"{perf_counter() - start:.2f}s ({(perf_counter() - start) / runtime_s}), {reading}hPa")
        pressure_readings.append(reading)

    with open("pressure_readings.pkl", 'wb') as f:
        pickle.dump(pressure_readings, f)