"""The planting pit of a v4 scene: its substrate, loose or compacted, and where it stops.

The pit is dug through a surface barrier (asphalt, paving, a supported slab) but never through a
deep one (rock, a buried slab): its bottom is the shallower of its own depth and the first deep
barrier of the profile that dominates the column. A compacted pit stops at FR, never VR, but a
dense FR can still pass the stop threshold: the collar always sits in the tree's root ball, the
loose nursery soil it was planted with, so no tree is stillborn whatever the pit.
"""
from dataclasses import dataclass, fields

import numpy as np

from grid import VoxelGrid
from soil_library.compaction import measure_class_bounds
from soil_library.draw import DEEP_BARRIER, SOIL, DrawnLayer, DrawnProfile, draw_layer, draw_texture
from soil_library.materials import IMPORTED_TOPSOIL, PIT_SUBSTRATE, TREE_SAND, Material
from soil_library.profiles import LayerRecipe
from soil_v4.column import StaticSoil
from soil_v4.mosaic import ProfileMosaic

PIT_MATERIALS = (IMPORTED_TOPSOIL, PIT_SUBSTRATE, TREE_SAND)
PIT_VARIANTS = {"loose": ("VL", "LO"), "compacted": ("IN", "FR")}
# A street tree of 18-25 cm girth leaves the nursery with a ball of about 70 cm (ANSI Z60.1, FLL).
ROOT_BALL_RADIUS_CM = 35.0
ROOT_BALL_DEPTH_CM = 45.0
ROOT_BALL_CLASS = "LO"


@dataclass(frozen=True)
class PlantingPit:
    radius_cm: float
    depth_cm: float
    variant: str
    substrate: DrawnLayer


def draw_planting_pit(radius_cm: float, depth_cm: float, variant: str, material: Material,
                      rng: np.random.Generator) -> PlantingPit:
    recipe = LayerRecipe((material,), None, PIT_VARIANTS[variant])
    substrate = draw_layer(material, recipe, 0.0, depth_cm, draw_texture(material, rng), rng)
    return PlantingPit(radius_cm, depth_cm, variant, substrate)


def build_root_ball() -> DrawnLayer:
    material = IMPORTED_TOPSOIL
    clay, organic_carbon = material.clay_fraction.middle, material.organic_carbon_percent.middle
    density = np.mean(measure_class_bounds(ROOT_BALL_CLASS, clay, organic_carbon))
    return DrawnLayer(material.identifier, "nursery root ball", SOIL, 0.0, ROOT_BALL_DEPTH_CM,
                      material.sand_fraction.middle, clay, organic_carbon,
                      material.coarse_fraction.middle, ROOT_BALL_CLASS, float(density))


ROOT_BALL = build_root_ball()


def build_root_ball_mask(pit_mask: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    around_collar = grid.measure_trunk_distances_cm() < ROOT_BALL_RADIUS_CM
    shallow = grid.measure_layer_depths_cm() < ROOT_BALL_DEPTH_CM
    return pit_mask & around_collar[None, :, :] & shallow[:, None, None]


def measure_deep_barrier_top_cm(profile: DrawnProfile) -> float:
    return min((layer.top_cm for layer in profile.layers if layer.kind == DEEP_BARRIER),
               default=np.inf)


def build_pit_mask(pit: PlantingPit, mosaic: ProfileMosaic, weights: np.ndarray,
                   grid: VoxelGrid) -> np.ndarray:
    barrier_tops_cm = np.array([measure_deep_barrier_top_cm(patch.profile) for patch in mosaic.patches])
    bottoms_cm = np.minimum(pit.depth_cm, barrier_tops_cm[weights.argmax(axis=0)])
    inside = grid.measure_trunk_distances_cm() < pit.radius_cm
    return inside[None, :, :] & (grid.measure_layer_depths_cm()[:, None, None] < bottoms_cm[None, :, :])


def apply_pit(field: StaticSoil, pit_soil: StaticSoil, mask: np.ndarray) -> StaticSoil:
    return StaticSoil(**{channel.name: np.where(mask, getattr(pit_soil, channel.name),
                                                getattr(field, channel.name))
                         for channel in fields(StaticSoil)})
