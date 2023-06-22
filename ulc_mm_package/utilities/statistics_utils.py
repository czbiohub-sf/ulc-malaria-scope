import numpy as np
import numpy.typing as npt

from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_IDX_MAP


def calc_total_perc_err(confidences: npt.NDArray) -> str:
    """
    Return percent error based on model confidences and Poisson statistics
    """
    num_confidences = len(confidences)

    if num_confidences == 0:
        return np.nan

    poisson_rel_err = calc_poisson_rel_err(num_confidences)
    total_perc_err = poisson_rel_err * 100

    return f"{total_perc_err:.3g}%%"


def calc_poisson_rel_err(count: int) -> float:
    """
    Return relative error based on Poisson statistics
    """
    return 1 / sqrt(count)


def calc_confidence_rel_err(confidences: npt.NDArray) -> float:
    """
    Return relative error based on model confidences
    """
    # TODO: Is it better to calculate standard dev of predictions using 1-np.mean(confidences)
    # TODO: Is 1-confidence equivalent to percent error/standard deviation or variance?
    return calc_rms(1 - confidences)


def calc_rms(arr: Union[npt.NDArray, List]) -> float:
    """
    Calculate RMS of array
    """
    return np.sqrt(np.mean(np.square(np.array(arr))))


def get_class_stats_str(
    name: str,
    count: npt.NDArray,
    all_confidences_by_class: npt.NDArray,
    peak_confidences_by_class: npt.NDArray,
) -> str:
    """
    Return results string with statistics for individual class
    """
    return f"\t{name.upper()}: {int(count)} | {int(np.sum(all_confidences_by_class))} ({calc_total_perc_err(peak_confidences_by_class)} | {np.mean(sorted_confidences):.3g} | {np.std(peak_confidences_by_class):.3g})\n"


def get_all_stats_str(
    counts: npt.NDArray,
    all_confidences_by_class: List[npt.NDArray],
    peak_confidences_by_class: List[npt.NDArray],
) -> str:
    """
    Parameters
    ----------
    counts: npt.NDArray
    all_cnofidences_by_class: List[npt.NDArray]
        List of length NUM_CLASSES, ndarray of size 1 x N (N for however many objects detected in total)
        This has all the confidences for a given class (including confidences where that class was not the most likely predicted class for a given prediction)
    peak_confidences_by_class: List[npt.NDArray]
        List of length NUM_CLASSES, ndarray of size 1 x M (M variable for each class, depends on how many of those class instances were detected)
        This has all the confidences for objects which were predicted to be a particular class

    Returns
    -------
    str
        Results string with statistics for all classes
    """
    template_string = "Class results: Unscaled cell count | expectation value (percent uncertainty | confidence mean | confidence std)\n"
    class_strings = [
        get_class_stats_str(
            class_name,
            counts[class_idx],
            all_confidences_by_class[class_idx],
            peak_confidences_by_class[class_idx],
        )
        for class_name, class_idx in YOGO_CLASS_IDX_MAP.items()
    ]
    return template_string + "".join(class_strings)
