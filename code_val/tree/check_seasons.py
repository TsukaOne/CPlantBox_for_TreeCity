"""Check the seasonal grower against grow_plant on the environment of a v3 scene.

    python3 code_val/tree/check_seasons.py

Four identical seasons, wired as four distinct grid objects, must give exactly the segments of
grow_plant. Stopping growth (f_se = 0) in some seasons must then shorten the root system, and
stopping all of them must leave nothing.
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.environment import build_environment
from generator.scene import draw_scene
from grid import VoxelGrid
from tree.growth import build_soil_grid, extract_root_system, grow_plant
from tree.seasons import SEASON_COUNT, SeasonalGrids, grow_plant_through_seasons

GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
SCENE = 1001
SEEDS = range(1, 11)
EQUIVALENCE_AGE_YEARS = 40.0
AGES_YEARS = (5.0, 40.0)
STOPPED_SEASONS = {"winter stopped": (3,), "three seasons stopped": (1, 2, 3),
                   "all seasons stopped": (0, 1, 2, 3)}


def build_seasonal_grids(environment, stopped: tuple) -> SeasonalGrids:
    stopped_scale = np.zeros(GRID.shape, np.float32)
    scales = [stopped_scale if season in stopped else environment.growth_scale
              for season in range(SEASON_COUNT)]
    elongation = tuple(build_soil_grid(scale, GRID) for scale in scales)
    angle = tuple(build_soil_grid(environment.angle_scale, GRID) for _ in range(SEASON_COUNT))
    return SeasonalGrids(elongation, angle)


def measure_length_cm(segments: np.ndarray) -> float:
    return float(np.linalg.norm(segments[:, 3:] - segments[:, :3], axis=1).sum())


def grow_reference(environment, seed: int, age_years: float) -> np.ndarray:
    plant = grow_plant(environment.geometry, environment.elongation_grid, seed, age_years,
                       angle_grid=environment.angle_grid, water_lookup=environment.water_lookup)
    return extract_root_system(plant).segments


def grow_seasonal(environment, grids: SeasonalGrids, seed: int, age_years: float) -> np.ndarray:
    plant = grow_plant_through_seasons(environment.geometry, grids, seed, age_years,
                                       environment.water_lookup, None)
    return extract_root_system(plant).segments


def check_equivalence(environment) -> None:
    identical = build_seasonal_grids(environment, ())
    matches, reference_seconds, seasonal_seconds = 0, 0.0, 0.0
    for seed in SEEDS:
        started = time.perf_counter()
        reference = grow_reference(environment, seed, EQUIVALENCE_AGE_YEARS)
        reference_seconds += time.perf_counter() - started
        started = time.perf_counter()
        seasonal = grow_seasonal(environment, identical, seed, EQUIVALENCE_AGE_YEARS)
        seasonal_seconds += time.perf_counter() - started
        matches += reference.shape == seasonal.shape and np.array_equal(reference, seasonal)
    print(f"four identical seasons give the segments of grow_plant: {matches}/{len(SEEDS)} seeds")
    print(f"time per plant at {EQUIVALENCE_AGE_YEARS:.0f} years: grow_plant"
          f" {reference_seconds / len(SEEDS):.2f} s, seasonal {seasonal_seconds / len(SEEDS):.2f} s")


def report_stopped_seasons(environment) -> None:
    for age_years in AGES_YEARS:
        reference = np.mean([measure_length_cm(grow_reference(environment, seed, age_years))
                             for seed in SEEDS])
        print(f"age {age_years:.0f} years, reference root length {reference:.0f} cm")
        for label, stopped in STOPPED_SEASONS.items():
            grids = build_seasonal_grids(environment, stopped)
            ratios = np.array([measure_length_cm(grow_seasonal(environment, grids, seed, age_years))
                               for seed in SEEDS]) / reference
            print(f"  {label}: {ratios.mean():.2f} of the reference (seed spread {ratios.std():.2f})")


if __name__ == "__main__":
    scene_environment = build_environment(draw_scene(SCENE, GRID), GRID)
    check_equivalence(scene_environment)
    report_stopped_seasons(scene_environment)
