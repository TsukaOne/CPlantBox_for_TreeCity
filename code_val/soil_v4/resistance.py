"""Penetration resistance from matric potential, saturation and bulk density.

Whalley et al. (2007), Geoderma 137: 370: log10 Q = 1.26 + 0.35 log10(|psi| S) + 0.93 rho, with
Q and psi in kPa and rho in g/cm3. The coefficients are second-hand and still to be checked
against the paper. The model was fitted between -20 and -300 kPa; outside, it extrapolates.
"""
import numpy as np

INTERCEPT = 1.26
SUCTION_SLOPE = 0.35
DENSITY_SLOPE = 0.93
KILOPASCALS_PER_CENTIMETRE_OF_HEAD = 0.0980665
KILOPASCALS_PER_MEGAPASCAL = 1000.0
# A saturated soil has no suction: the floor keeps the logarithm finite and leaves the density
# term alone, which is what makes a wet compacted soil still resist.
MINIMUM_EFFECTIVE_STRESS_KPA = 1.0
MAXIMUM_RESISTANCE_MPA = 5.0


def convert_head_to_suction_kpa(pressure_head_cm: np.ndarray) -> np.ndarray:
    return np.abs(pressure_head_cm) * KILOPASCALS_PER_CENTIMETRE_OF_HEAD


def estimate_penetration_resistance(pressure_head_cm: np.ndarray, saturation: np.ndarray,
                                    density_g_cm3: np.ndarray, deviation_log10: np.ndarray) -> np.ndarray:
    stress_kpa = np.maximum(convert_head_to_suction_kpa(pressure_head_cm) * saturation,
                            MINIMUM_EFFECTIVE_STRESS_KPA)
    log_resistance_kpa = (INTERCEPT + SUCTION_SLOPE * np.log10(stress_kpa)
                          + DENSITY_SLOPE * density_g_cm3 + deviation_log10)
    return np.minimum(10.0 ** log_resistance_kpa / KILOPASCALS_PER_MEGAPASCAL, MAXIMUM_RESISTANCE_MPA)
