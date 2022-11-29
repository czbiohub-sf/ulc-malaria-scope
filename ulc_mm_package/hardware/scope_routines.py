from typing import List, Tuple, Optional, Sequence, Generator, Union
from time import perf_counter
import numpy as np

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.image_processing.processing_modules import *
from ulc_mm_package.hardware.motorcontroller import Direction, MotorControllerError
import ulc_mm_package.neural_nets.neural_network_constants as nn_constants
import ulc_mm_package.image_processing.processing_constants as processing_constants


def focusRoutine(
    mscope: MalariaScope, lower_bound: int, upper_bound: int, img: np.ndarray = None
):
    mscope.motor.move_abs(lower_bound)
    focus_metrics = []
    while mscope.motor.pos < upper_bound:
        img = yield img
        focus_metrics.append(logPowerSpectrumRadialAverageSum(img))
        mscope.motor.move_rel(steps=1, dir=Direction.CW)

    best_focus_pos = lower_bound + np.argmax(focus_metrics)
    mscope.motor.move_abs(best_focus_pos)


def singleShotAutofocusRoutine(mscope: MalariaScope, steps_from_focus: float) -> None:
    """Single shot autofocus routine.

    Takes in the predicted number of steps from focus and adjusts the motor position to try
    to get the stage back into focus. In practice, it moves -int(steps_from_focus).

    Parameters
    ----------
    List[np.ndarray]:
        Array of images (np.ndarray)
    """
    try:
        # needs to move in the opposite direction of `steps_from_focus` to get to focus! Therefore
        # if we are below focus, move CW, and vice versa.
        dir = Direction.CW if steps_from_focus < 0 else Direction.CCW
        mscope.motor.move_rel(dir=dir, steps=steps_from_focus)
    except MotorControllerError as e:
        raise e


def continuousSSAFRoutine(mscope: MalariaScope) -> Generator[Union[None, int], np.ndarray, None]:
    """A wrapper around singleShotAutofocusRoutine which continually accepts images and makes motor position adjustments."""

    images_sent: int = 0
    steps_from_focus: Optional[float] = None

    while True:
        img: np.ndarray = yield steps_from_focus

        mscope.autofocus_model.asyn(img)
        images_sent += 1

        steps_from_focus = None

        if images_sent == nn_constants.AF_BATCH_SIZE:
            async_results = mscope.autofocus_model.get_asyn_results(timeout=None)
            steps_from_focus = np.mean(v.result for v in async_results)
            singleShotAutofocusRoutine(mscope, steps_from_focus)
            images_sent = 0


def periodicAutofocusWrapper(
    mscope: MalariaScope
) -> Generator[Union[None, int], np.ndarray, None]:
    """A periodic wrapper around the `continuousSSAFRoutine`.

    This function adds a simple time wrapper around `continuousSSAFRoutine`
    such that inferences (in batches) and motor adjustments are done every `AF_PERIOD_S`seconds.

    When not making an adjustment, this Generator yields None. After an adjustment has been completed, the next
    `.send(img)` will yield a float value.

    The caller of this function should have an isinstance(float) or isinstance(None) check to the output received.

    Returns
    -------
    None:
        In between periods, images are not being sent to SSAF.
    int:
        Number of motor steps taken, returned after a full batch of images have been sent once
        AF_PERIOD_S has elapsed since the last adjustment.
    """
    counter: int = 0
    steps_from_focus: Optional[float] = None
    prev_adjustment_time = perf_counter()
    ssaf_routine = continuousSSAFRoutine(mscope)
    ssaf_routine.send(None)

    while True:
        img: np.ndarray = yield steps_from_focus
        if perf_counter() - prev_adjustment_time > nn_constants.AF_PERIOD_S:
            steps_from_focus = ssaf_routine.send(img)
            counter += 1
            if counter >= nn_constants.AF_BATCH_SIZE:
                counter = 0
                prev_adjustment_time = perf_counter()


def count_parasitemia(
    mscope: MalariaScope, img: np.ndarray, counts: Optional[Sequence[int]] = None
) -> List[Tuple[int, Tuple[float, ...]]]:
    results = mscope.cell_diagnosis_model.get_asyn_results()
    mscope.cell_diagnosis_model(img, counts)
    return results


def flowControlRoutine(
    mscope: MalariaScope, target_flowrate: float, img: np.ndarray
) -> Generator[float, np.ndarray, None]:
    """Keep the flowrate steady by continuously calculating the flowrate and periodically
    adjusting the syringe position. Need to initially pass in the flowrate to maintain.

    Parameters
    ----------
    mscope: MalariaScope
    target_flowrate: float
        The flowrate value to attempt to keep steady
    img: np.ndarray
        Image to be passed into the FlowController

    Exceptions
    ----------
    CantReachTargetFlowrate:
        Raised when the syringe is already at its maximally extended position but the flowrate
        is still outside the tolerance band.
    """

    img, timestamp = yield
    flow_val = 0
    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(target_flowrate)

    while True:
        img, timestamp = yield flow_val
        try:
            flow_val = flow_controller.controlFlow(img, timestamp)
        except CantReachTargetFlowrate:
            raise


def fastFlowRoutine(
    mscope: MalariaScope,
    img: np.ndarray,
    target_flowrate: float = processing_constants.FLOWRATE.FAST.value,
) -> Generator[float, np.ndarray, float]:
    """Faster flowrate feedback for initial flow ramp-up.

    See FlowController.fastFlowAdjustment for specifics.

    Usage
    -----
    - Use this routine to do the initial ramp up. Once it hits the target,
    it raises a StopIteration exception and a float number (flowrate) is returned via the exception (e.value)

        fastflow_generator = fastFlowRoutine(mscope, None)
        fastflow_generator.send(None) # need to start generator with a None value
        for img in cam.yieldImages():
            try:
                flow_val = fastflow_generator.send(img)
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
    CantReachTargetFlowrate:
        Raised when the syringe is already at its maximally extended position but the flowrate
        is still outside the tolerance band.
    """

    flow_val = 0
    img, timestamp = yield
    h, w = img.shape
    flow_controller = FlowController(mscope.pneumatic_module, h, w)
    flow_controller.setTargetFlowrate(target_flowrate)

    while True:
        img, timestamp = yield flow_val
        try:
            flow_val, flow_error = flow_controller.fastFlowAdjustment(img, timestamp)
        except CantReachTargetFlowrate:
            raise

        if flow_error == 0:
            return flow_val


def autobrightnessRoutine(mscope: MalariaScope, img: np.ndarray = None) -> float:
    """Autobrightness routine to set led power.

    Parameters
    ----------
    mscope: MalariaScope
    img: np.ndarray

    Returns
    -------
    float: Mean autobrightness value

    Exceptions
    ----------
    BrightnessTargetNotAchieved:
        The target was not achieved BUT is still sufficiently bright enough
        to proceed with a run. THe mean pixel brightness value can be accessed
        by:
            try:
                ...
            exception BrightTargetNotAchieved as e:
                val = e.value

    BrightnessCriticallyLow:
        The targeg was not achieved and the brightness is too low to continue
        with the run. The mean pixel brightness value can be accessed by:
            try:
                ...
            exception BrightTargetNotAchieved as e:
                val = e.value

    Usage
    -----
        ab_generator = autobrightnessRoutine(mscope, None)
        ab_generator.send(None) # need to start the generator with a None value

        for img in cam.yieldImages():
            try:
                ab_generator.send(img)
            except StopIteration as e:
                mean_brightness_val = e.value
            except BrightnessTargetNotAchieved:
                Brightness not at target but still workable
            except BrightnessCriticallyLow:

        cam.stopAcquisition()
        print(mean_brightness_val)
    """

    autobrightness = Autobrightness(mscope.led)
    brightness_achieved = False

    while not brightness_achieved:
        img = yield img
        try:
            brightness_achieved = autobrightness.runAutobrightness(img)
        except BrightnessTargetNotAchieved as e:
            # TODO switch to logging
            print(f"Autobrightness routine exception : {e}")
            raise
        except BrightnessCriticallyLow as e:
            # TODO switch to logging
            print(f"Autobrightness routine exception : {e}")
            raise

    # Get the mean image brightness to store in the experiment metadata
    return autobrightness.prev_mean_img_brightness


def find_cells_routine(
    mscope: MalariaScope,
    pull_time: float = 5,
    steps_per_image: int = 10,
    img: np.ndarray = None,
) -> int:
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

    max_attempts = (
        3  # Maximum number of times to run check for cells routine before aborting
    )
    cell_finder = CellFinder()
    img = yield

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
            img = yield
        mscope.pneumatic_module.setDutyCycle(mscope.pneumatic_module.getMaxDutyCycle())

        # Perform a full focal stack and get the cross-correlation value for each image
        for pos in range(0, mscope.motor.max_pos, steps_per_image):
            mscope.motor.move_abs(pos)
            img = yield
            cell_finder.add_image(mscope.motor.pos, img)

        # Return the motor position where cells were found
        try:
            cells_present_motor_pos = cell_finder.get_cells_found_position()
            return cells_present_motor_pos
        except NoCellsFound:
            max_attempts -= 1
            print("MAX ATTEMPTS LEFT {}".format(max_attempts))


def cell_density_routine(
    img: np.ndarray,
):
    prev_time = perf_counter()
    prev_measurements = np.asarray(
        [100] * processing_constants.CELL_DENSITY_HISTORY_LEN
    )
    idx = 0

    while True:
        if (
            perf_counter() - prev_time
            >= processing_constants.CELL_DENSITY_CHECK_PERIOD_S
        ):
            img = yield prev_measurements[(idx - 1) % 10]
            _, prev_measurements[idx] = isDensitySufficient(img)
            idx = (idx + 1) % len(prev_measurements)

            if np.all(prev_measurements < processing_constants.MIN_CELL_COUNT):
                raise LowDensity

            prev_time = perf_counter()
