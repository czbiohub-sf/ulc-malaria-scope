import numpy as np
import numpy.typing as npt

from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_CLASS_IDX_MAP,
    YOGO_CLASS_LIST,
    RBC_CLASS_IDS,
    ASEXUAL_PARASITE_CLASS_IDS,
    YOGO_CMATRIX_MEAN_DIR,
    YOGO_INV_CMATRIX_STD_DIR,
)


class StatsUtils:
    def __init__(self):
        self.matrix_dim = len(YOGO_CLASS_LIST)

        # Load confusion matrix data
        norm_cmatrix = np.load(YOGO_CMATRIX_MEAN_DIR)
        self.inv_cmatrix_std = np.load(YOGO_INV_CMATRIX_STD_DIR)

        # Compute inverse
        self.inv_cmatrix = np.linalg.inv(norm_cmatrix)

    def calc_deskewed_counts(self, raw_counts: npt.NDArray) -> npt.NDArray:
        """
        Deskew raw counts using inverse confusion matrix. Optional parameters

        Returns list of deskewed cell counts. that are whole number integers (ie. no negative vals)
        """
        deskewed_floats = np.matmul(raw_counts, self.inv_cmatrix)
        # Round all negative values to 0
        deskewed_floats[deskewed_floats < 0] = 0

        return deskewed_floats

    def calc_parasitemia(self, deskewed_counts: npt.NDArray) -> float:
        """
        Return total parasitemia count
        """
        parasites = np.sum(deskewed_counts[ASEXUAL_PARASITE_CLASS_IDS])
        RBCs = np.sum(deskewed_counts[RBC_CLASS_IDS])
        return parasites / RBCs

    def calc_parasitemia_rel_err(self, raw_counts: npt.NDArray) -> float:
        """
        Return relative uncertainty of total parasitemia count
        See remoscope manuscript for full derivation
        """
        deskewed_counts = self.calc_deskewed_counts(raw_counts)
        count_vars = self.calc_class_count_vars(raw_counts, deskewed_counts)

        # Filter for parasite classes only
        parasite_count_vars = count_vars[ASEXUAL_PARASITE_CLASS_IDS]
        parasite_count = np.sum(deskewed_counts[ASEXUAL_PARASITE_CLASS_IDS])

        # Compute error
        return np.sqrt(np.sum(parasite_count_vars)) / parasite_count

    def calc_class_count_vars(
        self, raw_counts: npt.NDArray, deskewed_counts: npt.NDArray
    ) -> npt.NDArray:
        """
        Return absolute uncertainty of each class count based on deskewing and Poisson statistics
        See remoscope manuscript for full derivation
        """
        poisson_terms = self.calc_poisson_count_var_terms(raw_counts)
        deskew_terms = self.calc_deskew_count_var_terms(raw_counts)

        class_vars = poisson_terms + deskew_terms

        print(f"POISSON {poisson_terms[ASEXUAL_PARASITE_CLASS_IDS]}")
        print(f"DESKEW {deskew_terms[ASEXUAL_PARASITE_CLASS_IDS]}")
        print(f"REL {class_vars[ASEXUAL_PARASITE_CLASS_IDS]}")

        return class_vars

    def calc_poisson_count_var_terms(self, raw_counts: npt.NDArray) -> npt.NDArray:
        """
        Return absolute uncertainty term of each class count based on Poisson statistics
        See remoscope manuscript for full derivation
        """
        return np.matmul(raw_counts, np.square(self.inv_cmatrix))

    def calc_deskew_count_var_terms(self, raw_counts: npt.NDArray) -> npt.NDArray:
        """
        Return absolute uncertainty term of each class count based on deskewing
        See remoscope manuscript for full derivation
        """
        # Commented out for now because int overflow should not be an issue with bug fixes
        # # TODO does division by 0 cause error?
        # RBC_count = np.sum(raw_counts[RBC_CLASS_IDS])

        # # Use ratio of class relative to RBC count to avoid overflow
        # class_ratios = raw_counts / RBC_count
        # unscaled_err = np.matmul(np.square(class_ratios), np.square(self.inv_cmatrix_std))

        # return unscaled_err * RBC_count **2

        return np.matmul(np.square(raw_counts), np.square(self.inv_cmatrix_std))

    def get_class_stats_str(
        self,
        name: str,
        deskewed_count: float,
        percent_err: float,
    ) -> str:
        """
        Return results string with statistics for individual class
        """
        return f"\t{name.upper()}: {int(deskewed_count)} ({percent_err:.3g}% uncertainty)\n"

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
        deskewed_counts = self.calc_deskewed_counts(raw_counts)

        # Get parasitemia results
        parasitemia = self.calc_parasitemia(deskewed_counts)
        parasitemia_unc = self.calc_parasitemia_rel_err(raw_counts)

        # Get uncertainties
        rel_vars = self.calc_class_count_vars(raw_counts, deskewed_counts)
        percent_errs = np.multiply(np.sqrt(rel_vars), 100)

        base_string = f"\n\tParasitemia: {parasitemia:.3g} ({parasitemia_unc:.3g}% uncertainty)\n\tCompensated class counts:\n"
        class_strings = [
            self.get_class_stats_str(
                class_name,
                deskewed_counts[class_idx],
                percent_errs[class_idx],
            )
            for class_name, class_idx in YOGO_CLASS_IDX_MAP[ASEXUAL_PARASITE_CLASS_IDS].items()
        ]
        return base_string + "".join(class_strings)
