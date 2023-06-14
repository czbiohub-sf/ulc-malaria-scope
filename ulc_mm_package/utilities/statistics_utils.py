import numpy as np
import numpy.typing as npt

from pathlib import Path
from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_IDX_MAP
from ulc_mm_package.image_processing.data_storage import DataStorage


def calc_total_perc_err(confidences: npt.NDArray) -> str:
    """ "
    Return percent error based on model confidences and Poisson statistics
    """
    num_confidences = len(confidences)

    if num_confidences == 0:
        return np.nan

    poisson_rel_err = calc_poisson_rel_err(num_confidences)
    total_perc_err = poisson_rel_err * 100

    return f"{total_perc_err:.3g}%%"


def calc_poisson_rel_err(count: int) -> float:
    """ "
    Return relative error based on Poisson statistics
    """
    return 1 / sqrt(count)


def calc_confidence_rel_err(confidences: npt.NDArray) -> float:
    """ "
    Return relative error based on model confidences
    """
    # TODO: Is it better to calculate standard dev of predictions using 1-np.mean(confidences)
    # TODO: Is 1-confidence equivalent to percent error/standard deviation or variance?
    return calc_rms(1 - confidences)


def calc_rms(arr: Union[npt.NDArray, List]) -> float:
    """ "
    Calculate RMS of array
    """
    return np.sqrt(np.mean(np.square(np.array(arr))))


def get_class_stats_str(
    name: str,
    count: npt.NDArray,
    unsorted_confidences: npt.NDArray,
    sorted_confidences: npt.NDArray,
) -> str:
    """ "
    Return results string with statistics for individual class
    """
    return f"\t{name.upper()}: {int(count)} | {int(np.sum(unsorted_confidences))} ({calc_total_perc_err(sorted_confidences)} | {np.mean(sorted_confidences):.3g} | {np.std(sorted_confidences):.3g})\n"


def get_all_stats_str(
    counts: npt.NDArray,
    unsorted_confidences: npt.NDArray,
    sorted_confidences: npt.NDArray,
) -> str:
    """ "
    Return results string with statistics for all classes
    """
    template_string = f"Class results: Unscaled cell count | expectation value (percent uncertainty | confidence mean | confidence std)\n"
    class_strings = [
        get_class_stats_str(
            class_name,
            counts[class_idx],
            unsorted_confidences[class_idx],
            sorted_confidences[class_idx],
        )
        for class_name, class_idx in YOGO_CLASS_IDX_MAP.items()
    ]
    return template_string + "".join(class_strings)
