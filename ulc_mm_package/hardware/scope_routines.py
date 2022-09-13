from time import perf_counter
import numpy as np

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.image_processing.processing_modules import *
from ulc_mm_package.hardware.motorcontroller import Direction, MotorControllerError
import ulc_mm_package.neural_nets.ssaf_constants as ssaf_constants
import ulc_mm_package.image_processing.processing_constants as processing_constants

def getFocusBoundsCoroutine(mscope: MalariaScope, img: np.ndarray=None):
    # Move stage to the bottom
    mscope.motor.move_abs(0)

    hist_standard_deviations = []
    steps_per_image = 30

    # Get image, move motor, get standard deviation of the histogram
    while mscope.motor.pos < mscope.motor.max_pos:
        img = yield img
        hist_standard_deviations.append(np.std(np.histogram(img)[0]))
        mscope.motor.move_rel(steps=steps_per_image, dir=Direction.CW)
    
    # Calculate lower and upper bound
    search_window_steps = 30
    x_max = np.argmax(hist_standard_deviations)*steps_per_image
    lower, upper = x_max - search_window_steps, x_max+search_window_steps
    lower = lower if lower >= 0 else 0
    upper = upper if upper < mscope.motor.max_pos else mscope.motor.max_pos

    return lower, upper

def focusCoroutine(mscope: MalariaScope, lower_bound: int, upper_bound: int, img: np.ndarray=None):
    mscope.motor.move_abs(lower_bound)
    focus_metrics = []
    while mscope.motor.pos < upper_bound:
        img = yield img
        focus_metrics.append(logPowerSpectrumRadialAverageSum(img))
        mscope.motor.move_rel(steps=1, dir=Direction.CW)
    
    best_focus_pos = lower_bound + np.argmax(focus_metrics)
    mscope.motor.move_abs(best_focus_pos)

def singleShotAutofocusCoroutine(mscope: MalariaScope, img: np.ndarray):
    """Single shot autofocus coroutine.

    Use the neural compute stick and the single shot autofocus network
    to determine the number of steps to take to move back into focus.

    This function batches and averages several inferences before making an adjustment. The number
    of images to look at before adjusting the motor is determined by the `AF_BATCH_SIZE` constant in
    `neural_nets/ssaf_constants.py`.
    """

    ssaf_steps_from_focus = []

    while True:
        img = yield img
        ssaf_steps_from_focus.append(-int(mscope.autofocus_model(img)[0][0][0]))

        # Once batch is full, get mean and move motor
        if len(ssaf_steps_from_focus) == ssaf_constants.AF_BATCH_SIZE:
            steps_from_focus = np.mean(ssaf_steps_from_focus)
            ssaf_steps_from_focus = []

            try:
                dir = Direction.CW if steps_from_focus > 0 else Direction.CCW
                mscope.motor.threaded_move_rel(dir=dir, steps=abs(steps_from_focus))
            except MotorControllerError as e:
                # TODO - change to logging
                print(f"Error moving motor after receiving steps from the SSAF model: {e}")

def periodicAutofocusWrapper(mscope: MalariaScope, img: np.ndarray):
    """A periodic wrapper around the single shot autofocus coroutine.

    This function adds a simple time wrapper around singleShotAutofocusCoroutine
    such that inferences and motor adjustments are done every `AF_PERIOD_S`seconds
    (located under `neuraL_nets/ssaf_constants.py`).

    In other words, instead of every image
    being inferenced and an adjustment being done once AF_BATCH_SIZE images have been analyzed,
    inferences and adjustments are done only if AF_PERIOD_S has elapsed since the last adjustment.
    """

    prev_adjustment_time = perf_counter()
    counter = 0
    ssaf_coroutine = singleShotAutofocusCoroutine(mscope, None)
    ssaf_coroutine.send(None)

    while True:
        img = yield img
        if perf_counter() - prev_adjustment_time > ssaf_constants.AF_PERIOD_S:
            ssaf_coroutine.send(img)
            counter += 1
            if counter >= ssaf_constants.AF_BATCH_SIZE:
                counter = 0
                prev_adjustment_time = perf_counter()

def flowControlCoroutine(mscope: MalariaScope, target_flowrate: float, img: np.ndarray):
    """Keep the flowrate steady by continuously calculating the flowrate and periodically
    adjusting the syringe position. Need to initially pass in the flowrate to maintain.

    Parameters
    ----------
    mscope: MalariaScope
    target_flowrate: float
        The flowrate value to attempt to keep steady
    img: np.ndarray
        Image to be passed into the FlowController
    """
    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(target_flowrate)

    while True:
        img = yield img
        flow_controller.controlFlow(img)

def fastFlowCoroutine(mscope: MalariaScope, img: np.ndarray) -> float:
    """Faster flowrate feedback for initial flow ramp-up.

    See FlowController.fastFlowAdjustment for specifics.

    Usage
    -----
    - Use this coroutine to do the initial ramp up. Once it hits the target,
    it raises a StopIteration exception and a float number (flowrate)

        fastflow_generator = fastFlowCoroutine(mscope, None)
        fastflow_generator.send(None) # need to start generator with a None value
        for img in cam.yieldImages():
            try:
                fastflow_generator.send(img)
            except StopIteration as e:
                flow_val = e.value
        cam.stopAcquisition()
        print(flow_val)

    Then this flow_val can be passed into `flowControlCoroutine` on initialization to set
    the flowrate that should be held steady: i.e:

        flow_control = flowControlCoroutine(mscope, flow_val, None)
        ...
        ...etc
    """

    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(processing_constants.TARGET_FLOWRATE)

    while True:
        img = yield img
        flow_val = flow_controller.fastFlowAdjustment(img)

        # flow_val is False if target not yet achieved, float otherwise
        if isinstance(flow_val, float):
            # Stops the iterator, returns the flow rate value that was achieved
            return flow_val

def autobrightnessCoroutine(mscope: MalariaScope, img: np.ndarray=None) -> float:
    """Autobrightness routine to set led power.

    Usage
    -----
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