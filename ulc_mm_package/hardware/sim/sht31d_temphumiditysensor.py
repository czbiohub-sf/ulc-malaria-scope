from typing import Tuple


class SHT3X:
    """Simulated temperature/humidity sensor returning dummy values"""

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        return 25.0, 1.0

    def stop(self):
        ...
