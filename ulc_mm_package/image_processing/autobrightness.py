import enum
from typing import Union
import numpy as np
import cv2

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
            f"Unable to achieve the target brightness. The exposure may be too low (and the target pixel value too high) ",
            f"or there may be an issue with the LED. Final mean pixel value: {brightness_val}. ",
            f"The brightness value is still above the minimum acceptable value ",
            f"of ({MIN_ACCEPTABLE_MEAN_BRIGHTNESS}).",
        )
        self.value = brightness_val
        super().__init__(f"{msg}")


class BrightnessCriticallyLow(AutobrightnessError):
    def __init__(self, brightness_val):
        msg = f""
        self.value = brightness_val
        super().__init__(f"{msg}")


def downsample_image(img: np.ndarray, scale_factor: int) -> np.ndarray:
    """Downsamples an image by `scale_factor`"""

    h, w = img.shape
    return cv2.resize(img, (w // scale_factor, h // scale_factor))


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
) -> Union[AB, float]:
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


class Autobrightness:
    def __init__(
        self,
        led: LED_TPS5420TDDCT,
        target_pixel_val: int = TOP_PERC_TARGET_VAL,
        step_size_perc: float = 0.01,
    ):
        self.prev_brightness_enum = None
        self.prev_mean_img_brightness = None
        self.target_pixel_val = target_pixel_val
        self.led = led
        self.step_size_perc = step_size_perc
        self.default_step_size_perc = step_size_perc
        self.timeout_steps = 100
        self.step_counter = 0

    def runAutobrightness(self, img: np.ndarray) -> bool:
        curr_brightness_enum, curr_mean_brightness_val = adjustBrightness(
            img, self.target_pixel_val, self.led, self.step_size_perc
        )
        if not self.prev_brightness_enum == None:
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

    def reset(self):
        self.prev_brightness_enum = None
        self.step_size_perc = self.default_step_size_perc
        self.step_counter = 0
