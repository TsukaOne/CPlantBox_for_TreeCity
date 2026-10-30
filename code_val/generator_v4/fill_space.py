"""Fill scenes: soils drawn straight from the ranges of the physical quantities, without profile
types, so the network meets rare combinations and cannot learn a table from profile to roots.

A scrambled Sobol sequence places each new point where the space is still emptiest. Impossible
combinations are not drawn rather than rejected, which keeps that even coverage: the sand is a
share of what the clay leaves, and the density is a position between the loosest and the firmest
density WRB allows for the texture drawn. Layers are soil only; barriers come with profile types.
"""
from functools import cache

import numpy as np
from scipy.stats import qmc

from soil_library.cities import City
from soil_library.compaction import COMPACTION_CLASSES, measure_class_edges
from soil_library.draw import SOIL, DrawnLayer, DrawnProfile

FILL_PROFILE = "fill"
POINT_COUNT_LOG2 = 10
LAYER_COUNT_RANGE = (2, 4)
THICKNESS_RANGE_CM = (10.0, 120.0)
CLAY_RANGE = (0.0, 0.6)
ORGANIC_CARBON_RANGE_PERCENT = (0.0, 5.0)
COARSE_RANGE = (0.0, 0.7)
WATER_SCALE_RANGE = (0.5, 1.3)
WATER_TABLE_PROBABILITY = 0.25
WATER_TABLE_RANGE_CM = (40.0, 250.0)
LAYER_DIMENSIONS = 6
DIMENSIONS = 1 + LAYER_COUNT_RANGE[1] * LAYER_DIMENSIONS + 2


@cache
def build_fill_points(master_seed: int) -> np.ndarray:
    return qmc.Sobol(DIMENSIONS, scramble=True, seed=master_seed).random_base2(POINT_COUNT_LOG2)


def scale(unit: float, bounds: tuple[float, float]) -> float:
    return float(bounds[0] + unit * (bounds[1] - bounds[0]))


def build_fill_layer(units: np.ndarray, top_cm: float, bottom_cm) -> DrawnLayer:
    _, clay_unit, sand_share, carbon_unit, coarse_unit, density_unit = units
    clay = scale(clay_unit, CLAY_RANGE)
    organic_carbon = scale(carbon_unit, ORGANIC_CARBON_RANGE_PERCENT)
    edges = measure_class_edges(clay, organic_carbon)
    density = scale(density_unit, (edges[0], edges[-1]))
    compaction_class = COMPACTION_CLASSES[min(int(np.searchsorted(edges, density)) - 1,
                                              len(COMPACTION_CLASSES) - 1)]
    return DrawnLayer(FILL_PROFILE, "fill layer", SOIL, top_cm, bottom_cm,
                      float(sand_share * (1.0 - clay)), clay, organic_carbon,
                      scale(coarse_unit, COARSE_RANGE), compaction_class, density)


def draw_fill_profile(fill_index: int, city: City, master_seed: int) -> tuple[DrawnProfile, float]:
    """Returns the profile and the factor applied to the city's seasonal water."""
    point = build_fill_points(master_seed)[fill_index]
    fewest, most = LAYER_COUNT_RANGE
    count = min(fewest + int(point[0] * (most - fewest + 1)), most)
    layers, top_cm = [], 0.0
    for index in range(count):
        units = point[1 + index * LAYER_DIMENSIONS:1 + (index + 1) * LAYER_DIMENSIONS]
        bottom_cm = None if index == count - 1 else top_cm + scale(units[0], THICKNESS_RANGE_CM)
        layers.append(build_fill_layer(units, top_cm, bottom_cm))
        top_cm = bottom_cm
    water_unit, table_unit = point[-2:]
    water_table_cm = (scale(table_unit / WATER_TABLE_PROBABILITY, WATER_TABLE_RANGE_CM)
                      if table_unit < WATER_TABLE_PROBABILITY else None)
    return (DrawnProfile(FILL_PROFILE, city.name, tuple(layers), False, water_table_cm),
            scale(water_unit, WATER_SCALE_RANGE))
