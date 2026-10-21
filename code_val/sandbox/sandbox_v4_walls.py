"""E3: the three wall kinds on P01, P05 and P08 in Brussels.

    python3 code_val/sandbox/sandbox_v4_walls.py --tree my_Picea_abies.xml

For every wall panel, the share of the root mass on its far side (away from the trunk, or outside
the ring of a confined pit) is compared with the same region without any wall. No root node may
end inside a wall or a pipe.
"""
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.build import grow_once
from generator_v4.environment import build_environment_v4
from network.coverage import measure_cell_axes_cm
from network.street import build_frame
from network.wall_layouts import (CONFINED_PIT, FOUNDATION, NARROW_STRIP, NO_WALL, WALL_KINDS,
                                  draw_wall_module)
from sandbox_v4_scene import (GRID, SEED, build_sandbox_soil, build_tree_directory,
                              grow_and_measure, load_frozen_scene, parse_tree, write_fields)
from soil.growth_response import STOPPED_GROWTH_RESISTANCE_MPA
from soil_library.cities import CITIES
from soil_library.profiles import PROFILES

TESTED_PROFILES = ("P01", "P05", "P08")
CITY = "Brussels"
TESTED_KINDS = (NO_WALL, FOUNDATION, NARROW_STRIP, CONFINED_PIT)
EXPERIMENT = "walls"


def build_far_side_mask(panel, bearing_deg: float) -> np.ndarray:
    along, across = build_frame(bearing_deg)
    _, rows, columns = measure_cell_axes_cm(GRID)
    lateral = columns[None, :] * across[0] + rows[:, None] * across[1]
    longitudinal = columns[None, :] * along[0] + rows[:, None] * along[1]
    path = np.asarray(panel.path_cm, float)
    if len(path) > 2:
        half_side_cm = np.abs(path @ along).max()
        far = np.maximum(np.abs(lateral), np.abs(longitudinal)) > half_side_cm
    else:
        panel_lateral_cm = float(path[0] @ across)
        far = lateral * np.sign(panel_lateral_cm) > abs(panel_lateral_cm)
    return np.broadcast_to(far, GRID.shape)


def run_wall_kind(task: tuple) -> tuple:
    profile_name, kind, tree_xml = task
    recipe = next(recipe for recipe in PROFILES if recipe.identifier == profile_name)
    city = next(city for city in CITIES if city.name == CITY)
    configuration = load_frozen_scene(tree_xml)
    directory = build_tree_directory(tree_xml) / EXPERIMENT
    walls = draw_wall_module(kind, configuration.street, configuration.pit_radius_cm,
                             configuration.pit_depth_cm, GRID,
                             np.random.default_rng([SEED, WALL_KINDS.index(kind)]))
    environment = build_environment_v4(configuration.street, configuration.leaks,
                                       build_sandbox_soil(recipe, city, configuration), walls,
                                       STOPPED_GROWTH_RESISTANCE_MPA, GRID)
    name = f"{profile_name}_{kind}"
    probability, measure = grow_and_measure(configuration, environment, grow_once, directory / name)
    write_fields(directory / f"{name}.vti", environment, probability)
    return profile_name, kind, walls, probability, measure


def report(results: list, bearing_deg: float) -> None:
    baselines = {profile: probability for profile, kind, _, probability, _ in results
                 if kind == NO_WALL}
    for profile, kind, walls, probability, measure in results:
        print(f"{profile} {kind:12s} mass {measure.mass:.5f}"
              f"  depth max {measure.maximum_depth_cm:5.1f}"
              f"  intrusions {measure.intrusions or 'none'}  in barriers {measure.barrier_share:.4f}"
              f"  statuses {walls.statuses}")
        for panel in walls.panels:
            far = build_far_side_mask(panel, bearing_deg)
            print(f"      {panel.name}: depth {-panel.bottom_cm:.0f} cm, far-side share"
                  f" {probability[far].sum() / probability.sum():.3f}"
                  f" (without wall {baselines[profile][far].sum() / baselines[profile].sum():.3f})")


def main() -> None:
    tree_xml = parse_tree(__doc__)
    (build_tree_directory(tree_xml) / EXPERIMENT).mkdir(parents=True, exist_ok=True)
    tasks = [(profile, kind, tree_xml) for profile in TESTED_PROFILES for kind in TESTED_KINDS]
    with Pool(min(len(tasks), max(1, (os.cpu_count() or 2) - 1))) as pool:
        results = pool.map(run_wall_kind, tasks)
    report(results, load_frozen_scene(tree_xml).street.bearing_deg)


if __name__ == "__main__":
    main()
