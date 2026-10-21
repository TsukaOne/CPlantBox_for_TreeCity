"""One configuration: the complete description of a single training example.

Every archetype is crossed with every obstacle family, then drawn several times
so that no two configurations share the same numbers.
"""
from dataclasses import dataclass

import numpy as np

from obstacles.layouts import (
    OBSTACLE_FAMILIES,
    TREE_PIT_HALF_SIZE_RANGE_CM,
    ObstacleLayout,
    draw_obstacle_layout,
)
from soil.archetypes import ARCHETYPES, PIT_SUBSTRATE_ARCHETYPE
from soil.pit import TREE_PIT_DEPTH_RANGE_CM
from soil.profile import SoilProfile, draw_soil_profile
from tree.attributes import TreeAttributes, draw_tree_attributes
from tree.species import PICEA_ABIES

MONTE_CARLO_RUNS = 50
DRAWS_PER_COMBINATION = 9
MASTER_SEED = 2026
ROOT_SEED_STRIDE = 1000


@dataclass(frozen=True)
class Configuration:
    identifier: int
    soil: SoilProfile
    pit_soil: SoilProfile
    pit_radius_cm: float
    pit_depth_cm: float
    obstacles: ObstacleLayout
    tree: TreeAttributes
    soil_noise_seed: int
    root_seeds: tuple[int, ...]


def build_root_seeds(identifier: int, run_count: int) -> tuple[int, ...]:
    return tuple(identifier * ROOT_SEED_STRIDE + run for run in range(1, run_count + 1))


def draw_configurations(draws_per_combination: int = DRAWS_PER_COMBINATION, monte_carlo_runs: int = MONTE_CARLO_RUNS, master_seed: int = MASTER_SEED,species: str = PICEA_ABIES) -> list[Configuration]:
    configurations = []
    for archetype in ARCHETYPES:
        for family in OBSTACLE_FAMILIES:
            for _ in range(draws_per_combination):
                identifier = len(configurations) + 1
                rng = np.random.default_rng([master_seed, identifier])
                configurations.append(Configuration(
                    identifier=identifier,
                    soil=draw_soil_profile(archetype, rng),
                    pit_soil=draw_soil_profile(PIT_SUBSTRATE_ARCHETYPE, rng),
                    pit_radius_cm=float(rng.uniform(*TREE_PIT_HALF_SIZE_RANGE_CM)),
                    pit_depth_cm=float(rng.uniform(*TREE_PIT_DEPTH_RANGE_CM)),
                    obstacles=draw_obstacle_layout(family, rng),
                    tree=draw_tree_attributes(species, rng),
                    soil_noise_seed=int(rng.integers(1, 2 ** 31)),
                    root_seeds=build_root_seeds(identifier, monte_carlo_runs),
                ))
    return configurations
