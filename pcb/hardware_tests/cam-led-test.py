from time import perf_counter
import cv2
from ulc_mm_package.hardware.camera import BaslerCamera
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT

if __name__ == "__main__":
    cam = BaslerCamera()
    led = LED_TPS5420TDDCT()
    led.turnOn()
    led.setDutyCycle(0.5)
    start = perf_counter()

    for img in cam.yieldImages():
        cv2.imshow("preview", img)
        cv2.waitKey(2)

        if perf_counter() - start >= 5:
            led.turnOff()
            quit()
