import numpy as np
import numpy.typing as npt

from typing import List, Union
from math import sqrt

from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_CLASS_IDX_MAP,
    YOGO_CLASS_LIST,
    ASEXUAL_PARASITE_CLASS_IDS,
    YOGO_CMATRIX_MEAN_DIR,
    YOGO_CMATRIX_STD_DIR,
)

import pandas as pd

# TODO dummy define above constants to run in ipython
# TODO rewrite supplementary note in more detail

class StatsUtils():
    def __init__(self):
        # TODO request normalized matrices from Axel (esp. std matrix!)

        self.matrix_dim = len(YOGO_CLASS_LIST)

        # Load confusion matrix data
        norm_cmatrix = np.load(YOGO_CMATRIX_MEAN_DIR)
        norm_cmatrix_std = np.load(YOGO_CMATRIX_STD_DIR)
        # raw_cmatrix = np.reshape(
        #                 pd.read_csv('../utilities/confusion_matrix.csv')['nPredictions'].to_numpy(), # TODO turn dir into a constant
        #                 (self.matrix_dim, self.matrix_dim)
        #                 )
        # norm_cmatrix = raw_cmatrix / raw_cmatrix.sum(axis=1).reshape(-1, 1)
        # norm_cmatrix_std = np.random.rand(7, 7) * 0.1    # temporarily generate vals between 0.1


        # Compute inverses
        self.inv_cmatrix = np.linalg.inv(norm_cmatrix)
        self.inv_cmatrix_std = self.calc_inv_cmatrix_std(norm_cmatrix_std)


    def calc_inv_cmatrix_std(self, norm_cmatrix_std : npt.NDArray):
        """
        Returns standard deviations corresponding to the inverse of a matrix, 
        given standard deviations of the initial matrix (based on Lefebvre, 2000)
        """
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
        deskewed_floats = np.matmul(raw_counts, self.inv_cmatrix)
        # Round all negative values to 0
        deskewed_floats[deskewed_floats < 0] = 0

        if int_out:
            return np.rint(deskewed_floats)
        else:
            return deskewed_floats

            
    def calc_parasitemia_rel_err(self, rel_errs: npt.NDArray) -> float:
        """
        Return relative uncertainty of total parasitemia count
        """
        # Filter for parasite classes only
        parasite_rel_errs = rel_errs[ASEXUAL_PARASITE_CLASS_IDS]

        return sqrt(np.sum(np.square(parasite_rel_errs)))

    def calc_total_rel_errs(self, raw_counts: npt.NDArray, deskewed_counts: npt.NDArray) -> npt.NDArray:
        """
        Return relative uncertainty of each class count based on deskewing and Poisson statistics
        """
        # TODO clamp this above 0?

        rel_poisson_errs = self.calc_rel_poisson_errs(deskewed_counts)
        rel_deskew_errs = self.calc_rel_deskew_errs(raw_counts, deskewed_counts)

        print(f"RAW: {raw_counts[0]}")
        print(f"DESKEWED: {deskewed_counts[0]}")

        rel_errs = np.sqrt(np.square(rel_poisson_errs) + np.square(rel_deskew_errs))

        print(f"POISSON / DESKEW / REL: {rel_poisson_errs[0]} / {rel_deskew_errs[0]} / {rel_errs[0]}")

        return rel_errs

    def calc_rel_poisson_errs(self, deskewed_counts: npt.NDArray) -> npt.NDArray:
        """
        Return absolute uncertainty of each class count based on Poisson statistics only
        """
        sqrt_counts = np.sqrt(deskewed_counts)

        return np.divide(
                    1, 
                    sqrt_counts, 
                    out=np.zeros(sqrt_counts.shape, dtype=deskewed_counts.dtype),
                    where=~np.isclose(sqrt_counts, 0)
                )


    def calc_rel_deskew_errs(self, raw_counts: npt.NDArray, deskewed_counts: npt.NDArray) -> npt.NDArray:
        """
        Return absolute uncertainty of each class count based on deskewing only
        """

        # TODO how to deal with this square??
        divided_deskewed_counts = np.divide(
                                1, 
                                deskewed_counts, 
                                out=np.zeros(deskewed_counts.shape, dtype=deskewed_counts.dtype),
                                where=~np.isclose(deskewed_counts, 0)
                            )
                            
        class_ratios = np.outer(divided_deskewed_counts, raw_counts)
        product = np.matmul(np.square(class_ratios), np.square(self.inv_cmatrix_std))

        return np.sqrt(np.diagonal(product))


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
        raw_counts: npt.NDArray

        Returns
        -------
        str
            Results string with statistics for all classes
        """

        # Deskew
        deskewed_counts = self.calc_deskewed_counts(raw_counts, int_out=False)
        
        # Get uncertainty
        rel_errs = self.calc_total_rel_errs(raw_counts, deskewed_counts)
        percent_errs = np.multiply(rel_errs, 100)

        template_string = "Class results: Count (%% uncertainty)\n"
        class_strings = [
            self.get_class_stats_str(
                class_name,
                deskewed_counts[class_idx],
                percent_errs[class_idx],
            )
            for class_name, class_idx in YOGO_CLASS_IDX_MAP.items()
        ]
        return template_string + "".join(class_strings)
