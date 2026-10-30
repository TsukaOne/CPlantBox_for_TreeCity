"""The water a scene sees, drawn from its city and independent of its texture.

The city gives four seasonal states as fractions of the available water capacity; the year is
dry, normal or wet; a drought module dries the summer; a sealed surface lets less water in; a
runoff module (sealed profiles only) waters the planting pit. The mean state averages the four
seasons. A water table saturates every cell below it. All factors are estimates.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from grid import VoxelGrid
from soil_library.cities import City

SEASONS = ("spring", "summer", "autumn", "winter")
MEAN_STATE = "mean"
SUMMER_INDEX = SEASONS.index("summer")
YEAR_FACTORS = (0.75, 1.0, 1.15)
YEAR_PROBABILITIES = (0.25, 0.5, 0.25)
DROUGHT_PROBABILITY = 0.15
DROUGHT_SUMMER_FACTOR = 0.5
RUNOFF_PROBABILITY = 0.15
RUNOFF_PIT_INCREMENT = 0.25
SEALED_SURFACE_FACTOR = 0.75


@dataclass(frozen=True)
class WaterRegime:
    seasonal_water_fraction: tuple[float, ...]
    year_factor: float
    drought: bool
    runoff: bool
    frozen_winter: bool


def draw_water_regime(city: City, sealed_surface: bool, rng: np.random.Generator) -> WaterRegime:
    year_factor = YEAR_FACTORS[rng.choice(len(YEAR_FACTORS), p=YEAR_PROBABILITIES)]
    drought = bool(rng.random() < DROUGHT_PROBABILITY)
    runoff = bool(sealed_surface and rng.random() < RUNOFF_PROBABILITY)
    seasonal = np.array(city.seasonal_water_fraction) * year_factor
    if drought:
        seasonal[SUMMER_INDEX] *= DROUGHT_SUMMER_FACTOR
    return WaterRegime(tuple(np.clip(seasonal, 0.0, 1.0).tolist()), year_factor, drought, runoff,
                       city.frozen_winter)


def list_state_fractions(regime: WaterRegime) -> dict:
    states = dict(zip(SEASONS, regime.seasonal_water_fraction))
    states[MEAN_STATE] = float(np.mean(regime.seasonal_water_fraction))
    return states


def build_available_water(state_fraction: float, sealed_share) -> np.ndarray:
    return np.clip(state_fraction * (1.0 - (1.0 - SEALED_SURFACE_FACTOR) * np.asarray(sealed_share)),
                   0.0, 1.0)


def apply_runoff(available_water: np.ndarray, pit_mask: np.ndarray) -> np.ndarray:
    return np.where(pit_mask, np.minimum(available_water + RUNOFF_PIT_INCREMENT, 1.0), available_water)


def apply_leaks(available_water: np.ndarray, sources: tuple) -> np.ndarray:
    """A leak only adds water: the resistance and the air follow from it in compute_soil_state."""
    for ramp, target_fraction in sources:
        available_water = available_water + (target_fraction - available_water) * ramp
    return available_water


def build_saturated_fraction(water_table_depth_cm: Optional[float], grid: VoxelGrid) -> np.ndarray:
    if water_table_depth_cm is None:
        return np.zeros(grid.depth_cells)
    cell_bottoms_cm = (np.arange(grid.depth_cells) + 1.0) * grid.cell_height_cm
    return np.clip((cell_bottoms_cm - water_table_depth_cm) / grid.cell_height_cm, 0.0, 1.0)
