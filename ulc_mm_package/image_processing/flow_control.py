from typing import Optional, Tuple
import logging

import numpy as np

from ulc_mm_package.scope_constants import CAMERA_SELECTION, DOWNSAMPLE_FACTOR
from ulc_mm_package.image_processing.ewma_filtering_utils import EWMAFiltering
from ulc_mm_package.image_processing.processing_constants import (
    FLOW_CONTROL_EWMA_ALPHA,
    TOL_PERC,
)
from ulc_mm_package.image_processing.flowrate import FlowRateEstimator

from ulc_mm_package.hardware.pneumatic_module import PneumaticModule, SyringeEndOfTravel


class FlowControlError(Exception):
    pass


class CantReachTargetFlowrate(FlowControlError):
    """Raised when the target flowrate cannot be reached"""

    def __init__(self, flowrate):
        self.flowrate = flowrate


class TargetFlowrateNotSet(FlowControlError):
    """Raised when `control_flow` is called without previously setting a target_flowrate"""


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
        h: int = CAMERA_SELECTION.IMG_HEIGHT // DOWNSAMPLE_FACTOR,
        w: int = CAMERA_SELECTION.IMG_WIDTH // DOWNSAMPLE_FACTOR,
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
        self.logger = logging.getLogger(__name__)

        self.pneumatic_module: PneumaticModule = pneumatic_module
        self.flowrate: Optional[float] = None
        self.alpha: float = FLOW_CONTROL_EWMA_ALPHA
        self.EWMA = EWMAFiltering(self.alpha)
        self.counter: int = 0
        self.prev_adjustment_stamp: int = 0
        self.feedback_delay_frames = self.EWMA.get_adjustment_period_ewma()
        self.fre: FlowRateEstimator = FlowRateEstimator(h, w)

        self.first_image: bool = True
        self.target_flowrate: Optional[float] = None
        self.logger = logging.getLogger(__name__)

    def reset(self):
        self.fre.reset()
        self.flowrate: Optional[float] = None
        self.counter: int = 0
        self.prev_adjustment_stamp: int = 0
        self.target_flowrate: Optional[float] = None

    def set_alpha(self, alpha: float) -> None:
        """Set the alpha value for EWMA filtering"""
        self.alpha = alpha
        self.EWMA.alpha = self.alpha
        self.feedback_delay_frames = self.EWMA.get_adjustment_period_ewma()

    def _add_image_and_update_flowrate(self, img: np.ndarray, time: float) -> None:
        """Adds an image to the FlowRateEsimator and updates the flowrate measurement.

        Note, the first value returned by FlowRateEstimator's `add_image_and_calculate_pair_displacement`
        is ignored. That is what `is_primed` checks for below (since the estimator needs to see
        at least two images before it can make a displacement calculation.)

        Parameters
        ----------
        img: np.ndarray
        time: float
            Timestamp of when the image was received
        """

        dx, dy, xcorr_coeff = self.fre.add_image_and_calculate_pair_displacement(
            img, time
        )

        if self.fre.is_primed():
            if self.flowrate is None:
                self.flowrate = dy
                self.EWMA.set_init_val(self.flowrate)
            else:
                self.flowrate = self.EWMA.update_and_get_val(dy)
            self.counter += 1

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
    ) -> Tuple[Optional[float], Optional[float], Optional[bool]]:
        """Takes in an image, calculates, and adjusts flowrate periodically to maintain the target (within a tolerance bound).
        Periodically is defined as twice the half-life of the EWMA filter (based on its alpha value).

        If the `self.target_flowrate` has not been set, this function raises an exception.

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
        bool:
            True if the syringe move was successful, false if the syringe has reached the end of its range of motion

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
                "Please set a target flowrate using `set_target_flowrate(target_value)' first. The value should be a float."
            )

        self._add_image_and_update_flowrate(img, timestamp)

        # Adjust pressure using the pneumatic module based on the flow rate error
        if self.flowrate is not None:
            flow_error = get_flow_error(self.target_flowrate, self.flowrate)
            if self.counter >= self.prev_adjustment_stamp + self.feedback_delay_frames:
                self.prev_adjustment_stamp = self.counter

                try:
                    self._adjustSyringe(flow_error)
                    syringe_successfully_adjusted = True
                except CantReachTargetFlowrate as e:
                    self.logger.error(
                        f"Can't reach target flowrate {e.flowrate}. Syringe at end of travel."
                    )
                    syringe_successfully_adjusted = False

                self.logger.debug(
                    f"Flow diff: {flow_error}, syringe pos: {self.pneumatic_module.getCurrentDutyCycle()}"
                )
            return self.flowrate, flow_error, syringe_successfully_adjusted
        else:
            return (None, None, None)

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
                if not self.pneumatic_module.is_locked():
                    self.pneumatic_module.threadedDecreaseDutyCycle()
            except SyringeEndOfTravel:
                raise CantReachTargetFlowrate(self.flowrate)
        elif flow_error < 0:
            try:
                # Decrease pressure, move syringe up
                if not self.pneumatic_module.is_locked():
                    self.pneumatic_module.threadedIncreaseDutyCycle()
            except SyringeEndOfTravel:
                raise CantReachTargetFlowrate(self.flowrate)

    def stop(self):
        self.fre.stop()
        self.fre.reset()
