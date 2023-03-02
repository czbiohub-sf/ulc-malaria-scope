import os
import cv2
import numpy as np

from typing import cast
from datetime import datetime

from ulc_mm_package.image_processing.focus_metrics import (
    gradientAverage,
    logPowerSpectrumRadialAverageSum,
)
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT


def takeZStack(camera, motor: DRV8825Nema, steps_per_image: int = 1, save_loc=None):
    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-global_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
            return

    # Re-home the motor to the limit switch
    motor.homed = False
    motor.homeToLimitSwitches()

    step_counter = 0
    max_steps = motor.max_pos
    focus_metrics = []
    for image in camera.yieldImages():
        focus_metrics.append(gradientAverage(image))
        if save_loc is not None:
            cv2.imwrite(save_dir + f"{motor.pos:03d}.png", image)
        motor.move_rel(steps=steps_per_image, dir=Direction.CW)
        step_counter += steps_per_image

        if step_counter > max_steps:
            break

    best_focus_position = np.argmax(focus_metrics) * steps_per_image
    return best_focus_position, focus_metrics


def full_sweep_image_collection(
    motor: DRV8825Nema, steps_per_coarse: int = 10, save_loc: str = None
) -> None:
    """Do a full sweep of the motor range and save images at defined motor position increments.

    Parameters
    ----------
    motor: DRV8825Nema
    steps_per_coarse: int
        Motor increments at which to save images
    save_loc: str
        Path where the folder of images will be saved
    """
    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-global_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
            return
    else:
        print(f"Save location is necessary! Received: {save_loc}")
        return

    # Re-home the motor
    motor.homed = False
    motor.homeToLimitSwitches()
    for _ in range(0, motor.max_pos):
        img = yield
        cv2.imwrite(save_dir + f"{motor.pos:03d}.png", img)
        motor.move_rel(steps=steps_per_coarse, dir=Direction.CW, stepdelay=0.001)
    motor.move_abs(10)


def local_sweep_image_collection(
    motor: DRV8825Nema,
    start_point: int,
    num_steps: int = 30,
    steps_per_image: int = 1,
    num_imgs_per_step: int = 30,
    save_loc: str = None,
) -> None:
    """Sweep through a local vicinity (+/- num_steps from the start_point) and save images.

    Parameters
    ----------
    motor: DRV8825Nema
    start_point: int
        Central position about which the motor will move +/- num_steps steps and save images
    num_steps: int
        Number of images to take above/below the start_point
    num_imgs_per_step: int
        The number of images to save at each motor position
    save_loc: str
        Where the folder of images will be saved
    """

    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-local_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
            return

    # Get motion bounds
    min_pos = int(start_point - num_steps)
    max_pos = int(start_point + num_steps)
    min_pos = int(min_pos) if min_pos >= 0 else 0
    max_pos = int(max_pos) if max_pos <= motor.max_pos else motor.max_pos

    motor.move_abs(min_pos)
    for _ in range(min_pos, max_pos, steps_per_image):
        for i in range(num_imgs_per_step):
            img = yield
            cv2.imwrite(save_dir + f"{motor.pos:03d}_{i:03d}.png", img)
        motor.move_rel(steps=steps_per_image, dir=Direction.CW, stepdelay=0.001)

    # Move the motor back to its original position
    motor.move_abs(start_point)


def takeZStackCoroutine(
    img,
    motor: DRV8825Nema,
    steps_per_coarse: int = 10,
    steps_per_fine: int = 1,
    save_loc=None,
):
    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-global_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
            return

    # Re-home the motor to the limit switch
    motor.homed = False
    motor.homeToLimitSwitches()
    step_counter = 0
    max_steps = motor.max_pos
    focus_metrics = []

    # Do an initial, large-step through from 0-max position
    while step_counter < max_steps:
        img = yield img
        focus_metrics.append(logPowerSpectrumRadialAverageSum(img))
        motor.move_rel(steps=steps_per_coarse, dir=Direction.CW, stepdelay=0.001)
        if save_loc is not None:
            cv2.imwrite(save_dir + f"{motor.pos:03d}.png", img)
        step_counter += steps_per_coarse

    # Do a 1um sweep closer to where the true focus is
    focus_metrics_fine = []
    step_counter = 0
    best_focus_position: int = cast(int, np.argmax(focus_metrics)) * steps_per_coarse
    start = best_focus_position - steps_per_coarse
    end = best_focus_position + steps_per_coarse
    start = start if start >= 0 else 0
    end = end if end <= motor.max_pos else motor.max_pos

    motor.move_abs(start)
    step_counter = start
    while step_counter < end:
        img = yield img
        focus_metrics_fine.append(logPowerSpectrumRadialAverageSum(img))
        motor.move_rel(steps=steps_per_fine, dir=Direction.CW)
        if save_loc is not None:
            cv2.imwrite(save_dir + f"{motor.pos:03d}.png", img)
        step_counter += steps_per_fine
    best_focus_position = (
        start + cast(int, np.argmax(focus_metrics_fine)) * steps_per_fine
    )
    motor.move_abs(best_focus_position)


def symmetricZStack(
    camera,
    motor: DRV8825Nema,
    start_point: int,
    num_steps: int = 20,
    steps_per_image: int = 1,
    save_loc=None,
):
    """Take a symmetric z-stack about a given motor position.

    Parameters
    ----------
    camera: BaslerCamera/AVTCamera
        An instance of the BaslerCamera/AVTCamera object (defined in /hardware/camera.py)
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
    save_loc: string
        Default None - provide a location to save the ZStack images.
    """

    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-local_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
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
        if save_loc is not None:
            cv2.imwrite(save_dir + f"{motor.pos:03d}.png", image)
        step_counter += steps_per_image
        if step_counter > max_pos:
            break
    best_focus_position = int(min_pos + np.argmax(focus_metrics) * steps_per_image)
    return best_focus_position, focus_metrics


def symmetricZStackCoroutine(
    img,
    motor: DRV8825Nema,
    start_point: int,
    num_steps: int = 30,
    steps_per_image: int = 1,
    num_imgs=30,
    save_loc=None,
):
    """The coroutine companion to symmetricZStack"""

    if save_loc is not None:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        save_dir = os.path.join(save_loc, timestamp + "-local_zstack/")
        try:
            os.mkdir(save_dir)
        except Exception as e:
            print(
                f"Could not make directory {save_dir}. Encountered: \n{e}. Cancelling ZStack."
            )
            return

    min_pos = int(start_point - num_steps)
    max_pos = int(start_point + num_steps)
    min_pos = int(min_pos) if min_pos >= 0 else 0
    max_pos = int(max_pos) if max_pos <= motor.max_pos else motor.max_pos

    motor.move_abs(min_pos)
    step_counter = min_pos

    while step_counter < max_pos:
        for i in range(num_imgs):
            img = yield img
            if save_loc is not None:
                cv2.imwrite(save_dir + f"{motor.pos:03d}_{i:03d}.png", img)

        motor.move_rel(steps=steps_per_image, dir=Direction.CW, stepdelay=0.001)
        step_counter += steps_per_image
        if step_counter > max_pos:
            break

    motor.move_abs(start_point)
