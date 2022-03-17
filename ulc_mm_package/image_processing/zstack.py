import os
from datetime import datetime
import cv2
import numpy as np
from time import sleep

from ulc_mm_package.image_processing.focus_metrics import *
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError
from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera

def takeZStack(camera: ULCMM_Camera, motor: DRV8825Nema, steps_per_image: int=1, save_images=True):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    save_dir = timestamp + '-zstack/'
    try:
        os.mkdir(save_dir)
    except Exception as e:
        print(f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack.")
        return

    # Re-home the motor to the limit switch
    motor.homed = False
    motor.homeToLimitSwitches()

    step_counter = 0
    max_steps = motor.max_pos
    focus_metrics = []
    for image in camera.yieldImages():
        focus_metrics.append(gradientAverage(image))
        if save_images:
            cv2.imwrite(save_dir + f"{step_counter:03d}.tiff", image)
        motor.move_rel(steps=steps_per_image, dir=Direction.CW)
        step_counter += steps_per_image

        if step_counter > max_steps:
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
        motor.move_rel(steps=steps_per_coarse, dir=Direction.CW, stepdelay=0.001)
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

def symmetricZStack(camera: ULCMM_Camera, motor: DRV8825Nema, start_point: int, num_steps: int=30, steps_per_image: int=1, save_images=True):
    """Take a symmetric z-stack about a given motor position.

    Parameters
    ----------
    camera: ULCMM_Camera:
        An instance of the ULCMM_Camera object (defined in /hardware/camera.py)
    motor: DRV8825Nema()
        An instance of the DRV8825Nema motor driver object (defined in /hardware/motorcontroller.py).
    start_point: int
        The position to the move motor before beginning a symmetric sweep (i.e start_point +/- steps_per_image).
    num_steps: int
        The number of steps to move the motor above and below the set_point. Note that if the num_steps would
        cause the motor to go outside its range of motion, the number of steps in that direction will be clipped.

        For example, if: set_point=890, num_steps=20, and motor.min_pos = 0, motor.max_pos = 900, then 20 steps will be taken below
        (to 870), but only 10 steps will be taken above (reaching the maximum of 900).
    steps_per_image: int
        The number of motor steps to take per image.
    save_images: boolean
        Toggles whether to save images acquired to a folder.
    """

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    save_dir = timestamp + '-zstack/'
    try:
        os.mkdir(save_dir)
    except Exception as e:
        print(f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack.")
        return
    min_pos = int(start_point - num_steps)
    max_pos = int(start_point + num_steps)
    min_pos = int(min_pos) if min_pos >= 0 else 0
    max_pos = int(max_pos) if max_pos <= motor.max_pos else motor.max_pos

    motor.move_abs(min_pos)
    step_counter = min_pos
    focus_metrics = []
    for image in camera.yieldImages():
        focus_metrics.append(gradientAverage(image))
        motor.move_rel(steps=steps_per_image, dir=Direction.CW)
        if save_images:
            cv2.imwrite(save_dir + f"{step_counter:03d}.tiff", image)
        step_counter += steps_per_image
        if step_counter > max_pos:
            break
    best_focus_position = int(min_pos + np.argmax(focus_metrics)*steps_per_image)
    return best_focus_position, focus_metrics

def symmetricZStackCoroutine(motor: DRV8825Nema, start_point: int, num_steps: int=30, steps_per_image: int=1, save_images=True):
    """The coroutine companion to symmetricZStack"""

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    save_dir = timestamp + '-zstack/'
    try:
        os.mkdir(save_dir)
    except Exception as e:
        print(f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack.")
        return
    min_pos = int(start_point - num_steps)
    max_pos = int(start_point + num_steps)
    min_pos = int(min_pos) if min_pos >= 0 else 0
    max_pos = int(max_pos) if max_pos <= motor.max_pos else motor.max_pos

    motor.move_abs(min_pos)
    step_counter = min_pos
    focus_metrics = []
    while step_counter < max_pos:
        image = yield image
        focus_metrics.append(gradientAverage(image))
        motor.move_rel(steps=steps_per_image, dir=Direction.CW, stepdelay=0.001)
        if save_images:
            cv2.imwrite(save_dir + f"{step_counter:03d}.tiff", image)
        step_counter += steps_per_image
        if step_counter > max_pos:
            break
    best_focus_position = int(min_pos + np.argmax(focus_metrics)*steps_per_image)
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

    most_focused, metrics = symmetricZStack(camera=camera, motor=motor, start_point=450, save_images=True)
    print(f"\n=======Most focused image is likely: {most_focused:03d}.tiff=======\n")

    plt.plot(range(0, int(motor.max_pos), steps_per_image), metrics, 'o', markersize=2, color='#2CBDFE')
    plt.title("Focus metric vs. motor position (um)")
    plt.xlabel("Motor position (um)")
    plt.ylabel("Focus metric")
    plt.show()
    led.close()
    motor.close()