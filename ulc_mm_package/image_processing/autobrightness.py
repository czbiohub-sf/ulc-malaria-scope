import enum
import numpy as np
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT

TOP_PERC_TARGET_VAL = 245
TOP_PERC = 0.03
TOL = 0.01

class AB(enum.Enum):
    TOO_HIGH = 1
    JUST_RIGHT = 0
    TOO_LOW = -1

class AutobrightnessError(Exception):
    """Base class for catching Autobrightness errors."""
    
    def __init__(self, msg: str):
        super().__init__(f"{msg}")

def assessBrightness(img: np.ndarray, top_perc: float):
    """Returns the mean value of the top N pixels in a given image.

    Parameters
    ----------
    img: np.ndarray
        The input image whose brightness will be assessed
    top_perc: float
        A float number between 0-1 which determines the number of pixels to assess (i.e the top X% of pixels)
    """

    top_n_perc = top_perc * img.size
    mean_brightness = np.mean(img.flatten()[np.argpartition(img.flatten(), -int(top_n_perc))[-int(top_n_perc):]])
    return mean_brightness

def adjustBrightness(img: np.ndarray, target_pixel_val: int, led: LED_TPS5420TDDCT, step_size_perc: float):
    """Adjusts the LED's duty cycle to achieve the target brightness"""

    current_led_pwm_perc = led._convertPWMValToDutyCyclePerc(led.pwm_duty_cycle)
    current_brightness = assessBrightness(img, TOP_PERC)
    diff = target_pixel_val - current_brightness
    diff = diff if abs(diff/np.iinfo(str(img.dtype)).max) >= TOL else 0

    led.turnOn()
    if diff > 0:
        # Increase brightness
        step = current_led_pwm_perc + step_size_perc
        step = step if step <= 1.0 else 1.0
        led.setDutyCycle(step)
        return AB.TOO_LOW

    elif diff < 0:
        # Decrease brightness 
        step = current_led_pwm_perc - step_size_perc
        step = step if step >= 0.0 else 0.0
        led.setDutyCycle(step)
        return AB.TOO_HIGH
    else:
        # Brightness achieved within tol 
        return AB.JUST_RIGHT

class Autobrightness():
    def __init__(self, led: LED_TPS5420TDDCT, target_pixel_val: int=TOP_PERC_TARGET_VAL, step_size_perc: float=0.01):
        self.prev_brightness_enum = None
        self.target_pixel_val = target_pixel_val
        self.led = led
        self.step_size_perc = step_size_perc
        self.default_step_size_perc = step_size_perc
        self.timeout_steps = 100
        self.step_counter = 0
    
    def runAutobrightness(self, img: np.ndarray):
        curr_brightness_enum = adjustBrightness(img, self.target_pixel_val, self.led, self.step_size_perc)
        if not self.prev_brightness_enum == None:
            if self.prev_brightness_enum != curr_brightness_enum:
                self.step_size_perc /= 2

        self.prev_brightness_enum = curr_brightness_enum
        self.step_counter += 1

        if self.step_counter >= self.timeout_steps:
            self.led.setDutyCycle(0)
            raise AutobrightnessError(f"Unable to achieve the target brightness within {self.timeout_steps} steps. The exposure may be too low (and the target pixel value too high), or there may be an issue with the LED.") 

        if curr_brightness_enum == AB.JUST_RIGHT:
            return True
        else:
            return False

    def reset(self):
        self.prev_brightness_enum = None
        self.step_size_perc = self.default_step_size_perc
        self.step_counter = 0