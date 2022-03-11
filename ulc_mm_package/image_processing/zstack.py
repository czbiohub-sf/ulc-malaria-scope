import os
from datetime import datetime
import cv2
import numpy as np
from time import sleep

from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError
from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera

def radial_average(arr):
    w, h = arr.shape[1], arr.shape[0]
    cx, cy = w // 2, h // 2

    # Create centered radius matrix
    x, y = np.meshgrid(np.arange(w) - cx, np.arange(h) - cy)
    R = np.sqrt(x**2 + y**2)

    # Compute radial mean 
    rm = lambda r: arr[(R >= r - 0.5) & (R <= r + 0.5)].mean()
    r = np.linspace(1, int(np.max(R)))
    radial_mean = np.vectorize(rm)(r)

    return radial_mean

def logPowerSpectrumRadialAverageSum(img):
    power_spectrum = np.fft.fftshift(np.fft.fft2(img))
    log_ps = np.log(np.abs(power_spectrum))
    return np.sum(radial_average(log_ps))

def getLaplacianFocusMetric(img):
    return cv2.Laplacian(img, cv2.CV_64F).var()

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
        focus_metrics.append(getLaplacianFocusMetric(image))
        if save_images:
            cv2.imwrite(save_dir + f"{step_counter:03d}.jpg", image)
        motor.move_rel(steps=steps_per_image, dir=Direction.CW)
        sleep(delay)
        step_counter += steps_per_image

        if step_counter >= max_steps:
            break

    best_focus_position = np.argmax(focus_metrics)*steps_per_image
    return best_focus_position, focus_metrics

if __name__ == "__main__":
    print("===Initiating z-stack.===\n")

    # Instantiate camera
    try:
        camera = ULCMM_Camera()
    except CameraError as e:
        print(f"Could not instantiate camera, encountered: \n{e}")

    # Instantiate motor
    try:
        motor = DRV8825Nema(steptype="Half")
        motor.homeToLimitSwitches()
    except MotorControllerError as e:
        print(f"Motorcontroller error, encountered: \n{e}")

    most_focused, metrics = takeZStack(camera=camera, motor=motor, steps_per_image=10, save_images=True)
    print(f"Most focused image is likely: {most_focused:03d}.jpg")
    motor.close()