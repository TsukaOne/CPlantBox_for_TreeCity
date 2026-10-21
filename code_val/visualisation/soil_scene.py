"""The v4 soil of a v3 scene, as a .vti to open in ParaView next to the scene's root .vtp.

    python3 code_val/visualisation/soil_scene.py 1001
    python3 code_val/visualisation/soil_scene.py 1001 --profile P08 --city Helsinki --pit compacted
    python3 code_val/visualisation/soil_scene.py 1001 --walls narrow_strip

The tree, pit size, networks and leaks are those of the v3 scene; the soil and the walls are v4.
Without options, the city, profile, pit variant and wall kind are drawn from the scene identifier.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.network_layers import build_network_layers
from generator.scene import MASTER_SEED, build_generator, draw_scene
from grid import VoxelGrid
from network.wall_layouts import WALL_KINDS, draw_wall_kind, draw_wall_module
from paraview import write_voxel_grids
from soil.growth_response import STOPPED_GROWTH_RESISTANCE_MPA
from soil_library.cities import CITIES
from soil_library.profiles import PROFILES
from soil_v4.pit import PIT_VARIANTS
from soil_v4.scene import build_scene_soil, compute_scene_state, draw_soil_scene
from soil_v4.water import MEAN_STATE, list_state_fractions
from visualisation.soil_report import print_scene_report

GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
SOIL_DOMAIN = 6
WALL_DOMAIN = 9
SHOWN_STATES = (MEAN_STATE, "summer")
OUTPUT_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "output" / "soil_v4"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=int)
    parser.add_argument("--profile", choices=[recipe.identifier for recipe in PROFILES])
    parser.add_argument("--city", choices=[city.name for city in CITIES])
    parser.add_argument("--pit", choices=list(PIT_VARIANTS))
    parser.add_argument("--walls", choices=WALL_KINDS)
    return parser.parse_args()


def pick(options: list, wanted, rng: np.random.Generator):
    chosen = options[rng.integers(len(options))]
    return chosen if wanted is None else wanted


def build_fields(soil, states: dict, network) -> dict:
    static = soil.static
    fields = {"patches": np.broadcast_to(soil.weights.argmax(axis=0) + 1.0, GRID.shape),
              "pit": soil.pit_mask, "rootable": static.rootable_fraction,
              "density": static.fine_earth_density_g_cm3, "coarse": static.coarse_fraction,
              "sand": static.sand_fraction, "clay": static.clay_fraction,
              "organic_carbon": static.organic_carbon_percent, "saturated": soil.saturated_fraction,
              "pipes": network.pipe_labels, "leaks": network.leak_plume,
              "backfill": network.backfill_fraction, "walls": soil.wall_fraction}
    for name, state in states.items():
        fields.update({f"f_se_{name}": state.growth_scale,
                       f"resistance_{name}": state.penetrometer_mpa,
                       f"air_{name}": state.air_filled_porosity,
                       f"water_{name}": state.available_water_fraction})
    return {name: np.asarray(values, np.float32) for name, values in fields.items()}


def main() -> None:
    arguments = parse_arguments()
    configuration = draw_scene(arguments.scene, GRID)
    rng = build_generator(MASTER_SEED, arguments.scene, SOIL_DOMAIN)
    city = pick(CITIES, next((c for c in CITIES if c.name == arguments.city), None), rng)
    recipe = pick(PROFILES, next((p for p in PROFILES if p.identifier == arguments.profile), None),
                  rng)
    variant = pick(list(PIT_VARIANTS), arguments.pit, rng)

    scene = draw_soil_scene(city, recipe, configuration.pit_radius_cm, configuration.pit_depth_cm,
                            variant, GRID, rng)
    wall_rng = build_generator(MASTER_SEED, arguments.scene, WALL_DOMAIN)
    wall_kind = draw_wall_kind(wall_rng)
    walls = draw_wall_module(arguments.walls or wall_kind, configuration.street,
                             configuration.pit_radius_cm, configuration.pit_depth_cm, GRID,
                             wall_rng)
    network = build_network_layers(configuration.street, configuration.leaks, GRID)
    soil = build_scene_soil(scene, network, walls.panels, GRID)
    fractions = list_state_fractions(scene.water)
    states = {name: compute_scene_state(soil, scene, network, fractions[name],
                                        STOPPED_GROWTH_RESISTANCE_MPA) for name in SHOWN_STATES}

    print_scene_report(scene, walls, soil, states[MEAN_STATE], GRID)
    name = f"scene_{arguments.scene:05d}_{recipe.identifier}_{city.name.lower()}_{walls.kind}"
    path = OUTPUT_DIRECTORY / f"{name}.vti"
    write_voxel_grids(path, build_fields(soil, states, network), GRID)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
