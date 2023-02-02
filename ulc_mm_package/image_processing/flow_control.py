from typing import Optional, Tuple
import logging

import numpy as np

from ulc_mm_package.image_processing.processing_modules import (
    ewma_update_step,
    get_adjustment_period_ewma,
)
from ulc_mm_package.image_processing.processing_constants import (
    FLOW_CONTROL_EWMA_ALPHA,
    TOL_PERC,
    FAILED_CORR_PERC_TOLERANCE,
)
from ulc_mm_package.image_processing.flowrate import (
    FlowRateEstimator,
    CORRELATION_THRESH,
)
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule, SyringeEndOfTravel


class FlowControlError(Exception):
    pass


class CantReachTargetFlowrate(FlowControlError):
    """Raised when the target flowrate cannot be reached"""

    def __init__(self, flowrate):
        self.flowrate = flowrate


class TargetFlowrateNotSet(FlowControlError):
    """Raised when `control_flow` is called without previously setting a target_flowrate"""


class LowConfidenceCorrelations(FlowControlError):
    """Raised when the number of recent low confidence measurements is too high.

    Normally, an exception is raised if the desired flow rate cannot be achieved and the syringe is already at its maximum position.
    In cases where measurements are invalid (i.e due to low confidence), there may be some other underlying issue.

    This exception, LowConfidenceCorrelations, is to be raised after some threshold number of failed correlations have occurred (a % of total measurements made),
    allowing flow control to terminate early.

    Examples where correlations may fail:
        - RBCs flowing at different rates (e.g a sample with a mix of regular cells and reticulocytes might exhibit this)
        - Air bubbles deflecting flow
        - Large toner blobs
        - etc.
    """

    def __init__(self, num_failed_corrs: int, total_pairs: int, tol_perc: float):
        msg = (
            f"Too many recent xcorr calculations have yielded poor confidence. "
            f"The number of recent low-confidence correlations is = {num_failed_corrs} ({100*num_failed_corrs / total_pairs:.2f}% of measurements) "
        )
        super().__init__(f"{msg}")


def get_flow_error(target_flowrate: float, curr_flowrate: float):
    """Returns the flowrate error, i.e the difference between the target and current flowrate.

    Parameters
    ----------
    target_flowrate: float
    curr_flowrate: float

    Returns
    -------
    float:
        Positive (+) number if the current flowrate is _below_ the target.
        Negative (-) number if the current flowrate is _above_ the target.
        0 if the current flowrate is within +/- % tolerance of the target (as defined by TOL_PERC).
    """

    diff = target_flowrate - curr_flowrate

    if abs(diff) / target_flowrate < TOL_PERC:
        return 0
    else:
        return diff


class FlowController:
    def __init__(
        self,
        pneumatic_module: PneumaticModule,
        h: int = 600,
        w: int = 800,
    ):
        """Flow controller class.

        Wraps the functionality of FlowRateEstimator, PneumaticModule, and the flow control algorithm
        together to control the flowrate. Single images are provided to this class via `control_flow(img)`
        which, using the FlowRateEstimator, and an exponentially weighted moving average (EWMA) to smooth the noise,
        adjusts the syringe to maintain the target flowrate.

        Parameters
        ----------
        pneumatic_module : PneumaticModule
            Pneumatic module to control the syringe
        h : int
            Height of the image
        w : int
            Width of the image
        window_size : int
            Size of the exponentially weighted moving average (EWMA) window
        """

        self.pneumatic_module: PneumaticModule = pneumatic_module
        self.flowrate: Optional[float] = None
        self.counter: int = 0
        self.prev_adjustment_stamp: int = 0
        self.failed_corr_counter: int = 0
        self.alpha: float = FLOW_CONTROL_EWMA_ALPHA
        self.fre: FlowRateEstimator = FlowRateEstimator(h, w)

        self.first_image: bool = True
        self.target_flowrate: Optional[float] = None
        self.logger = logging.getLogger(__name__)

    def reset(self):
        self.fre.reset()
        self.flowrate: Optional[float] = None
        self.counter: int = 0
        self.prev_adjustment_stamp: int = 0
        self.failed_corr_counter: int = 0
        self.target_flowrate: Optional[float] = None

    def set_alpha(self, alpha: float) -> None:
        """Set the alpha value for EWMA filtering"""
        self.alpha = alpha

    def _add_image_and_update_flowrate(self, img: np.ndarray, time: float) -> None:
        """Adds an image to the FlowRateEsimator and updates the flowrate measurement.

        Note, the first value returned by FlowRateEstimator's `add_image_and_calculate_pair`
        is ignored. That is what `is_primed` checks for below (since the estimator needs to see
        at least two images before it can make a displacement calculation.)

        Parameters
        ----------
        img: np.ndarray
        time: float
            Timestamp of when the image was received
        """

        dx, dy, xcorr_coeff = self.fre.add_image_and_calculate_pair(img, time)

        if self.fre.is_primed():
            self.update_flowrate(dy)
            self.counter += 1

            if xcorr_coeff < CORRELATION_THRESH:
                self.failed_corr_counter += 1
                if (
                    self.failed_corr_counter / (self.counter)
                    > FAILED_CORR_PERC_TOLERANCE
                ):
                    raise LowConfidenceCorrelations(
                        self.failed_corr_counter,
                        self.counter,
                        FAILED_CORR_PERC_TOLERANCE,
                    )

    def set_target_flowrate(self, target_flowrate: float):
        """Set the target flowrate.

        Parameters
        ----------
        target_flowrate: float
            The flowrate to attempt to hold steady
        """

        self.target_flowrate = target_flowrate

    def control_flow(
        self, img: np.ndarray, timestamp: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """Takes in an image, calculates, and adjusts flowrate periodically to maintain the target (within a tolerance bound).

        If the `self.target_flowrate` has not been set, this function raises an exception.

        Some background explanation
        ---------------------------
        'Periodically' is defined as the number of frames it takes for the FlowRateEstimator to
        fill its window multiplied by the number of flowrate measurements to fill the EWMA
        window.

        For example, if the FlowRateEstimator takes in 12 image pairs (i.e 24 frames), and the
        EWMA window is 12, then a total of 288 frames will be observed before a syringe adjustment
        is made (@30fps, that's every 9.6s).

        Parameters
        ----------
        img : np.ndarray
            Image must have the same dimensions as those specified on initializing this FlowController class.
        timestamp: int
            Timestamp of when the image was taken

        Returns
        -------
        float:
            flow_val if a full window of measurements has been acquried by FlowRateEstimator
        int (None, None):
            Returned if a full window of measurements has not been acquired yet

        Exceptions
        ----------
        TargetFlowrateNotSet:
            Raised if a target is not set before this function is called. It can be set by calling `set_target_flowrate()`
        CantReachTargetFlowrate:
            Raised if the target flowrate hasn't been reached and the syringe
            can't move any further in the necessary direction, this exception is raised
        """

        if self.target_flowrate is None:
            raise TargetFlowrateNotSet(
                f"Please set a target flowrate using `set_target_flowrate(target_value)' first. The value should be a float."
            )

        self._add_image_and_update_flowrate(img, timestamp)

        # Adjust pressure using the pneumatic module based on the flow rate error
        if self.flowrate is not None:
            flow_error = get_flow_error(self.target_flowrate, self.flowrate)
            try:
                if (
                    self.counter
                    >= self.prev_adjustment_stamp
                    + get_adjustment_period_ewma(self.alpha)
                ):
                    self.prev_adjustment_stamp = self.counter
                    self._adjustSyringe(flow_error)
                    self.logger.info(
                        f"Flow error: {flow_error}, syringe pos: {self.pneumatic_module.getCurrentDutyCycle()}"
                    )
                    return self.flowrate, flow_error
            except CantReachTargetFlowrate:
                raise

    def _adjustSyringe(self, flow_error: float):
        """Adjusts the syringe based on the flow error.

        Parameters
        ----------
        flow_error : float

        Exceptions
        ----------
        CantReachTargetFlowrate:
            Raised when the syringe has reached the end of travel
            despite being above/below the required flowrate.
        """

        if flow_error == 0:
            return
        elif flow_error > 0:
            try:
                # Increase pressure, move syringe down
                self.pneumatic_module.decreaseDutyCycle()
            except SyringeEndOfTravel:
                raise CantReachTargetFlowrate(self.flowrate)
        elif flow_error < 0:
            try:
                # Decrease pressure, move syringe up
                self.pneumatic_module.increaseDutyCycle()
            except SyringeEndOfTravel:
                raise CantReachTargetFlowrate(self.flowrate)

    def update_flowrate(self, new_flowrate_dy: float):
        self.flowrate = ewma_update_step(self.flowrate, new_flowrate_dy, self.alpha)
