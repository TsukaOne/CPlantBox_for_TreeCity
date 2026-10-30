"""E1: the twelve profile types in the three cities, with a stop at 2.5 and at 3.0 MPa.

    python3 code_val/sandbox/sandbox_v4_profiles.py --tree my_Picea_abies.xml

Writes output/sandbox_v4/<xml>/profiles.csv, and per configuration a .vti and the .vtp of run 1.
"""
import csv
import os
import sys
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator_v4.build import grow_once_v4
from generator_v4.environment import build_environment_v4
from network.wall_layouts import NO_WALL, WallModule
from sandbox_v4_scene import (GRID, build_sandbox_soil, build_tree_directory, grow_and_measure,
                              load_frozen_scene, parse_tree, write_fields)
from soil_library.cities import CITIES
from soil_library.draw import SOIL
from soil_library.profiles import PROFILES
from soil_v4.water import MEAN_STATE
from visualisation.soil_report import measure_limiting_shares

STOP_THRESHOLDS_MPA = (2.5, 3.0)
NO_WALLS = WallModule(NO_WALL, (), ())
EXPERIMENT = "profiles"


def describe_layers(profile, environment) -> str:
    depths_cm = GRID.measure_layer_depths_cm()
    state = environment.states[MEAN_STATE]
    outside_pit = ~environment.soil.pit_mask
    cells = []
    for layer in profile.layers:
        bottom_cm = GRID.depth_cm if layer.bottom_cm is None else layer.bottom_cm
        inside = ((depths_cm >= layer.top_cm) & (depths_cm < bottom_cm))[:, None, None] & outside_pit
        if layer.kind != SOIL or not inside.any():
            cells.append(f"{layer.name} {layer.top_cm:.0f}-{bottom_cm:.0f}")
            continue
        cells.append(f"{layer.component} {layer.compaction_class} {layer.top_cm:.0f}-{bottom_cm:.0f}:"
                     f" f_se {state.growth_scale[inside].mean():.2f}"
                     f" PR {np.median(state.penetrometer_mpa[inside]):.1f}")
    return " | ".join(cells)


def run_profile_in_city(task: tuple) -> list:
    profile_index, city_index, tree_xml = task
    recipe, city = PROFILES[profile_index], CITIES[city_index]
    configuration = load_frozen_scene(tree_xml)
    directory = build_tree_directory(tree_xml) / EXPERIMENT
    soil_scene = build_sandbox_soil(recipe, city, configuration)
    rows = []
    for stop_mpa in STOP_THRESHOLDS_MPA:
        environment = build_environment_v4(configuration.street, configuration.leaks, soil_scene,
                                           NO_WALLS, stop_mpa, GRID)
        name = f"{recipe.identifier}_{city.name.lower()}_stop_{stop_mpa}"
        probability, measure = grow_and_measure(configuration, environment, grow_once_v4,
                                                directory / name)
        write_fields(directory / f"{name}.vti", environment, probability)
        shares = measure_limiting_shares(environment.soil, environment.states[MEAN_STATE])
        rows.append({"profile": recipe.identifier, "city": city.name, "stop_mpa": stop_mpa,
                     **asdict(measure),
                     **{f"limited_by_{key}": value for key, value in shares.items()},
                     "layers": describe_layers(soil_scene.mosaic.patches[0].profile, environment)})
    return rows


def print_row(row: dict) -> None:
    print(f"{row['profile']} {row['city']:9s} stop {row['stop_mpa']}: mass {row['mass']:.5f}"
          f"  depth max {row['maximum_depth_cm']:5.1f} mean {row['mean_depth_cm']:5.1f}"
          f"  radius {row['mean_radius_cm']:5.1f}  segments {row['segments']:6.0f}"
          f"  stillborn {row['stillborn']}  in barriers {row['barrier_share']:.4f}"
          f"  limited: mech {row['limited_by_bengough']:.2f}"
          f" water {row['limited_by_water_scale']:.2f}"
          f" air {row['limited_by_aeration_scale']:.2f} barrier {row['limited_by_barrier']:.2f}"
          f"\n      {row['layers']}", flush=True)


def main() -> None:
    tree_xml = parse_tree(__doc__)
    directory = build_tree_directory(tree_xml)
    (directory / EXPERIMENT).mkdir(parents=True, exist_ok=True)
    tasks = [(profile, city, tree_xml) for profile in range(len(PROFILES))
             for city in range(len(CITIES))]
    with Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        rows = [row for rows in pool.map(run_profile_in_city, tasks) for row in rows]
    for row in rows:
        print_row(row)
    with open(directory / f"{EXPERIMENT}.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
