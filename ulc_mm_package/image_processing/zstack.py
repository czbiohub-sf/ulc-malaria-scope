import os
from datetime import datetime
import cv2
import numpy as np
from time import sleep

from ulc_mm_package.image_processing.focus_metrics import *
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError
from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera

def takeZStack(camera: ULCMM_Camera, motor: DRV8825Nema, steps_per_image: int=1, delay=0, save_images=True):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    save_dir = timestamp + '-zstack/'
    try:
        os.mkdir(save_dir)
    except Exception as e:
        print(f"Could not make directory {save_dir}. Encountered: \n{e}")

    # Re-home the motor to the limit switch
    motor.homed = False
    motor.homeToLimitSwitches()

    step_counter = 0
    max_steps = motor.max_pos
    focus_metrics = []
    for image in camera.yieldImages():
        image = np.ascontiguousarray(np.flipud(image))
        focus_metrics.append(gradientAverage(image))
        if save_images:
            cv2.imwrite(save_dir + f"{step_counter:03d}.tiff", image)
        motor.move_rel(steps=steps_per_image, dir=Direction.CW)
        sleep(delay)
        step_counter += steps_per_image

        if step_counter >= max_steps:
            break

    best_focus_position = np.argmax(focus_metrics)*steps_per_image
    return best_focus_position, focus_metrics

def takeZStackCoroutine(img, motor: DRV8825Nema, steps_per_coarse: int=10, steps_per_fine: int=1):
    # Re-home the motor to the limit switch
    motor.homed = False
    motor.homeToLimitSwitches()
    step_counter = 0
    max_steps = motor.max_pos
    focus_metrics = []

    # Do an initial, large-step through from 0-max position
    while step_counter < max_steps:
        img = yield img
        focus_metrics.append(gradientAverage(img))
        motor.move_rel(steps=steps_per_coarse, dir=Direction.CW)
        step_counter += steps_per_coarse
    
    # Do a 1um sweep closer to where the true focus is
    focus_metrics_fine = []
    step_counter = 0
    best_focus_position = np.argmax(focus_metrics)*steps_per_coarse
    start = best_focus_position - steps_per_coarse
    end = best_focus_position + steps_per_coarse
    motor.move_abs(start)
    step_counter = start
    while step_counter < end:
        img = yield img
        focus_metrics_fine.append(gradientAverage(img))
        motor.move_rel(steps=steps_per_fine, dir=Direction.CW)
        step_counter += steps_per_fine
    best_focus_position = start + np.argmax(focus_metrics_fine)*steps_per_fine
    motor.move_abs(best_focus_position)

if __name__ == "__main__":
    from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT

    print("===Initiating z-stack.===\n")

    # Turn on LED
    led = LED_TPS5420TDDCT()
    led.setDutyCycle(0.5)
    # Instantiate camera
    try:
        camera = ULCMM_Camera()
        camera.exposureTime_ms = 3
    except CameraError as e:
        print(f"Could not instantiate camera, encountered: \n{e}")

    # Instantiate motor
    try:
        motor = DRV8825Nema(steptype="Half")
        motor.homeToLimitSwitches()
    except MotorControllerError as e:
        print(f"Motorcontroller error, encountered: \n{e}")

    steps_per_image = 10
    most_focused, metrics = takeZStack(camera=camera, motor=motor, steps_per_image=steps_per_image, save_images=True)
    print(f"\n=======Most focused image is likely: {most_focused:03d}.tiff=======\n")

    plt.plot(range(0, int(motor.max_pos), steps_per_image), metrics, 'o', markersize=2, color='#2CBDFE')
    plt.title("Focus metric vs. motor position (um)")
    plt.xlabel("Motor position (um)")
    plt.ylabel("Focus metric")
    plt.show()
    led.close()
    motor.close()