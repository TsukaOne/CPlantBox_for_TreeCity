"""The static soil of a scene: one column per patch, blended by the patch weights, then noised.

Blending keeps a transition voxel between two real soils, as in v3. Two shared noise fields
follow v3 too, one for compaction and one for texture, but compaction now moves the density
only, by 3 % instead of 8 %: the resistance follows 10^(0.93 rho), so 8 % on the density would
swing it by about 30 %.
"""
from dataclasses import fields

import numpy as np

from grid import VoxelGrid
from soil.field import NOISE_AMPLITUDE, build_smooth_noise
from soil_v4.column import StaticSoil, build_column
from soil_v4.mosaic import ProfileMosaic

COMPACTION_NOISE_AMPLITUDE = 0.03
TEXTURE_NOISE_AMPLITUDE = NOISE_AMPLITUDE
DENSITY_LIMITS_G_CM3 = (0.5, 2.3)


def blend_patches(column_values: list, weights: np.ndarray) -> np.ndarray:
    return np.einsum("nd,nrc->drc", np.stack(column_values), weights)


def build_static_field(mosaic: ProfileMosaic, weights: np.ndarray, grid: VoxelGrid,
                       rng: np.random.Generator) -> StaticSoil:
    columns = [build_column(patch.profile, grid, rng) for patch in mosaic.patches]
    blended = {channel.name: blend_patches([getattr(column, channel.name) for column in columns], weights)
               for channel in fields(StaticSoil)}
    compaction_noise = build_smooth_noise(grid.shape, rng)
    texture_noise = build_smooth_noise(grid.shape, rng)

    density = blended["fine_earth_density_g_cm3"] * (1.0 + COMPACTION_NOISE_AMPLITUDE * compaction_noise)
    sand = np.clip(blended["sand_fraction"] * (1.0 + TEXTURE_NOISE_AMPLITUDE * texture_noise), 0.0, 1.0)
    clay = np.clip(blended["clay_fraction"] * (1.0 - TEXTURE_NOISE_AMPLITUDE * texture_noise), 0.0, 1.0 - sand)
    return StaticSoil(sand_fraction=sand,
                      clay_fraction=clay,
                      organic_carbon_percent=blended["organic_carbon_percent"],
                      coarse_fraction=blended["coarse_fraction"],
                      fine_earth_density_g_cm3=np.clip(density, *DENSITY_LIMITS_G_CM3),
                      resistance_deviation_log10=blended["resistance_deviation_log10"],
                      rootable_fraction=blended["rootable_fraction"])
