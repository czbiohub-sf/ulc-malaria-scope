import numpy as np
import numpy.typing as npt

from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_IDX_MAP


import pandas as pd

class StatsUtils():
    def init(self):
        # TODO request normalized matrices from Axel (esp. std matrix!)

        # Load confusion matrix
        raw_cmatrix = np.reshape(pd.read_csv('confusion_matrix.csv')['nPredictions'].to_numpy(), (7, 7))
        norm_cmatrix = raw_cmatrix / raw_cmatrix.sum(axis=1).reshape(-1, 1)
        self.inv_cmatrix = np.linalg.inv(norm_cmatrix)

        # Load standard deviation matrix
        norm_cmatrix_std = np.random.rand(7, 7) * 0.2 + 0.1    # temporarily generate vals between 0.1-0.3
        self.inv_cmatrix_std = self.calc_inv_cmatrix_err(norm_cmatrix_std)


    def calc_inv_cmatrix_err(self, norm_cmatrix_std):
        matrix_dim, _ = np.shape(self.inv_cmatrix)
        iter_arr = range(0, matrix_dim)

        squared_inv_cmatrix = np.square(self.inv_cmatrix)
        squared_norm_cmatrix_std = np.square(norm_cmatrix_std)

        inv_cmatrix_std = np.zeros((matrix_dim, matrix_dim))

        for i in iter_arr:
            for j in iter_arr:
                calc = np.matmul(squared_inv_cmatrix[i, :], squared_norm_cmatrix_std)
                inv_cmatrix_std[i, j] = np.matmul(calc, squared_inv_cmatrix[:, j])                

        return inv_cmatrix_std


    def calc_total_perc_err(self, confidences: npt.NDArray) -> str:
        """
        Return percent error based on model confidences and Poisson statistics
        """
        num_confidences = len(confidences)

        if num_confidences == 0:
            return np.nan

        poisson_rel_err = calc_poisson_rel_err(num_confidences)
        total_perc_err = poisson_rel_err * 100

        return f"{total_perc_err:.3g}%%"


    def calc_poisson_rel_err(self, count: int) -> float:
        """
        Return relative error based on Poisson statistics
        """
        return 1 / sqrt(count)


    def get_class_stats_str(
        self,
        name: str,
        count: npt.NDArray,
        all_confidences_by_class: npt.NDArray,
        peak_confidences_by_class: npt.NDArray,
    ) -> str:
        """
        Return results string with statistics for individual class
        """

        conf_mean = (
            np.nan
            if len(peak_confidences_by_class) == 0
            else np.mean(peak_confidences_by_class)
        )
        conf_sd = (
            np.nan
            if len(peak_confidences_by_class) == 0
            else np.std(peak_confidences_by_class)
        )

        return f"\t{name.upper()}: {int(count)} | {int(np.sum(all_confidences_by_class))} ({this.calc_total_perc_err(peak_confidences_by_class)} | {conf_mean:.3g} | {conf_sd:.3g})\n"


    def get_all_stats_str(
        self,
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
            this.get_class_stats_str(
                class_name,
                counts[class_idx],
                all_confidences_by_class[class_idx],
                peak_confidences_by_class[class_idx],
            )
            for class_name, class_idx in YOGO_CLASS_IDX_MAP.items()
        ]
        return template_string + "".join(class_strings)
