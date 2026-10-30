"""The frozen scene of the v4 sandbox, and what is measured on it.

The tree, pit size, networks, leaks and root seeds are those of v3 scene 1001: only the soil, the
walls and the water change from one configuration to the next. The profile stands alone (no
mosaic), the pit is loose, its substrate and the backfills are drawn with the same seed for every
configuration, and the year is normal: no drought, no runoff. Each configuration grows 20 root
systems with the v3 secondary growth and radius voxelisation. The tree is given with --tree, and
each tree writes in its own folder output/sandbox_v4/<xml>/.
"""
import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.build import grow_ensemble
from generator.scene import SceneConfiguration, draw_scene
from generator_v4.environment import EnvironmentV4, find_pipe_and_wall_intrusions
from grid import VoxelGrid
from paraview import write_voxel_grids
from root_metrics import measure_occupancy_shape
from soil_library.cities import CITIES, City
from soil_library.draw import draw_profile
from soil_library.profiles import PROFILES, ProfileRecipe
from soil_v4.mosaic import single_profile_mosaic
from soil_v4.scene import SoilScene, draw_soil_scene
from soil_v4.water import MEAN_STATE, WaterRegime
from tree.species import secondary_growth_for

SCENE = 1001
GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
SEED = 7
PIT_VARIANT = "loose"
NORMAL_YEAR_FACTOR = 1.0
STILLBORN_SEGMENTS = 50
OUTPUT_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "output" / "sandbox_v4"


@dataclass(frozen=True)
class SandboxMeasure:
    segments: float
    maximum_depth_cm: float
    mass: float
    support: float
    mean_radius_cm: float
    mean_depth_cm: float
    intrusions: dict
    barrier_share: float
    stillborn: bool


def parse_tree(description: str) -> str:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--tree", required=True, metavar="XML",
                        help="CPlantBox XML file (parameters/ folder)")
    return Path(parser.parse_args().tree).name


def build_tree_directory(tree_xml: str) -> Path:
    return OUTPUT_DIRECTORY / Path(tree_xml).stem


def load_frozen_scene(tree_xml: str) -> SceneConfiguration:
    return draw_scene(SCENE, GRID, tree_xml=tree_xml)


def build_normal_year(city: City) -> WaterRegime:
    return WaterRegime(city.seasonal_water_fraction, NORMAL_YEAR_FACTOR, False, False,
                       city.frozen_winter)


def build_sandbox_soil(recipe: ProfileRecipe, city: City,
                       configuration: SceneConfiguration) -> SoilScene:
    profile_rng = np.random.default_rng([SEED, PROFILES.index(recipe), CITIES.index(city)])
    mosaic = single_profile_mosaic(draw_profile(recipe, city, profile_rng))
    scene = draw_soil_scene(city, mosaic, configuration.pit_radius_cm, configuration.pit_depth_cm,
                            PIT_VARIANT, np.random.default_rng(SEED))
    return replace(scene, water=build_normal_year(city))


def grow_and_measure(configuration: SceneConfiguration, environment: EnvironmentV4, grow_run,
                     vtp_directory: Path) -> tuple:
    ensemble = grow_ensemble(configuration, environment, GRID,
                             secondary_growth_for(configuration.tree.species), vtp_directory,
                             grow_run, find_pipe_and_wall_intrusions)
    probability = ensemble.hit_counts["radius"] / len(configuration.root_seeds)
    centreline = ensemble.hit_counts["centreline"]
    in_barrier = environment.soil.static.rootable_fraction <= 0.0
    mean_radius_cm, mean_depth_cm = measure_occupancy_shape(probability, GRID)
    diagnostics = ensemble.diagnostics
    return probability, SandboxMeasure(
        diagnostics["segments_mean"], diagnostics["max_depth_cm_mean"],
        diagnostics["mean_probability"], diagnostics["support_voxel_fraction"],
        mean_radius_cm, mean_depth_cm, diagnostics["intrusions"],
        float(centreline[in_barrier].sum() / max(centreline.sum(), 1)),
        diagnostics["segments_mean"] < STILLBORN_SEGMENTS)


def write_fields(path: Path, environment: EnvironmentV4, probability: np.ndarray) -> None:
    mean = environment.states[MEAN_STATE]
    write_voxel_grids(path, {"occupancy": probability.astype(np.float32),
                             "f_se": mean.growth_scale,
                             "resistance": mean.penetrometer_mpa.astype(np.float32),
                             "rootable": environment.soil.static.rootable_fraction.astype(np.float32),
                             "walls": environment.soil.wall_fraction.astype(np.float32),
                             "pipes": environment.network.pipe_labels}, GRID)
