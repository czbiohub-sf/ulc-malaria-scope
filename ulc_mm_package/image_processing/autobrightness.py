import enum
import pickle
from typing import Tuple, Optional

import numpy as np

from ulc_mm_package.image_processing.focus_metrics import downsample_image
from ulc_mm_package.image_processing.processing_constants import (
    TOP_PERC_TARGET_VAL,
    TOP_PERC,
    TOL,
    MIN_ACCEPTABLE_MEAN_BRIGHTNESS,
)
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT


class AB(enum.Enum):
    TOO_HIGH = 1
    JUST_RIGHT = 0
    TOO_LOW = -1


class AutobrightnessError(Exception):
    """Base class for catching Autobrightness errors."""

    def __init__(self, msg: str):
        super().__init__(f"{msg}")


class BrightnessTargetNotAchieved(AutobrightnessError):
    """Raised when target not achieved, but still sufficiently bright for a run to proceed."""

    def __init__(self, brightness_val):
        msg = (
            f"Unable to achieve the target brightness. The exposure may be too low (and the target pixel value too high) "
            f"or there may be an issue with the LED. Final mean pixel value: {brightness_val}. "
            f"The brightness value is still above the minimum acceptable value "
            f"of ({MIN_ACCEPTABLE_MEAN_BRIGHTNESS})."
        )
        self.value = brightness_val
        super().__init__(f"{msg}")


class BrightnessCriticallyLow(AutobrightnessError):
    def __init__(self, brightness_val):
        msg = ""
        self.value = brightness_val
        super().__init__(f"{msg}")


class LEDNoPower(AutobrightnessError):
    """Raised when it appears as if the LED is not working."""

    def __init__(self, mean_off_img: float, off_img_sd: float, mean_on_img: float):
        msg = (
            f"The LED does not seem to be working. Mean pixel value w/ LED off is = {mean_off_img:.2f}. "
            f"Mean pixel value w/ LED on = {mean_on_img:.2f}. "
            f"SD of image w/ LED off is = {off_img_sd:.2f}. "
            f"The LED may be dead or a cable may have become disconnected. "
        )

        super().__init__(f"{msg}")


def assessBrightness(
    img: np.ndarray, top_perc: float, downsample_factor: int = 20
) -> float:
    """Returns the mean value of the top N pixels in a given image.

    Parameters
    ----------
    img: np.ndarray
        The input image whose brightness will be assessed
    top_perc: float
        A float number between 0-1 which determines the number of pixels to assess (i.e the top X% of pixels)
    """

    img = downsample_image(img, downsample_factor)
    top_n_perc = top_perc * img.size
    mean_brightness = np.mean(
        img.flatten()[
            np.argpartition(img.flatten(), -int(top_n_perc))[-int(top_n_perc) :]
        ]
    )
    return mean_brightness


def adjustBrightness(
    img: np.ndarray, target_pixel_val: int, led: LED_TPS5420TDDCT, step_size_perc: float
) -> Tuple[AB, float]:
    """Adjusts the LED's duty cycle to achieve the target brightness.

    Returns
    -------
    Enum:
        AB custom enum specifying where the brightness is relative to the target (below/above/on target)
    float:
        Mean image-pixel value
    """
    current_led_pwm_perc = led.pwm_duty_cycle
    current_brightness = assessBrightness(img, TOP_PERC)
    diff = target_pixel_val - current_brightness
    diff = diff if abs(diff / np.iinfo(str(img.dtype)).max) >= TOL else 0

    led.turnOn()
    if diff > 0:
        # Increase brightness
        step = current_led_pwm_perc + step_size_perc
        step = step if step <= 1.0 else 1.0
        led.setDutyCycle(step)
        return AB.TOO_LOW, current_brightness

    elif diff < 0:
        # Decrease brightness
        step = current_led_pwm_perc - step_size_perc
        step = step if step >= 0.0 else 0.0
        led.setDutyCycle(step)
        return AB.TOO_HIGH, current_brightness
    else:
        # Brightness achieved within tol
        return AB.JUST_RIGHT, current_brightness


def checkLedWorking(
    img_led_off: np.ndarray, img_led_on: np.ndarray, n_devs: int = 3
) -> float:
    """Check whether the led is on by comparing an image with the LED off vs. one with the LED on.

    Parameters
    ----------
    img_led_off: np.ndarray
        Image taken when the led is completely off
    img_led_on: np.ndarray
        Image taken when the led is on (ideally fully on so that we don't get a false negative due to the LED being dim)
    n_devs: int=3
        Number of standard deviations above the "off" image's mean that the "on" image needs to be to deem the LED as working.

    Returns
    -------
    float:
        The difference between mean pixel value when the led is on and

    Exceptions
    ----------
    LEDNoPower:
        An exception raised when `the difference between the mean pixel value when the LED is on is less than
        `n_devs` standard deviations above the mean of the image taken with the led off.

    """
    sd_off: float = np.std(img_led_off)
    mean_off: float = np.mean(img_led_off)
    mean_on: float = np.mean(img_led_on)
    diff = mean_on - (mean_off + n_devs * sd_off)
    if diff >= 0:
        return mean_on - mean_off
    else:
        raise LEDNoPower(mean_off, sd_off, mean_on)


class Autobrightness:
    def __init__(
        self,
        led: LED_TPS5420TDDCT,
        target_pixel_val: int = TOP_PERC_TARGET_VAL,
        step_size_perc: float = 0.01,
        kp: float = 0.001,
        ki: float = 0.01,
        kd: float = 0.01,
    ):
        self.prev_brightness_enum: Optional[AB] = None
        self.prev_mean_img_brightness: Optional[float] = None
        self.target_pixel_val: int = target_pixel_val
        self.led = led
        self.step_size_perc = step_size_perc
        self.default_step_size_perc = step_size_perc
        self.timeout_steps = 200
        self.step_counter = 0

        # PID constants
        self.kp = kp
        self.ki = ki
        self.kd = kd

        self.prev_error = None
        self.intergral_error = 0

    def runAutobrightness(self, img: np.ndarray) -> bool:
        curr_brightness_enum, curr_mean_brightness_val = adjustBrightness(
            img, self.target_pixel_val, self.led, self.step_size_perc
        )

        if self.prev_brightness_enum is not None:
            if self.prev_brightness_enum != curr_brightness_enum:
                self.step_size_perc /= 2

        self.prev_brightness_enum = curr_brightness_enum
        self.prev_mean_img_brightness = curr_mean_brightness_val
        self.step_counter += 1

        if self.step_counter >= self.timeout_steps:
            if self.prev_mean_img_brightness >= MIN_ACCEPTABLE_MEAN_BRIGHTNESS:
                raise BrightnessTargetNotAchieved(self.prev_mean_img_brightness)
            else:
                raise BrightnessCriticallyLow(self.prev_mean_img_brightness)

        if curr_brightness_enum == AB.JUST_RIGHT:
            return True
        else:
            return False

    def autobrightness_pid_control(self, img: np.ndarray):
        img_brightness = assessBrightness(img, TOP_PERC)
        self.prev_mean_img_brightness = img_brightness
        error = self.target_pixel_val - img_brightness

        self.intergral_error += error

        if self.prev_error is None:
            self.prev_error = error
            derivative_error = 0
        else:
            # Implicit dt = 1
            derivative_error = error - self.prev_error
        self.prev_error = error

        correction = (
            self.kp
            * error
            # + (self.ki * self.intergral_error)
            # + (self.kd * derivative_error)
        )

        current_led_pwm_perc = self.led.pwm_duty_cycle
        new_led_pwm_perc = current_led_pwm_perc + correction
        new_led_pwm_perc = new_led_pwm_perc if new_led_pwm_perc <= 1.0 else 1.0
        new_led_pwm_perc = new_led_pwm_perc if new_led_pwm_perc >= 0.0 else 0.0
        self.led.setDutyCycle(new_led_pwm_perc)

    def reset(self):
        self.prev_brightness_enum = None
        self.step_size_perc = self.default_step_size_perc
        self.step_counter = 0

        self.prev_error = None
        self.intergral_error = 0
