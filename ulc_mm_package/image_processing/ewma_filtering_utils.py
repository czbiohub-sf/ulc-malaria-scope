import numpy as np


class EWMAFiltering:
    def __init__(self, alpha: float):
        """Initialize the EWMA filter with a particular alpha and initialization value.

        Usage
        -----
            filter = EWMAFiltering(alpha=0.1)
            filter.set_init_val(10)

            for new_measurement in measurements:
                new_val = filter.update_and_get_val(new_measurement)

        Parameters
        ----------
        alpha : float
            Smoothing factor for the EWMA filter (0 < alpha < 1)
                - lower means more memory/heavier smoothing,
                - higher means more weight/confidence given to new measurements/i.e noisier
        """

        # TODO set this using the setter so that invalid alpha values are rejected
        self._alpha = alpha

    @property
    def alpha(self):
        return self._alpha

    @alpha.setter
    def alpha(self, alpha: float):
        """Set a new alpha value

        Exceptions
        ----------
        ValueError:
            Alpha must be 0 < alpha < 1
        """

        if not 0 < alpha < 1:
            raise ValueError(
                f"Invalid alpha, must be 0 < alpha < 1. Received: {alpha, type(alpha)}"
            )

        self._alpha = alpha

    def set_init_val(self, init_val: float) -> None:
        """Set the initialization value

        Parameters
        ----------
        init_val: float
        """

        self.prev_val = init_val

    @staticmethod
    def _ewma_update_step(prev_val: float, new_val: float, alpha: float) -> float:
        """EWMA calculation step

        Returns
        -------
        float
            Updated value
        """

        return prev_val * (1 - alpha) + new_val * alpha

    def update_and_get_val(self, new_measurement: float) -> float:
        """Pass a new measurement and get the updated prior

        Returns
        -------
        float
            Updated value
        """

        self.prev_val = self._ewma_update_step(
            self.prev_val, new_measurement, self.alpha
        )
        return self.prev_val

    @staticmethod
    def get_halflife_from_smoothing_factor(alpha: float) -> float:
        """Determine the half-life of the filter given its alpha value

        Returns
        -------
        float
            Half-life of filter given a particular alpha
        """

        return -np.log(2) / np.log(1 - alpha)

    def get_adjustment_period_ewma(self) -> int:
        """Get the period at which to take corrective steps (somewhat empirically defined as twice the half-life of the filter).

        Returns
        -------
        float
            Twice the half-life of the EWMA filter given its smoothing factor, alpha.
        """

        half_life = self.get_halflife_from_smoothing_factor(self.alpha)
        return int(round(2 * half_life))
