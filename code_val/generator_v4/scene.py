"""A v4 scene: the v3 scene of the same identifier, with a v4 soil and walls.

The tree, the pit size, the street, the leaks and the root seeds are taken from generator.scene,
so scene k of v4 is paired with scene k of v3: a difference between the two comes from the soil,
the walls and the stop threshold alone. The new draws live in their own random streams.
"""
from dataclasses import dataclass, replace

import numpy as np

from generator.scene import MASTER_SEED, MONTE_CARLO_RUNS, build_generator, draw_scene
from generator_v4.design import FILL, SceneSlot, assign_slot
from generator_v4.fill_space import draw_fill_profile
from grid import VoxelGrid
from network.street import StreetScene
from network.wall_layouts import WallModule, draw_wall_kind, draw_wall_module
from soil_library.cities import CITIES
from soil_library.profiles import PROFILES
from soil_v4.mosaic import draw_profile_mosaic, single_profile_mosaic
from soil_v4.scene import SoilScene, draw_soil_scene
from tree.attributes import TreeAttributes

SCHEMA_VERSION = "v4"
PROFILE, SOIL, WALL = 6, 7, 9


@dataclass(frozen=True)
class SceneConfigurationV4:
    identifier: int
    slot: SceneSlot
    tree: TreeAttributes
    pit_radius_cm: float
    pit_depth_cm: float
    soil: SoilScene
    walls: WallModule
    street: StreetScene
    leaks: tuple
    root_seeds: tuple
    tree_xml: str


def draw_soil(slot: SceneSlot, pit_radius_cm: float, pit_depth_cm: float, identifier: int,
              grid: VoxelGrid, master_seed: int) -> SoilScene:
    city = next(city for city in CITIES if city.name == slot.city)
    soil_rng = build_generator(master_seed, identifier, SOIL)
    if slot.kind != FILL:
        recipe = next(recipe for recipe in PROFILES if recipe.identifier == slot.profile)
        profile_rng = build_generator(master_seed, identifier, PROFILE)
        mosaic = draw_profile_mosaic(recipe, city, grid, profile_rng)
        return draw_soil_scene(city, mosaic, pit_radius_cm, pit_depth_cm, slot.pit_variant, soil_rng)

    profile, water_factor = draw_fill_profile(slot.fill_index, city, master_seed)
    scene = draw_soil_scene(city, single_profile_mosaic(profile), pit_radius_cm, pit_depth_cm,
                            slot.pit_variant, soil_rng)
    seasons = np.clip(np.array(scene.water.seasonal_water_fraction) * water_factor, 0.0, 1.0)
    return replace(scene, water=replace(scene.water, seasonal_water_fraction=tuple(seasons.tolist())))


def draw_scene_v4(identifier: int, grid: VoxelGrid, runs: int = MONTE_CARLO_RUNS,
                  master_seed: int = MASTER_SEED, *, tree_xml: str) -> SceneConfigurationV4:
    paired = draw_scene(identifier, grid, runs, master_seed, tree_xml=tree_xml)
    slot = assign_slot(identifier, master_seed)
    wall_rng = build_generator(master_seed, identifier, WALL)
    walls = draw_wall_module(draw_wall_kind(wall_rng), paired.street, paired.pit_radius_cm,
                             paired.pit_depth_cm, grid, wall_rng)
    return SceneConfigurationV4(
        identifier=identifier, slot=slot, tree=paired.tree,
        pit_radius_cm=paired.pit_radius_cm, pit_depth_cm=paired.pit_depth_cm,
        soil=draw_soil(slot, paired.pit_radius_cm, paired.pit_depth_cm, identifier, grid,
                       master_seed),
        walls=walls, street=paired.street, leaks=paired.leaks, root_seeds=paired.root_seeds,
        tree_xml=tree_xml)
