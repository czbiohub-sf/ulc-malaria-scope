import numpy as np
import numpy.typing as npt

from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_PERIOD_NUM

def calc_total_perc_err(confidences: npt.NDArray) -> str:
    """"
    Return percent error based on model confidences and Poisson statistics
    """
    num_confidences = len(confidences)

    if num_confidences == 0:
        return "N/A"

    poisson_rel_err = calc_poisson_rel_err(num_confidences)
    confidence_rel_err = calc_confidence_rel_err(confidences)

    total_perc_err = calc_rms([poisson_rel_err, confidence_rel_err])*100

    return(f"{total_perc_err:.3g}%%")

def calc_poisson_rel_err(count: int) -> float:
    """"
    Return relative error based on Poisson statistics
    """
    # TODO: Does this accurately account for multiplication by YOGO_PERIOD_NUM
    return YOGO_PERIOD_NUM / sqrt(count)

def calc_confidence_rel_err(confidences: npt.NDArray) -> float:    
    """"
    Return relative error based on model confidences
    """
    # TODO: Is it better to calculate standard dev of predictions using 1-np.mean(confidences)
    # TODO: Is 1-confidence equivalent to percent error/standard deviation or variance?
    return calc_rms(1-confidences)

def calc_rms(arr: Union[npt.NDArray, List]) -> float:
    """"
    Calculate RMS of array
    """
    return np.sqrt(np.mean(np.square(np.array(arr))))

