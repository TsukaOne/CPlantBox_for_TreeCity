""" All the code to generate a scene, including the tree, the pit, the soil, the street and the leaks.
"""
from dataclasses import dataclass

import numpy as np

from grid import VoxelGrid
from network.leaks import JointLeak, build_scene_leaks
from network.street import StreetScene, draw_street_scene
from soil.archetypes import ARCHETYPES, PIT_SUBSTRATE_ARCHETYPE
from soil.mosaic import SoilMosaic, draw_soil_mosaic
from soil.pit import TREE_PIT_DEPTH_RANGE_CM
from soil.profile import SoilProfile, draw_soil_profile
from tree.attributes import TreeAttributes, draw_tree_attributes
from tree.species import identify_species

SCHEMA_VERSION = "v3"
MASTER_SEED = 20260922
SCENE_COUNT = 2000
MONTE_CARLO_RUNS = 20
ROOT_SEED_STRIDE = 1000
TREE_PIT_RADIUS_RANGE_CM = (50.0, 150.0)

TREE, PIT, SOIL, STREET, NOISE = 1, 2, 3, 4, 5


@dataclass(frozen=True)
class SceneConfiguration:
    identifier: int
    tree: TreeAttributes
    pit_radius_cm: float
    pit_depth_cm: float
    pit_soil: SoilProfile
    soil: SoilMosaic
    street: StreetScene
    leaks: tuple[JointLeak, ...]
    soil_noise_seed: int
    root_seeds: tuple[int, ...]
    tree_xml: str


def build_generator(master_seed: int, identifier: int, domain: int) -> np.random.Generator:
    return np.random.default_rng([master_seed, identifier, domain])


def draw_scene(identifier: int, grid: VoxelGrid, runs: int = MONTE_CARLO_RUNS,
               master_seed: int = MASTER_SEED,
               *, tree_xml: str) -> SceneConfiguration:
    """The species only changes the tree attributes: soil, pit, street and seeds are drawn from
    independent streams, so the same identifier is the same scene for every species."""
    pit_rng = build_generator(master_seed, identifier, PIT)
    pit_radius_cm = float(pit_rng.uniform(*TREE_PIT_RADIUS_RANGE_CM))
    pit_depth_cm = float(pit_rng.uniform(*TREE_PIT_DEPTH_RANGE_CM))

    soil_rng = build_generator(master_seed, identifier, SOIL)
    primary = ARCHETYPES[soil_rng.integers(len(ARCHETYPES))]

    street_rng = build_generator(master_seed, identifier, STREET)
    street = draw_street_scene(pit_radius_cm, pit_depth_cm, grid, street_rng)

    return SceneConfiguration(
        identifier=identifier,
        tree=draw_tree_attributes(identify_species(tree_xml), build_generator(master_seed, identifier, TREE)),
        pit_radius_cm=pit_radius_cm,
        pit_depth_cm=pit_depth_cm,
        pit_soil=draw_soil_profile(PIT_SUBSTRATE_ARCHETYPE, pit_rng),
        soil=draw_soil_mosaic(primary, grid, soil_rng),
        street=street,
        leaks=build_scene_leaks(street.utilities, street_rng),
        soil_noise_seed=int(build_generator(master_seed, identifier, NOISE).integers(1, 2 ** 31)),
        root_seeds=tuple(identifier * ROOT_SEED_STRIDE + run for run in range(1, runs + 1)),
        tree_xml=tree_xml,
    )


def draw_scenes(count: int, grid: VoxelGrid, runs: int = MONTE_CARLO_RUNS,
                master_seed: int = MASTER_SEED,
                *, tree_xml: str) -> list:
    return [draw_scene(identifier, grid, runs, master_seed, tree_xml=tree_xml)
            for identifier in range(1, count + 1)]
