"""The v4 soil of a scene: drawn once, then built into fields.

The order matters. The static soil is built before the pit, the pit before the backfills (a
trench crosses the pit like any other soil), the root ball after them (no trench runs through a
planted tree's collar), the walls last, and Rosetta runs once on the result. The water comes
last and is redone for every water state: sealing, runoff into the pit, then the leaks.
"""
from dataclasses import dataclass, replace

import numpy as np
import plantbox.functional.van_genuchten as vg

from generator.network_layers import NetworkLayers
from grid import VoxelGrid
from network.wall_measures import measure_wall_fraction
from soil.mosaic import build_patch_weights
from soil_library.cities import City
from soil_v4.column import StaticSoil, convert_layer_to_soil
from soil_v4.field import blend_patches, build_static_field
from soil_v4.fills import Backfills, apply_fills, draw_backfills
from soil_v4.mosaic import ProfileMosaic
from soil_v4.pit import (PIT_MATERIALS, ROOT_BALL, PlantingPit, apply_pit, build_pit_mask,
                         build_root_ball_mask, draw_planting_pit)
from soil_v4.retention import estimate_retention
from soil_v4.state import SoilState, compute_soil_state
from soil_v4.water import (WaterRegime, apply_leaks, apply_runoff, build_available_water,
                           build_saturated_fraction, draw_water_regime)

SEED_LIMIT = 2 ** 31
CLOSED_WALL_FRACTION = 0.5


@dataclass(frozen=True)
class SoilScene:
    city: str
    mosaic: ProfileMosaic
    pit: PlantingPit
    backfills: Backfills
    water: WaterRegime
    noise_seed: int


@dataclass
class SceneSoil:
    static: StaticSoil
    retention: vg.Parameters
    weights: np.ndarray
    pit_mask: np.ndarray
    sealed_share: np.ndarray
    saturated_fraction: np.ndarray
    wall_fraction: np.ndarray


def draw_soil_scene(city: City, mosaic: ProfileMosaic, pit_radius_cm: float, pit_depth_cm: float,
                    pit_variant: str, rng: np.random.Generator) -> SoilScene:
    pit_material = PIT_MATERIALS[rng.integers(len(PIT_MATERIALS))]
    pit = draw_planting_pit(pit_radius_cm, pit_depth_cm, pit_variant, pit_material, rng)
    sealed_surface = mosaic.patches[0].profile.sealed_surface
    return SoilScene(city.name, mosaic, pit, draw_backfills(pit_material, rng),
                     draw_water_regime(city, sealed_surface, rng), int(rng.integers(1, SEED_LIMIT)))


def build_scene_soil(scene: SoilScene, network: NetworkLayers, wall_panels: tuple,
                     grid: VoxelGrid) -> SceneSoil:
    weights = build_patch_weights(scene.mosaic, grid)
    field = build_static_field(scene.mosaic, weights, grid, np.random.default_rng(scene.noise_seed))
    pit_mask = build_pit_mask(scene.pit, scene.mosaic, weights, grid)
    field = apply_pit(field, convert_layer_to_soil(scene.pit.substrate), pit_mask)
    field = apply_fills(field, network.shapes.fills, network.coverages, scene.backfills)
    field = apply_pit(field, convert_layer_to_soil(ROOT_BALL), build_root_ball_mask(pit_mask, grid))
    wall_fraction = measure_wall_fraction(wall_panels, grid)
    # A 15-25 cm pit wall seldom fills a voxel: scaling alone let the roots that slip past
    # CPlantBox's rejection keep growing inside it.
    open_fraction = np.where(wall_fraction >= CLOSED_WALL_FRACTION, 0.0, 1.0 - wall_fraction)
    field = replace(field, rootable_fraction=field.rootable_fraction * open_fraction)

    sealed = np.array([patch.profile.sealed_surface for patch in scene.mosaic.patches], float)
    outside_pit = grid.measure_trunk_distances_cm() >= scene.pit.radius_cm
    sealed_share = np.broadcast_to(np.einsum("n,nrc->rc", sealed, weights) * outside_pit, grid.shape)
    saturated = blend_patches([build_saturated_fraction(patch.profile.water_table_depth_cm, grid)
                               for patch in scene.mosaic.patches], weights)
    return SceneSoil(field, estimate_retention(field), weights, pit_mask, sealed_share, saturated,
                     wall_fraction)


def compute_scene_state(soil: SceneSoil, scene: SoilScene, network: NetworkLayers,
                        state_fraction: float, stopped_growth_mpa: float) -> SoilState:
    available = build_available_water(state_fraction, soil.sealed_share)
    if scene.water.runoff:
        available = apply_runoff(available, soil.pit_mask)
    available = apply_leaks(available, network.sources)
    return compute_soil_state(soil.static, soil.retention, available, soil.saturated_fraction,
                              stopped_growth_mpa)
