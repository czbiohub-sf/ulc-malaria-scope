import logging

from functools import wraps
from time import perf_counter, sleep
from typing import Any, Callable, List, Tuple, Optional, Sequence, Generator

import numpy as np

from ulc_mm_package.hardware.scope import MalariaScope

from ulc_mm_package.image_processing.autobrightness import (
    Autobrightness,
    BrightnessTargetNotAchieved,
    BrightnessCriticallyLow,
    checkLedWorking,
)
from ulc_mm_package.image_processing.flow_control import FlowController

from ulc_mm_package.image_processing.cell_finder import (
    CellFinder,
    NoCellsFound,
    LowDensity,
)
from ulc_mm_package.hardware.pneumatic_module import PressureLeak, PressureSensorBusy
from ulc_mm_package.hardware.motorcontroller import Direction, MotorControllerError
from ulc_mm_package.hardware.hardware_constants import (
    MIN_PRESSURE_DIFF,
    FOCUS_EWMA_ALPHA,
)
from ulc_mm_package.image_processing.classic_focus import OOF, ClassicImageFocus
from ulc_mm_package.neural_nets.NCSModel import AsyncInferenceResult
from ulc_mm_package.image_processing.ewma_filtering_utils import EWMAFiltering

import ulc_mm_package.neural_nets.neural_network_constants as nn_constants
import ulc_mm_package.image_processing.processing_constants as processing_constants


def init_generator(
    generator: Callable[..., Generator[Any, Any, Any]]
) -> Callable[..., Generator[Any, Any, Any]]:
    @wraps(generator)
    def call(*a, **k):
        g = generator(*a, **k)
        # advance just-started generator without requiring generator 'send' type to be optional
        next(g)
        return g

    return call


class Routines:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def singleShotAutofocusRoutine(
        self, mscope: MalariaScope, img_arr: List[np.ndarray]
    ) -> int:
        """Single shot autofocus routine.

        Takes in an array of images (number based on AF_BATCH_SIZE), runs an inference
        using the SSAF model, averages the results, and adjusts the motor position by that step value.

        Parameters
        ----------
        List[np.ndarray]:
            Array of images (np.ndarray)

        Returns
        -------
        int: steps_from_focus
            The number of steps that the motor was moved.
        """

        ssaf_steps_from_focus = mscope.autofocus_model(img_arr)
        steps_to_move = -round(np.mean(ssaf_steps_from_focus))

        try:
            dir = Direction.CW if steps_to_move > 0 else Direction.CCW
            mscope.motor.threaded_move_rel(dir=dir, steps=abs(steps_to_move))
        except MotorControllerError as e:
            raise e

        return steps_to_move

    @init_generator
    def periodicAutofocusWrapper(
        self, mscope: MalariaScope
    ) -> Generator[
        Tuple[Optional[float], Optional[float], Optional[bool]], np.ndarray, None
    ]:
        """Periodic autofocus calculations with EWMA filtering

        This function adds a simple time wrapper around the autofocus model and EWMA filter
        such that inferences and motor adjustments are done every `AF_PERIOD_NUM' frames.

        When not making an adjustment, this Generator yields None. After an adjustment has been completed, the next
        `.send(img)` will yield a float value.

        The caller of this function should have an isinstance(float) or isinstance(None) check to the output received.

        Returns
        -------
        None:
            In between periods, images are not being sent to SSAF.
        int:
            Number of motor steps taken, returned after an image has been sent once
            AF_PERIOD_NUM frames have elapsed since the last adjustment.
        """

        filtered_error = 0.0
        img_counter = 0
        throttle_counter = 0
        move_counter = 0

        adjusted = None
        steps_from_focus = None

        # reset the autofocus in case we got here fm. classic focus restarting us to this point.
        # we want to make sure we don't pollute the new PSSAF w/ old data
        mscope.autofocus_model.reset(wait_for_jobs=False)

        ssaf_filter = EWMAFiltering(FOCUS_EWMA_ALPHA)
        ssaf_filter.set_init_val(0)

        ssaf_period_num = ssaf_filter.get_adjustment_period_ewma()
        self.logger.info(
            f"Minimum SSAF adjustment period = {ssaf_period_num} measurements"
        )

        while True:
            throttle_counter += 1
            if throttle_counter >= nn_constants.AF_PERIOD_NUM:
                img_counter += 1
                img = yield steps_from_focus, filtered_error, adjusted
                adjusted = False

                # if mscope.autofocus_model._executor._work_queue.full(), this will block
                # until an element is removed from the queue
                # TODO watch performance, if blocking a lot then we must subclass ThreadPoolExecutor and change
                # https://github.com/python/cpython/blob/a712c5f42d5904e1a1cdaf11bd1f05852cfdd830/Lib/concurrent/futures/thread.py#L175
                # to `put_nowait`
                mscope.autofocus_model.asyn(img, img_counter)
                results = mscope.autofocus_model.get_asyn_results(timeout=0.005) or []

                for res in sorted(results, key=lambda res: res.id):
                    move_counter += 1

                    steps_from_focus = res.result.item()
                    filtered_error = ssaf_filter.update_and_get_val(steps_from_focus)

                throttle_counter = 0

                if (
                    move_counter >= ssaf_period_num
                    and abs(filtered_error) > nn_constants.AF_THRESHOLD
                ):
                    steps_to_move = -round(filtered_error)
                    self.logger.info(
                        f"Adjusted focus by {steps_to_move:.2f} steps after {move_counter} measurements"
                    )
                    move_counter = 0
                    adjusted = True

                    try:
                        dir = Direction.CW if steps_to_move > 0 else Direction.CCW
                        mscope.motor.threaded_move_rel(
                            dir=dir, steps=abs(steps_to_move)
                        )
                    except MotorControllerError as e:
                        raise e
            else:
                _ = yield None, None, None

    @init_generator
    def classic_focus_routine(
        self, init_img: np.ndarray
    ) -> Generator[float, np.ndarray, np.ndarray]:
        img_counter = 0
        self.classic_focus = ClassicImageFocus(init_img)

        while True:
            img = yield self.classic_focus.curr_ratio
            img_counter += 1

            if img_counter % processing_constants.CLASSIC_FOCUS_FRAME_THROTTLE == 0:
                try:
                    self.classic_focus.add_image(img)
                except OOF:
                    raise

    def count_parasitemia(
        self,
        mscope: MalariaScope,
        img: np.ndarray,
        counts: Optional[Sequence[int]] = None,
    ) -> List[AsyncInferenceResult]:
        results = mscope.cell_diagnosis_model.get_asyn_results()
        mscope.cell_diagnosis_model(img, counts)
        return results

    @init_generator
    def count_parasitemia_periodic_wrapper(
        self,
        mscope: MalariaScope,
    ) -> Generator[
        List[AsyncInferenceResult],
        Tuple[np.ndarray, Optional[int]],
        None,
    ]:
        while True:
            img, counts = yield mscope.cell_diagnosis_model.get_asyn_results()
            mscope.cell_diagnosis_model(img, counts)

    @init_generator
    def flow_control_routine(
        self, mscope: MalariaScope, target_flowrate: float, fast_flow: bool = False
    ) -> Generator[Tuple[Optional[float], Optional[bool]], np.ndarray, Optional[float]]:
        """Keep the flowrate steady by continuously calculating the flowrate and periodically
        adjusting the syringe position. Need to initially pass in the flowrate to maintain.

        If fast_flow is set to true, flow control feedback will run more rapidly (and with more noise) to attempt
        to reach the target flow rate sooner.

        Parameters
        ----------
        mscope: MalariaScope
        target_flowrate: float
            The flowrate value to attempt to keep steady
        fast_flow: bool
            Toggle whether to do faster feedback loop to reach the target flowrate sooner

        Exceptions
        ----------
        CantReachTargetFlowrate:
            Raised when the syringe is already at its maximally extended position but the flowrate
            is still outside the tolerance band.
        """

        flow_val: Optional[float] = None
        syringe_can_move: Optional[bool] = None
        prev_can_move: bool = True
        mscope.flow_controller.reset()
        flow_controller = mscope.flow_controller
        flow_controller.set_target_flowrate(target_flowrate)
        if fast_flow:
            flow_controller.set_alpha(
                processing_constants.FLOW_CONTROL_EWMA_ALPHA * 2
            )  # Double the alpha, ~halve the half life

        while True:
            img, timestamp = yield flow_val, syringe_can_move

            # Get the flow value, difference from target flow, and whether the syringe can move
            # If syringe_can_move is False, a CantReachTargetFlowrate exception was raised, meaning
            # the syringe can't move further and the target flowrate has not been reached.
            prev_can_move = (
                syringe_can_move if syringe_can_move is not None else prev_can_move
            )
            flow_val, flow_error, syringe_can_move = flow_controller.control_flow(
                img, timestamp
            )
            if (prev_can_move is True) and (syringe_can_move is False):
                # This is here so that we don't flood the logger with the same message
                self.logger.error(
                    "Can't reach target flowrate. Syringe at end of travel."
                )

            if fast_flow:
                if flow_error is not None:
                    if flow_error == 0:
                        return flow_val

    @init_generator
    def autobrightnessRoutine(
        self, mscope: MalariaScope
    ) -> Generator[None, np.ndarray, float]:
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
            The target was not achieved and the brightness is too low to continue
            with the run. The mean pixel brightness value can be accessed by:
                try:
                    ...
                exception BrightTargetNotAchieved as e:
                    val = e.value

        LEDNoPower:
            The initial check for LED functionality (comparing an image taken with the LED off vs. LED at full power)
            failed. This means that the LED is likely not working (perhaps a cable is loose or the LED is dead).

        Usage
        -----
            ab_generator = autobrightnessRoutine(mscope, None)

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

        # First set the LED off and acquire an image
        mscope.led.turnOff()
        sleep(0.25)
        img_off = yield

        # Turn the led on to max and acquire an image
        mscope.led.turnOn()
        mscope.led.setDutyCycle(1)
        sleep(0.25)
        img_on = yield
        checkLedWorking(img_off, img_on, n_devs=3)

        # Turn the led back to 0
        sleep(0.25)
        mscope.led.setDutyCycle(0)

        # Run autobrightness
        while not brightness_achieved:
            img = yield
            try:
                brightness_achieved = autobrightness.runAutobrightness(img)
            except BrightnessTargetNotAchieved:
                raise
            except BrightnessCriticallyLow:
                raise

        # Get the mean image brightness to store in the experiment metadata.
        # Since brightness was achieved, we know that this is now a float
        # instead of an Optional[float].
        brightness = autobrightness.prev_mean_img_brightness

        assert brightness is not None, "not possible"
        return brightness

    @init_generator
    def periodic_autobrightness_routine(
        self, mscope: MalariaScope
    ) -> Generator[Optional[float], np.ndarray, None]:
        """
        This routine is a wrapper around the autobrightness routine that will run at a set periodicity,
        defined by the constant CONTINUOUS_AB_PERIOD_NUM, during an acquisition.

        Parameters
        ----------
        mscope: MalariaScope
        """

        autobrightness = Autobrightness(mscope.led)
        curr_img_brightness: Optional[float] = None

        counter = 0
        while True:
            img = yield curr_img_brightness
            counter += 1
            if counter >= processing_constants.PERIODIC_AB_PERIOD_NUM_FRAMES:
                autobrightness.autobrightness_pid_control(img)
                curr_img_brightness = autobrightness.prev_mean_img_brightness

    def checkPressureDifference(
        self, mscope: MalariaScope, ambient_pressure: float
    ) -> float:
        """Check the pressure differential. Raises an exception if difference is insufficent
        or if the pressure sensor cannot be read.

        Returns
        -------
        float:
            Pressure difference value

        Exceptions
        ----------
        PressureSensorBusy:
            Raised if a valid value cannot be read from the sensor after the specified number of max_attempts
        PressureLeak:
            Raised if the pressure difference between the fully extended and retracted syringe is insufficient.
        """

        # Move syringe to its maximally extended (lowest) position
        mscope.pneumatic_module.setDutyCycle(mscope.pneumatic_module.getMinDutyCycle())

        # Record pressure at the bottom of the syringe range
        try:
            final_pressure, _ = mscope.pneumatic_module.getPressureMaxReadAttempts(
                max_attempts=10
            )
        except PressureSensorBusy:
            raise

        # Check if there is a pressure leak
        mscope.pneumatic_module.mpr.ambient_pressure = ambient_pressure
        mscope.pneumatic_module.mpr.final_pressure = final_pressure
        pressure_diff = ambient_pressure - final_pressure
        if pressure_diff < MIN_PRESSURE_DIFF:
            raise PressureLeak(
                f"Pressure leak detected. Could only generate {pressure_diff:.3f} hPa pressure differential."
            )
        else:
            # Return syringe to its initial position
            mscope.pneumatic_module.setDutyCycle(
                mscope.pneumatic_module.getMaxDutyCycle()
            )
            return pressure_diff

    @init_generator
    def find_cells_routine(
        self,
        mscope: MalariaScope,
        pull_time: float = 7,
        steps_per_image: int = 10,
        skip_syringe_pull: bool = False,
    ) -> Generator[None, np.ndarray, Optional[int]]:
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
        steps_per_image: int = 10
            How far to move the motor between before collecting another image
        skip_syringe_pull: bool
            If True, the syringe will not be pulled before the motor sweep (useful when returning from an OOF exception and we want to keep the cells flowing as they are)

        What to pass in send()
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

        # Maximum number of times to run check for cells routine before aborting
        max_attempts = 3
        cell_finder = CellFinder()
        flow_controller = FlowController(mscope.pneumatic_module)
        img = yield

        # Initial check for cells, return current motor position if cells found
        cell_finder.add_image(mscope.motor.pos, img)
        try:
            return cell_finder.get_cells_found_position()
        except NoCellsFound:
            cell_finder.reset()

        while True:
            """
            1. Pull syringe for pull_time seconds (unless deliberately skipped)
            2. Sweep the motor through the full range of motion and take in images at each step
            3. Assess whether cells are present
            """

            if max_attempts == 0:
                raise NoCellsFound()

            # Pull the syringe maximally for `pull_time` seconds

            # The syringe pull step is only skipped when this function is called from an OOF exception
            # in which case, cells are already present, we just need to sweep the motor to find them
            if not (skip_syringe_pull):
                start = perf_counter()

                while perf_counter() - start < pull_time:
                    flow_controller.adjustSyringe(-1)
                    img = yield
                mscope.pneumatic_module.setDutyCycle(
                    mscope.pneumatic_module.getMaxDutyCycle()
                )

            # Perform a full focal stack and get the cross-correlation value for each image

            # If we're currently at the bottom, do the bottom-up sweep. Otherwise, do the top-down sweep.
            if mscope.motor.pos == 0:
                for pos in range(0, mscope.motor.max_pos, steps_per_image):
                    mscope.motor.move_abs(pos)
                    img = yield
                    cell_finder.add_image(mscope.motor.pos, img)
                    try:
                        return cell_finder.get_cells_found_position()
                    except NoCellsFound:
                        pass
            elif mscope.motor.pos == mscope.motor.max_pos:
                for pos in range(mscope.motor.max_pos, 0, -steps_per_image):
                    mscope.motor.move_abs(pos)
                    img = yield
                    cell_finder.add_image(mscope.motor.pos, img)
                    try:
                        return cell_finder.get_cells_found_position()
                    except NoCellsFound:
                        pass
            else:
                # Move from the current position to the bottom sweep as we're going down
                for pos in range(mscope.motor.pos, 0, -steps_per_image):
                    mscope.motor.move_abs(pos)
                    img = yield
                    cell_finder.add_image(mscope.motor.pos, img)
                    try:
                        return cell_finder.get_cells_found_position()
                    except NoCellsFound:
                        pass

                # If cells not found on the way down, sweep all the way back up
                for pos in range(0, mscope.motor.max_pos, steps_per_image):
                    mscope.motor.move_abs(pos)
                    img = yield
                    cell_finder.add_image(mscope.motor.pos, img)
                    try:
                        return cell_finder.get_cells_found_position()
                    except NoCellsFound:
                        pass

            # The below only runs if the function didn't return early in the for loop above
            max_attempts -= 1
            self.logger.warning(
                f"No cells found, attempting again. Remaining attempts: {max_attempts}"
            )

    @init_generator
    def cell_density_routine(self) -> Generator[Optional[int], List[int], None]:
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
                class_counts = yield prev_measurements[idx]
                prev_measurements[idx] = class_counts[0]

                idx = (idx + 1) % processing_constants.CELL_DENSITY_HISTORY_LEN

                # number of elements of prev_measurements that is less than MIN_CELL_COUNT
                num_low_density = (
                    prev_measurements < processing_constants.MIN_CELL_COUNT
                ).sum()

                density_threshold = 0.95 * processing_constants.CELL_DENSITY_HISTORY_LEN

                if num_low_density > density_threshold:
                    raise LowDensity(
                        f"mean density over last {processing_constants.CELL_DENSITY_HISTORY_LEN} "
                        f"is {np.mean(prev_measurements)} cells - should be over {processing_constants.MIN_CELL_COUNT}"
                    )

                prev_time = perf_counter()
            else:
                # if we haven't waited period yet, yield immediately
                yield None
