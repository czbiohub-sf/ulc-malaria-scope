import numpy as np
from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.image_processing.autobrightness import Autobrightness, AutobrightnessError
from ulc_mm_package.image_processing.focus_metrics import logPowerSpectrumRadialAverageSum

class HardwareError(Exception):
    pass

def runMotorCoroutine(mscope: MalariaScope, start_pos, end_pos):
    if mscope.motor_enabled:
        motor = mscope.motor
    else:
        raise HardwareError("Motor not instantiated.")
    
    # Validate motor start/stop bounds
    start_pos = start_pos if start_pos >= 0 else 0
    end_pos = end_pos if end_pos <= motor.max_pos else motor.max_pos

    motor.move_abs(start_pos)
    num_steps = int(end_pos - start_pos)

    for i in range(num_steps):
        yield
        motor.move_rel()
        
def getFocusBoundsCoroutine(mscope: MalariaScope, img: np.ndarray=None):
    # Move stage to the bottom
    mscope.motor.move_abs(0)

    hist_standard_deviations = []

    # Get image, move motor, get standard deviation of the histogram
    while mscope.motor.pos < mscope.motor.max_pos:
        img = yield img
        hist_standard_deviations.append(np.std(np.histogram(img)[0]))
    
    # Calculate lower and upper bound
    search_window_steps = 30
    x_max = np.argmax(hist_standard_deviations)
    lower, upper = x_max - search_window_steps, x_max+search_window_steps

    return lower, upper

def focusCoroutine(mscope: MalariaScope, lower_bound: int, upper_bound: int, img: np.ndarray=None):
    mscope.motor.move_abs(lower_bound)
    focus_metrics = []
    while mscope.motor.pos < upper_bound:
        img = yield img
        focus_metrics.append(logPowerSpectrumRadialAverageSum(img))
    
    best_focus_pos = lower_bound + np.argmax(focus_metrics)
    mscope.motor.move_abs(best_focus_pos)

def autobrightnessCoroutine(mscope: MalariaScope, img: np.ndarray=None):
    """
    Usage:
        ab_generator = autobrightnessCoroutine(mscope, None)
        ab_generator.send(None) # need to start the generator with a None value

        for img in cam.yieldImages():
            try:
                ab_generator.send(img)
            except StopIteration as e:
                mean_brightness_val = e.value
        cam.stopAcquisition()
        print(mean_brightness_val)

    """
    autobrightness = Autobrightness(mscope.led)
    brightness_achieved = False

    while not brightness_achieved:
        img = yield img
        try:
            brightness_achieved = autobrightness.runAutobrightness(img)
        except AutobrightnessError as e:
            # TODO switch to logging
            print(f"AutobrightnessError encountered: {e}. Stopping autobrightness and continuing...")
            brightness_achieved = True
    # Get the mean image brightness to store in the experiment metadata
    return autobrightness.prev_mean_img_brightness
    

class StateMachine:
    def __init__(self):
        pass

    def state1_metadata_setup(self, mscope: MalariaScope):
        # Open GUI form

        dir = "placeholder from form"
        form_info = "placeholder from form"

        # Set up data storage
        mscope.data_storage.createTopLevelFolder("temp")
        mscope.data_storage.setExperimentMetadata(form_info)

    def state2_sample_setup(self, mscope: MalariaScope):
        # This state requires the camera. Stop acquisition if it is already running.
        mscope.camera.stopAcquisition()
        for img in mscope.camera.yieldImages():
            pass