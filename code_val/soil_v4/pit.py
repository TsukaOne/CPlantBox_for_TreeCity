"""The planting pit of a v4 scene: its substrate, loose or compacted, and where it stops.

The pit is dug through a surface barrier (asphalt, paving, a supported slab) but never through a
deep one (rock, a buried slab): its bottom is the shallower of its own depth and the first deep
barrier of the profile that dominates the column. A compacted pit stops at FR, never VR, so the
seed never germinates in a soil it cannot leave.
"""
from dataclasses import dataclass, fields

import numpy as np

from grid import VoxelGrid
from soil_library.draw import DEEP_BARRIER, DrawnLayer, DrawnProfile, draw_layer, draw_texture
from soil_library.materials import IMPORTED_TOPSOIL, PIT_SUBSTRATE, TREE_SAND, Material
from soil_library.profiles import LayerRecipe
from soil_v4.column import StaticSoil
from soil_v4.mosaic import ProfileMosaic

PIT_MATERIALS = (IMPORTED_TOPSOIL, PIT_SUBSTRATE, TREE_SAND)
PIT_VARIANTS = {"loose": ("VL", "LO"), "compacted": ("IN", "FR")}


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
