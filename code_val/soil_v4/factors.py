"""What CPlantBox reads: the elongation scale f_se and the lateral angle scale f_sa.

The mechanical ramp is Bengough et al. (2011), free below 0.5 MPa, with the stop threshold left
open: 2.5 MPa comes from crops, trees may push to about 3 MPa. The factors multiply, as in v3;
a cell covered by a barrier loses the share it covers.
"""
import numpy as np

from soil.growth_response import FREE_GROWTH_RESISTANCE_MPA, MINIMUM_ANGLE_SCALE


def apply_mechanical_impedance(penetrometer_mpa: np.ndarray, stopped_growth_mpa: float) -> np.ndarray:
    span = stopped_growth_mpa - FREE_GROWTH_RESISTANCE_MPA
    return np.clip((stopped_growth_mpa - penetrometer_mpa) / span, 0.0, 1.0)


def compute_growth_scale(bengough: np.ndarray, water_scale: np.ndarray, aeration_scale: np.ndarray,
                         rootable_fraction: np.ndarray) -> np.ndarray:
    return (bengough * water_scale * aeration_scale * rootable_fraction).astype(np.float32)


def compute_angle_scale(bengough: np.ndarray) -> np.ndarray:
    return (MINIMUM_ANGLE_SCALE + (1.0 - MINIMUM_ANGLE_SCALE) * bengough).astype(np.float32)
