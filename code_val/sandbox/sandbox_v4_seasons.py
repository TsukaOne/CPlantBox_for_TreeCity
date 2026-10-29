"""E2: does a cycle of four seasons grow a different root system than the mean water state?

    python3 code_val/sandbox/sandbox_v4_seasons.py --tree my_Picea_abies.xml

Every configuration is grown five times: the mean state; the mean state with 20 other root seeds,
which sets the noise floor; the season cycle; the cycle with a stopped winter; and the stopped
winter compensated by growing 4/3 faster the rest of the year. Each is compared with the mean
state by the overlap of the occupancy maps, 2 sum(a b) / (sum(a^2) + sum(b^2)), which is 1 for
identical maps. Rule: keep the mean state where the cycle stays within the noise floor and moves
the mean depth by less than one cell.
"""
import os
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.build import measure_plant
from generator_v4.build import grow_once_v4
from generator_v4.environment import build_environment_v4
from network.wall_layouts import NO_WALL, WallModule
from sandbox_v4_scene import (GRID, build_sandbox_soil, build_tree_directory, grow_and_measure,
                              load_frozen_scene, parse_tree)
from soil.growth_response import STOPPED_GROWTH_RESISTANCE_MPA
from soil_library.cities import CITIES
from soil_library.profiles import PROFILES
from soil_v4.water import SEASONS
from tree.growth import build_soil_grid
from tree.seasons import SeasonalGrids, grow_plant_through_seasons

TESTED_PROFILES = ("P01", "P03", "P05", "P08", "P12")
TESTED_CITIES = ("Brussels", "Helsinki")
WINTER = SEASONS.index("winter")
COMPENSATION = 4.0 / 3.0
NOISE_SEED_OFFSET = 500
CYCLES = {"cycle": (False, 1.0), "winter stopped": (True, 1.0),
          "winter stopped, x4/3": (True, COMPENSATION)}
NO_WALLS = WallModule(NO_WALL, (), ())
EXPERIMENT = "seasons"


def measure_overlap(reference: np.ndarray, other: np.ndarray) -> float:
    return float(2.0 * np.sum(reference * other) / (np.sum(reference ** 2) + np.sum(other ** 2)))


def build_cycle_grids(environment, winter_stopped: bool, growth_factor: float) -> SeasonalGrids:
    states = [environment.states[season] for season in SEASONS]
    scales = [np.zeros(GRID.shape, np.float32) if winter_stopped and index == WINTER
              else state.growth_scale * growth_factor for index, state in enumerate(states)]
    return SeasonalGrids(tuple(build_soil_grid(scale, GRID) for scale in scales),
                         tuple(build_soil_grid(state.angle_scale, GRID) for state in states))


def build_seasonal_grower(grids: SeasonalGrids):
    def grow_through_seasons(configuration, environment, grid, seed, parameters, vtp_path):
        plant = grow_plant_through_seasons(environment.geometry, grids, seed,
                                           configuration.tree.age_years,
                                           Path(configuration.tree_xml), None,
                                           vtp_path)
        return measure_plant(plant, grid, parameters)
    return grow_through_seasons


def describe(label: str, reference, measure, probability) -> str:
    return (f"    {label:22s} overlap {measure_overlap(reference[0], probability):.3f}"
            f"  mass {measure.mass / reference[1].mass:.2f}"
            f"  mean depth {measure.mean_depth_cm - reference[1].mean_depth_cm:+6.1f} cm"
            f"  radius {measure.mean_radius_cm - reference[1].mean_radius_cm:+6.1f} cm")


def run_cycles(task: tuple) -> str:
    profile_name, city_name, tree_xml = task
    recipe = next(recipe for recipe in PROFILES if recipe.identifier == profile_name)
    city = next(city for city in CITIES if city.name == city_name)
    configuration = load_frozen_scene(tree_xml)
    environment = build_environment_v4(configuration.street, configuration.leaks,
                                       build_sandbox_soil(recipe, city, configuration), NO_WALLS,
                                       STOPPED_GROWTH_RESISTANCE_MPA, GRID)
    directory = (build_tree_directory(tree_xml) / EXPERIMENT
                 / f"{recipe.identifier}_{city.name.lower()}")
    reference = grow_and_measure(configuration, environment, grow_once_v4, directory / "mean")
    other_seeds = replace(configuration, root_seeds=tuple(seed + NOISE_SEED_OFFSET
                                                          for seed in configuration.root_seeds))
    probability, measure = grow_and_measure(other_seeds, environment, grow_once_v4,
                                            directory / "other_seeds")
    lines = [f"{recipe.identifier} {city.name}: mean state mass {reference[1].mass:.5f},"
             f" mean depth {reference[1].mean_depth_cm:.1f} cm",
             describe("mean, other seeds", reference, measure, probability)]
    for label, (winter_stopped, factor) in CYCLES.items():
        grower = build_seasonal_grower(build_cycle_grids(environment, winter_stopped, factor))
        probability, measure = grow_and_measure(configuration, environment, grower,
                                                directory / label.replace(" ", "_"))
        lines.append(describe(label, reference, measure, probability))
    return "\n".join(lines)


def main() -> None:
    tree_xml = parse_tree(__doc__)
    (build_tree_directory(tree_xml) / EXPERIMENT).mkdir(parents=True, exist_ok=True)
    tasks = [(profile, city, tree_xml) for profile in TESTED_PROFILES for city in TESTED_CITIES]
    with Pool(min(len(tasks), max(1, (os.cpu_count() or 2) - 1))) as pool:
        for report in pool.map(run_cycles, tasks):
            print(report, flush=True)


if __name__ == "__main__":
    main()
