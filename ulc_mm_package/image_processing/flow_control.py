"""
FlowController
"""

import numpy as np

from ulc_mm_package.image_processing.processing_constants import (
    NUM_IMAGE_PAIRS,
    WINDOW_SIZE,
    TOL_PERC,
)
from time import perf_counter
from ulc_mm_package.image_processing.flowrate import FlowRateEstimator
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule, SyringeDirection, PressureLeak


class FlowController:
    def __init__(self, pneumatic_module: PneumaticModule, h: int=600, w: int=800, window_size: int=WINDOW_SIZE):
        """Flow controller class.
        
        Wraps the functionality of FlowRateEstimator, PneumaticModule, and the flow control algorithm
        together to control the flowrate. Single images are provided to this class via `controlFlow(img)`
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

        self.window_size = window_size
        self.pneumatic_module = pneumatic_module
        self.flowrates = np.zeros(self.window_size)
        self.fre = FlowRateEstimator(h, w, num_image_pairs=NUM_IMAGE_PAIRS)

        self._idx = 0
        self.target_flowrate: float = None
        self.curr_flowrate: float = None

    def _addImage(self, img: np.ndarray, time: float):
        """Adds an image to the FlowRateEsimator and appends the flowrate to self.flowrates
        if the FRE window is full.

        """

        self.fre.addImageAndCalculatePair(img, time)
        if self.fre.isFull():
            _, dy, _, _ = self.fre.getStatsAndReset()
            self.flowrates[self._idx] = dy
            self._idx += 1

    def _isFull(self):
        """Returns whether the EWMA window has been filled with a new batch of flowrate measurements."""
        
        if self._idx == len(self.flowrates):
            self._idx = 0
            return True
        return False

    def setTargetFlowrate(self, target_flowrate: float):
        """Set the target flowrate.

        Parameters
        ----------
        target_flowrate: float
            The flowrate to attempt to hold steady
        """

        self.target_flowrate = target_flowrate

    def fastFlowAdjustment(self, img: np.ndarray) -> float:
        """
        Adjust flow on a faster feedback cycle (i.e w/o the EWMA batching)
        until the target flowrate is achieved.

        Some background explanation
        ---------------------------
        Using the default FlowRateEstimator batch size
        (12 pairs of images, i.e 24 frames), the syringe is adjusted every 0.8s.

        The pneumatic module currently has 60 increments from its uppermost position to being
        fully extended. If the target flowrate requires the syringe to be at the halfway point
        (30 steps), this will take ~24s.

        Currently there is not a smarter proportional gain integrated into the control
        because:
            1. The granularity of the steps is fairly crude
            2. The response of the system is (empirically) nonlinear and at times, sporadic

        I _think_ that a simple, step-by-step increment/decrement and reassessment of the flow
        is the ideal solution for now.

        Parameters
        ----------
        img: np.ndarray
            Image to be passed into the FlowRateEstimator
        """

        self.fre.addImageAndCalculatePair(img, time)
        if self.fre.isFull():
            _, dy, _, _ = self.fre.getStatsAndReset()
            self.curr_flowrate = dy
            flow_error = self._getFlowError()
            self._adjustSyringe(flow_error)

            # If rough flow rate has been achieved, return float
            # else return False
            if flow_error == 0:
                return float(dy)

    def controlFlow(self, img: np.ndarray):
        """Takes in an image, calculates, and adjusts flowrate periodically to maintain the target (within a tolerance bound).
        
        If the `self.target_flowrate` has not been set, the first full measurement is used as the target, and all subsequent measurements
        will result in adjustments relative to that initial target.

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
        """

        self._addImage(img, perf_counter())
        if self._isFull():
            self.curr_flowrate = self._ewma(self.flowrates)

            # Set target flowrate if this is the first calculation
            self.target_flowrate = self.target_flowrate if self.target_flowrate is not None else self.curr_flowrate
            
            # Adjust pressure using the pneumatic module based on the flow rate error
            flow_error = self._getFlowError()
            self._adjustSyringe(flow_error)


    def _getFlowError(self):
        """Returns the flowrate error, i.e the difference between the target and current flowrate. 
        
        Returns
        -------
        float:
            Positive (+) number if the current flowrate is _below_ the target.
            Negative (-) number if the current flowrate is _above_ the target.
            0 if the current flowrate is within +/- % tolerance of the target (as defined by TOL_PERC).
        """

        diff = self.target_flowrate - self.curr_flowrate

        if abs(diff) / self.target_flowrate < TOL_PERC:
            return 0
        else:
            return diff

    def _adjustSyringe(self, flow_error: float):
        """Adjusts the syringe based on the flow error.
        
        Parameters
        ----------
        flow_error : float
        """
        
        if flow_error == 0:
            return
        elif flow_error > 0:
            if self.pneumatic_module.isMovePossible(SyringeDirection.DOWN):
                # Increase pressure, move syringe down
                self.pneumatic_module.decreaseDutyCycle()
            else:
                raise PressureLeak
        elif flow_error < 0:
            if self.pneumatic_module.isMovePossible(SyringeDirection.UP):
                # Decrease pressure, move syringe up
                self.pneumatic_module.increaseDutyCycle()
            else:
                raise PressureLeak

    def _ewma(self, data):
        """Adapted from @Divakar on StackOverflow
        
        Fast, pure-numpy implementation of an exponentially weighted moving average.

        Parameters
        ----------
        data : np.ndarray
            Data on which to run EWMA smoothing
        """
        
        window = self.window_size
        alpha = 2 /(window + 1.0)
        alpha_rev = 1-alpha
        n = data.shape[0]

        pows = alpha_rev**(np.arange(n+1))

        scale_arr = 1/pows[:-1]
        offset = data[0]*pows[1:]
        pw0 = alpha*alpha_rev**(n-1)

        mult = data*pw0*scale_arr
        cumsums = mult.cumsum()
        out = offset + cumsums*scale_arr[::-1]
        return out[-1]