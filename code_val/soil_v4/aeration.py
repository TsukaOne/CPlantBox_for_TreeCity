"""Air-filled porosity and the growth it allows.

The porosity comes from the particle density, 1 - rho/2.65, not from Rosetta's theta_s: theta_s
sits close to the field capacity of a loam and would leave a loose loam with 3 % air after
drainage. A saturated cell has no air at all. Roots stop below 5 % air and grow freely above 12 %
(Grable & Siemer 1968 place the critical range at 10 to 16 %).
"""
import numpy as np

PARTICLE_DENSITY_G_CM3 = 2.65
STOPPED_GROWTH_AIR_FRACTION = 0.05
FREE_GROWTH_AIR_FRACTION = 0.12


def measure_air_filled_porosity(density_g_cm3: np.ndarray, moisture: np.ndarray,
                                saturated_fraction: np.ndarray) -> np.ndarray:
    porosity = 1.0 - density_g_cm3 / PARTICLE_DENSITY_G_CM3
    return np.maximum(porosity - moisture, 0.0) * (1.0 - saturated_fraction)


def apply_aeration(air_filled_porosity: np.ndarray) -> np.ndarray:
    span = FREE_GROWTH_AIR_FRACTION - STOPPED_GROWTH_AIR_FRACTION
    return np.clip((air_filled_porosity - STOPPED_GROWTH_AIR_FRACTION) / span, 0.0, 1.0)
