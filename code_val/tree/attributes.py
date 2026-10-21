"""Tree attributes.

Species and age drive CPlantBox. Diameter, height and crown depth do not: they
exist only as conditioning inputs, estimated from age by the allometries of the
specification. Replace them once Team 2 supplies real measurements.
"""
from dataclasses import dataclass

import numpy as np


DAYS_PER_YEAR = 365
AGE_RANGE_YEARS = (5.0, 120.0)  # au-dela de 60 ans le XML est extrapole

DBH_COEFFICIENT = 1.2
DBH_AGE_EXPONENT = 0.85
DBH_RELATIVE_SPREAD = 0.15
HEIGHT_BASE_M = 1.3
HEIGHT_INCREMENT_M = 25.0
HEIGHT_RATE_PER_CM = 0.035
CROWN_DEPTH_FRACTION = 0.6


@dataclass(frozen=True)
class TreeAttributes:
    species: str
    age_years: float
    dbh_cm: float
    height_m: float
    crown_depth_m: float


def estimate_dbh_cm(age_years: float, rng: np.random.Generator) -> float:
    nominal = DBH_COEFFICIENT * age_years ** DBH_AGE_EXPONENT
    return float(nominal * (1.0 + rng.uniform(-DBH_RELATIVE_SPREAD, DBH_RELATIVE_SPREAD)))


def estimate_height_m(dbh_cm: float) -> float:
    return float(HEIGHT_BASE_M + HEIGHT_INCREMENT_M * (1.0 - np.exp(-HEIGHT_RATE_PER_CM * dbh_cm)))


def estimate_crown_depth_m(height_m: float) -> float:
    return CROWN_DEPTH_FRACTION * height_m


def draw_tree_attributes(species: str, rng: np.random.Generator) -> TreeAttributes:
    age_years = float(rng.uniform(*AGE_RANGE_YEARS))
    dbh_cm = estimate_dbh_cm(age_years, rng)
    height_m = estimate_height_m(dbh_cm)
    return TreeAttributes(species, age_years, dbh_cm, height_m, estimate_crown_depth_m(height_m))
