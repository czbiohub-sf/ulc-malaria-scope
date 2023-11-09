import numpy as np
import numpy.typing as npt

from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_IDX_MAP, YOGO_CLASS_LIST


import pandas as pd

class StatsUtils():
    def init(self):
        # TODO request normalized matrices from Axel (esp. std matrix!)

        self.matrix_dim = len(YOGO_CLASS_LIST)

        # Load confusion matrix
        raw_cmatrix = np.reshape(
                        pd.read_csv('confusion_matrix.csv')['nPredictions'].to_numpy(),
                        (self.matrix_dim, self.matrix_dim)
                        )
        norm_cmatrix = raw_cmatrix / raw_cmatrix.sum(axis=1).reshape(-1, 1)
        self.inv_cmatrix = np.linalg.inv(norm_cmatrix)

        # Load standard deviation matrix
        norm_cmatrix_std = np.random.rand(7, 7) * 0.2 + 0.1    # temporarily generate vals between 0.1-0.3
        self.inv_cmatrix_std = self.calc_inv_cmatrix_std(norm_cmatrix_std)


    def calc_inv_cmatrix_std(self, norm_cmatrix_std : npt.NDArray):
        squared_inv_cmatrix = np.square(self.inv_cmatrix)
        squared_norm_cmatrix_std = np.square(norm_cmatrix_std)

        inv_cmatrix_std = np.zeros((self.matrix_dim, self.matrix_dim))

        for i in range(0, self.matrix_dim):
            for j in range(0, self.matrix_dim):
                calc = np.matmul(squared_inv_cmatrix[i, :], squared_norm_cmatrix_std)
                inv_cmatrix_std[i, j] = np.matmul(calc, squared_inv_cmatrix[:, j])                

        return inv_cmatrix_std


    def calc_deskewed_counts(self, raw_counts: npt.NDArray, int_out: bool = True) -> npt.NDArray:
        """
        Deskew raw counts using inverse confusion matrix. Optional parameters
        
        Returns list of deskewed cell counts. that are whole number integers (ie. no negative vals)
        """
        deskewed_floats = np.matmul(raw_counts, self.inv_cmatrix).tolist()
        deskewed_pos = [0 for val in deskewed_floats if val < 0]
        deskewed_ints = [round(val) for val in deskewed_pos]

        if int_out:
            return [round(val) for val in deskewed_pos]
        else:
            return deskewed_pos

            
    # def calc_parasitemia(self, deskewed_counts: npt.NDArray, total_rel_err: npt.NDArray) -> npt.NDArray:



    def calc_total_rel_err(self, raw_counts: npt.NDArray, deskewed_counts: npt.NDArray) -> npt.NDArray:
        """
        Return percent error based on model confidences and Poisson statistics
        """
        if count == 0:
            return np.nan

        poisson_rel_err = self.calc_poisson_rel_err(deskewed_counts)
        deskew_rel_err = self.calc_deskew_rel_err(raw_counts)

        return sqrt(np.square(poisson_rel_err) + np.square(deskew_rel_err))

    
    def calc_poisson_rel_err(self, deskewed_counts: npt.NDArray) -> npt.NDArray:
        return 1 / np.sqrt(deskewed_counts)

    
    def calc_deskew_rel_err(self, raw_counts: npt.NDArray) -> npt.NDArray:
        squared_err = 0

        squared_raw_counts = np.square(raw_counts)
        squared_inv_cmatrix_std = np.square(self.inv_cmatrix_std)

        return np.matmul(squared_raw_counts, squared_inv_cmatrix_std)


    def get_class_stats_str(
        self,
        name: str,
        deskewed_count: float,
        percent_err: float,
    ) -> str:
        """
        Return results string with statistics for individual class
        """
        return f"\t{name.upper()}: {int(deskewed_count)} ({percent_err:.3g}%%)\n"


    def get_all_stats_str(
        self,
        raw_counts: npt.NDArray,
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

        # Deskew
        deskewed_counts = self.calc_deskewed_counts(raw_counts, int_out=False)
        
        # Get uncertainty
        rel_err = self.calc_total_rel_err(raw_counts)
        percent_err = np.multiply(rel_err, 100)

        template_string = "Class results: Count (%% uncertainty)\n"
        class_strings = [
            self.get_class_stats_str(
                class_name,
                deskewed_count[class_idx],
                percent_err[class_idx],
            )
            for class_name, class_idx in YOGO_CLASS_IDX_MAP.items()
        ]
        return template_string + "".join(class_strings)
