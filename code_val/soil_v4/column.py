"""A drawn profile laid on the depth cells of the grid.

Soil properties are read at the cell centre, so a horizon boundary stays sharp. A barrier cell
keeps the soil of the layer above it (the one below for a surface barrier), so the retention
physics always runs on a real soil; the barrier itself lives in `rootable_fraction`, the share of
the cell no barrier covers, computed from the exact overlap.

Each layer also draws its own deviation from the penetration resistance pedotransfer.
"""
from dataclasses import dataclass

import numpy as np

from grid import VoxelGrid
from soil_library.draw import SOIL, DrawnLayer, DrawnProfile

STONE_PARTICLE_DENSITY_G_CM3 = 2.65
# Estimate: published penetration resistance pedotransfers err by 0.9 to 1.8 MPa (Vaz et al.).
RESISTANCE_DEVIATION_LOG10_SD = 0.1


@dataclass
class StaticSoil:
    sand_fraction: np.ndarray
    clay_fraction: np.ndarray
    organic_carbon_percent: np.ndarray
    coarse_fraction: np.ndarray
    fine_earth_density_g_cm3: np.ndarray
    resistance_deviation_log10: np.ndarray
    rootable_fraction: np.ndarray

    @property
    def whole_soil_density_g_cm3(self) -> np.ndarray:
        return (self.fine_earth_density_g_cm3 * (1.0 - self.coarse_fraction)
                + STONE_PARTICLE_DENSITY_G_CM3 * self.coarse_fraction)


def convert_layer_to_soil(layer: DrawnLayer) -> StaticSoil:
    """One engineered layer as scalars, written whole into a planting pit or a backfill."""
    return StaticSoil(layer.sand_fraction, layer.clay_fraction, layer.organic_carbon_percent,
                      layer.coarse_fraction, layer.fine_earth_density_g_cm3, 0.0, 1.0)


def measure_layer_bottoms_cm(profile: DrawnProfile, grid: VoxelGrid) -> np.ndarray:
    return np.array([grid.depth_cm if layer.bottom_cm is None else layer.bottom_cm
                     for layer in profile.layers])


def measure_barrier_fraction(profile: DrawnProfile, bottoms_cm: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    cell_tops_cm = np.arange(grid.depth_cells) * grid.cell_height_cm
    cell_bottoms_cm = cell_tops_cm + grid.cell_height_cm
    covered = np.zeros(grid.depth_cells)
    for layer, bottom_cm in zip(profile.layers, bottoms_cm):
        if layer.kind == SOIL:
            continue
        overlap = np.minimum(cell_bottoms_cm, bottom_cm) - np.maximum(cell_tops_cm, layer.top_cm)
        covered += np.clip(overlap, 0.0, None) / grid.cell_height_cm
    return np.clip(covered, 0.0, 1.0)


def map_layers_to_soil(profile: DrawnProfile) -> np.ndarray:
    soil_indices = [index for index, layer in enumerate(profile.layers) if layer.kind == SOIL]
    return np.array([max((soil for soil in soil_indices if soil <= index), default=soil_indices[0])
                     for index in range(len(profile.layers))])


def read_layer_values(profile: DrawnProfile, layer_indices: np.ndarray, name: str) -> np.ndarray:
    return np.array([getattr(profile.layers[index], name) for index in layer_indices])


def build_column(profile: DrawnProfile, grid: VoxelGrid, rng: np.random.Generator) -> StaticSoil:
    bottoms_cm = measure_layer_bottoms_cm(profile, grid)
    deviations = rng.normal(0.0, RESISTANCE_DEVIATION_LOG10_SD, len(profile.layers))
    cell_layers = np.minimum(np.searchsorted(bottoms_cm, grid.measure_layer_depths_cm(), side="right"),
                             len(profile.layers) - 1)
    soil_layers = map_layers_to_soil(profile)[cell_layers]
    return StaticSoil(
        sand_fraction=read_layer_values(profile, soil_layers, "sand_fraction"),
        clay_fraction=read_layer_values(profile, soil_layers, "clay_fraction"),
        organic_carbon_percent=read_layer_values(profile, soil_layers, "organic_carbon_percent"),
        coarse_fraction=read_layer_values(profile, soil_layers, "coarse_fraction"),
        fine_earth_density_g_cm3=read_layer_values(profile, soil_layers, "fine_earth_density_g_cm3"),
        resistance_deviation_log10=deviations[soil_layers],
        rootable_fraction=1.0 - measure_barrier_fraction(profile, bottoms_cm, grid))
