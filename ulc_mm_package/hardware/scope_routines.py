from time import perf_counter, sleep
from typing import Union
import numpy as np

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.image_processing.processing_modules import *
from ulc_mm_package.hardware.motorcontroller import Direction, MotorControllerError
import ulc_mm_package.neural_nets.ssaf_constants as ssaf_constants
import ulc_mm_package.image_processing.processing_constants as processing_constants

def focusRoutine(mscope: MalariaScope, lower_bound: int, upper_bound: int, img: np.ndarray=None):
    mscope.motor.move_abs(lower_bound)
    focus_metrics = []
    while mscope.motor.pos < upper_bound:
        img = yield img
        focus_metrics.append(logPowerSpectrumRadialAverageSum(img))
        mscope.motor.move_rel(steps=1, dir=Direction.CW)
    
    best_focus_pos = lower_bound + np.argmax(focus_metrics)
    mscope.motor.move_abs(best_focus_pos)

def singleShotAutofocusRoutine(mscope: MalariaScope, img: np.ndarray):
    """Single shot autofocus routine.

    Use the neural compute stick and the single shot autofocus network
    to determine the number of steps to take to move back into focus.

    This function batches and averages several inferences before making an adjustment. The number
    of images to look at before adjusting the motor is determined by the `AF_BATCH_SIZE` constant in
    `neural_nets/ssaf_constants.py`.

    This function runs until one motor adjustment is completed, then returns.

    Returns
    -------
    int: steps_from_focus
        The number of steps that the motor was moved.
    """

    ssaf_steps_from_focus = []

    while len(ssaf_steps_from_focus) != ssaf_constants.AF_BATCH_SIZE:
        img = yield img
        ssaf_steps_from_focus.append(-int(mscope.autofocus_model(img)[0][0][0]))

    # Once batch is full, get mean and move motor
    steps_from_focus = np.mean(ssaf_steps_from_focus)

    try:
        dir = Direction.CW if steps_from_focus > 0 else Direction.CCW
        mscope.motor.threaded_move_rel(dir=dir, steps=abs(steps_from_focus))
    except MotorControllerError as e:
        # TODO - change to logging
        print(f"Error moving motor after receiving steps from the SSAF model: {e}")

    return steps_from_focus

def continuousSSAFRoutine(mscope: MalariaScope, img: np.ndarray):
    """A wrapper around singleShotAutofocusRoutine which continually accepts images and makes adjustments.
    
    `singleShotAutofocusRoutine` runs a single time before returning. This function is a simple
    continuous wrapper so continuously receive and send images to the autofocus model.
    """

    ssaf = singleShotAutofocusRoutine(mscope, None)
    ssaf.send(None)

    while True:
        img = yield img
        try:
            ssaf.send(img)
        except StopIteration as e:
            steps_taken = e.value
            print(f"SSAF - moved motor: {steps_taken}")
            ssaf = singleShotAutofocusRoutine(mscope, None)
            ssaf.send(None)

def periodicAutofocusWrapper(mscope: MalariaScope, img: np.ndarray):
    """A periodic wrapper around the `continuousSSAFRoutine`.

    This function adds a simple time wrapper around `continuousSSAFRoutine`
    such that inferences and motor adjustments are done every `AF_PERIOD_S`seconds
    (located under `neuraL_nets/ssaf_constants.py`).

    In other words, instead of every image being inferenced and an adjustment being done once
    AF_BATCH_SIZE images have been analyzed, inferences and adjustments are done only if AF_PERIOD_S
    has elapsed since the last adjustment.
    """

    prev_adjustment_time = perf_counter()
    counter = 0
    ssaf_routine = continuousSSAFRoutine(mscope, None)
    ssaf_routine.send(None)

    while True:
        img = yield img
        if perf_counter() - prev_adjustment_time > ssaf_constants.AF_PERIOD_S:
            ssaf_routine.send(img)
            counter += 1
            if counter >= ssaf_constants.AF_BATCH_SIZE:
                counter = 0
                prev_adjustment_time = perf_counter()

def flowControlRoutine(mscope: MalariaScope, target_flowrate: float, img: np.ndarray):
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

    img = yield img
    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(target_flowrate)

    while True:
        img = yield img
        try:
            flow_controller.controlFlow(img)
        except CantReachTargetFlowrate:
            # TODO what to do...
            raise

def fastFlowRoutine(mscope: MalariaScope, img: np.ndarray) -> float:
    """Faster flowrate feedback for initial flow ramp-up.

    See FlowController.fastFlowAdjustment for specifics.

    Usage
    -----
    - Use this routine to do the initial ramp up. Once it hits the target,
    it raises a StopIteration exception and a float number (flowrate)

        fastflow_generator = fastFlowRoutine(mscope, None)
        fastflow_generator.send(None) # need to start generator with a None value
        for img in cam.yieldImages():
            try:
                fastflow_generator.send(img)
            except StopIteration as e:
                flow_val = e.value
        cam.stopAcquisition()
        print(flow_val)

    Then this flow_val can be passed into `flowControlRoutine` on initialization to set
    the flowrate that should be held steady: i.e:

        flow_control = flowControlRoutine(mscope, flow_val, None)
        ...
        ...etc

    Returns
    -------
    float: flow_rate if target achieved

    Exceptions
    ----------
    CantReachTargetFlowrate - raised if the flowrate is above/below where it needs to be, but the syringe can no longer move in the direction necessary
    """

    img = yield img
    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(processing_constants.TARGET_FLOWRATE)

    while True:
        img = yield img
        try:
            flow_val = flow_controller.fastFlowAdjustment(img)
        except CantReachTargetFlowrate:
            raise

        if isinstance(flow_val, float):
            return flow_val

def autobrightnessRoutine(mscope: MalariaScope, img: np.ndarray=None) -> float:
    """Autobrightness routine to set led power.

    Usage
    -----
        ab_generator = autobrightnessRoutine(mscope, None)
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

def find_cells_routine(mscope: MalariaScope, pull_time: float=5, steps_per_image: int=10, img: np.ndarray=None) -> int:
    """Routine to pull pressure, sweep the motor, and assess whether cells are present.

    This routine does the following:
    1. Takes an initial image to check whether for cells (in the case when the blood already flows w/o pressure, and the cells are already in/near focus)
    2. If no cells are found above:
        2a. Pull the syringe maximally for `pull_time` seconds (default: 5s), then reset syringe back to its default (min pressure) position.
        2b. Sweep the motor from bottom to top, taking `steps_per_image (default: 10) per image. Perform a 2D cross-correlation w/ an RBC thumbnail for each image.
        2c. Taking the maximum cross-correlation value from the sweep, check whether it exceeds a threshold (indicative of if cells are present).
        2d. If cells found, return the motor position (integer: 0 - max motor pos).

    3. Repeat steps 2a-2c. `max_attempts` times (default: 3). If the attempts are exhausted, the function returns False.

    In the case when cells are found, the returned motor position should be used to see a local Z-stack (i.e start motor at the returned position and 
    sweep +/- N steps w/ a focus or use the single-shot autofocus model). 

    In the case when no cells are found after the maximum number of attempts, the user should be informed and the run aborted.

    Parameters
    ----------
    mscope: MalariaScope
    pull_time: float
        Sets how long the syringe should be pulled for (at its maximum pressure position) before assessing
        whether cells are present
    img: np.ndarray

    Returns
    -------
    int:
        Value between 0 and motor.max_pos -> Position where cells were found with the highest confidence. This position should be used to seed a local z-stack.

    Exceptions
    ----------
    NoCellsFound:
        Raised if no cells found after max_attempts iterations
    """

    max_attempts = 3 # Maximum number of times to run check for cells routine before aborting
    cell_finder = CellFinder()
    img = yield img
    
    # Initial check for cells, return current motor position if cells found
    cell_finder.add_image(mscope.motor.pos, img)
    try:
        cells_present_motor_pos = cell_finder.get_cells_found_position()
        return cells_present_motor_pos
    except NoCellsFound:
        cell_finder.reset()

    while True:
        """
        1. Pull syringe for 5 seconds
        2. Sweep the motor through the full range of motion and take in images at each step
        3. Assess whether cells are present
        """
        if max_attempts == 0:
            raise NoCellsFound()

        # Pull the syringe maximally for `pull_time` seconds
        start = perf_counter()
        mscope.pneumatic_module.setDutyCycle(mscope.pneumatic_module.getMinDutyCycle())
        while perf_counter() - start < pull_time:
            img = yield img
        mscope.pneumatic_module.setDutyCycle(mscope.pneumatic_module.getMaxDutyCycle())

        # Perform a full focal stack and get the cross-correlation value for each image
        for pos in range(0, mscope.motor.max_pos, steps_per_image):
            mscope.motor.move_abs(pos)
            img = yield img
            cell_finder.add_image(mscope.motor.pos, img)

        # Return the motor position where cells were found
        try:
            cells_present_motor_pos = cell_finder.get_cells_found_position()
            return cells_present_motor_pos
        except NoCellsFound:
            max_attempts -=1
            print("MAX ATTEMPTS LEFT {}".format(max_attempts))