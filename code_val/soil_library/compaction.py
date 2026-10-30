"""WRB packing density classes and the fine-earth bulk density each one allows.

Class boundaries follow IUSS Working Group WRB (2022), annex 1: T - 0.009 x clay %, lowered by
0.03 for every 0.5 % of organic carbon above 1 %. They match the NRCS root-restricting densities.
"""
import numpy as np

COMPACTION_CLASSES = ("VL", "LO", "IN", "FR", "VR")
BOUNDARY_INTERCEPTS_G_CM3 = np.array([1.4, 1.6, 1.8, 2.0])
CLAY_SLOPE_G_CM3_PER_PERCENT = 0.009
ORGANIC_CARBON_THRESHOLD_PERCENT = 1.0
ORGANIC_CARBON_STEP_PERCENT = 0.5
ORGANIC_CARBON_STEP_G_CM3 = 0.03
OUTER_CLASS_WIDTH_G_CM3 = 0.2
PERCENT = 100.0


def measure_class_edges(clay_fraction: float, organic_carbon_percent: float) -> np.ndarray:
    organic_excess = max(0.0, organic_carbon_percent - ORGANIC_CARBON_THRESHOLD_PERCENT)
    shift = (CLAY_SLOPE_G_CM3_PER_PERCENT * clay_fraction * PERCENT
             + ORGANIC_CARBON_STEP_G_CM3 * organic_excess / ORGANIC_CARBON_STEP_PERCENT)
    boundaries = BOUNDARY_INTERCEPTS_G_CM3 - shift
    return np.concatenate([[boundaries[0] - OUTER_CLASS_WIDTH_G_CM3], boundaries,
                           [boundaries[-1] + OUTER_CLASS_WIDTH_G_CM3]])


def measure_class_bounds(compaction_class: str, clay_fraction: float,
                         organic_carbon_percent: float) -> tuple[float, float]:
    edges = measure_class_edges(clay_fraction, organic_carbon_percent)
    index = COMPACTION_CLASSES.index(compaction_class)
    return float(edges[index]), float(edges[index + 1])


def draw_density(compaction_class: str, clay_fraction: float, organic_carbon_percent: float,
                 rng: np.random.Generator) -> float:
    low, high = measure_class_bounds(compaction_class, clay_fraction, organic_carbon_percent)
    return float(rng.uniform(low, high))
