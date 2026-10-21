"""Assemble the nine input channels, the FiLM vector and the depth-radius prior."""
import numpy as np

from grid import VoxelGrid
from obstacles.masks import OBSTACLE_DISTANCE_CLIP_CM, ObstacleMasks
from soil.archetypes import (
    BULK_DENSITY_RANGE_G_CM3,
    PENETROMETER_RANGE_MPA,
    TOPSOIL_DEPTH_RANGE_CM,
)
from soil.field import SoilField
from tree.attributes import AGE_RANGE_YEARS, TreeAttributes
from tree.species import (
    ARCHITECTURE_OF_SPECIES,
    ARCHITECTURE_SLOTS,
    GALE_GRIGAL_BETA,
    SPECIES_SLOTS,
)

CHANNEL_SCHEMA = "v2"
CHANNEL_NAMES = (
    "penetrometer", "bulk_density", "moisture", "sand_fraction", "clay_fraction",
    "pipe_mask", "pavement_mask", "obstacle_distance", "prior",
)

CROWN_ROOT_ZONE_PER_DBH = 18.0
CROWN_ROOT_ZONE_CUTOFF = 2.0
PRIOR_FLOOR = 1e-9

DBH_RANGE_CM = (0.0, 90.0)
HEIGHT_RANGE_M = (0.0, 30.0)
CROWN_DEPTH_RANGE_M = (0.0, 20.0)


def normalise(value, bounds: tuple[float, float]):
    return (value - bounds[0]) / (bounds[1] - bounds[0])


def build_prior(tree: TreeAttributes, grid: VoxelGrid) -> np.ndarray:
    """Gale and Grigal depth decay multiplied by a radial decay over the crown root zone."""
    beta = GALE_GRIGAL_BETA[tree.species]
    depth_profile = -np.log(beta) * beta ** grid.measure_layer_depths_cm()
    crown_root_zone_cm = CROWN_ROOT_ZONE_PER_DBH * tree.dbh_cm
    distances = grid.measure_trunk_distances_cm()
    radial_profile = np.where(distances < CROWN_ROOT_ZONE_CUTOFF * crown_root_zone_cm,
                              np.exp(-distances / crown_root_zone_cm), 0.0)
    prior = depth_profile[:, None, None] * radial_profile[None, :, :]
    return (prior / (prior.max() + PRIOR_FLOOR)).astype(np.float32)


def build_input_tensor(field: SoilField, masks: ObstacleMasks, tree: TreeAttributes,
                       grid: VoxelGrid) -> np.ndarray:
    channels = (
        field.penetrometer_mpa / PENETROMETER_RANGE_MPA[1],
        normalise(field.bulk_density_g_cm3, BULK_DENSITY_RANGE_G_CM3),
        field.available_water_fraction,
        field.sand_fraction,
        field.clay_fraction,
        masks.pipe.astype(np.float32),
        masks.pavement.astype(np.float32),
        masks.distance_to_obstacle_cm / OBSTACLE_DISTANCE_CLIP_CM,
        build_prior(tree, grid),
    )
    return np.stack(channels).astype(np.float32)


def build_one_hot(value: str, slots: tuple[str, ...]) -> np.ndarray:
    return np.array([float(value == slot) for slot in slots], dtype=np.float32)


def build_film_vector(tree: TreeAttributes, topsoil_depth_cm: float) -> np.ndarray:
    scalars = np.array([
        normalise(tree.age_years, AGE_RANGE_YEARS),
        normalise(tree.dbh_cm, DBH_RANGE_CM),
        normalise(tree.height_m, HEIGHT_RANGE_M),
        normalise(tree.crown_depth_m, CROWN_DEPTH_RANGE_M),
        normalise(topsoil_depth_cm, TOPSOIL_DEPTH_RANGE_CM),
    ], dtype=np.float32)
    return np.concatenate([
        build_one_hot(tree.species, SPECIES_SLOTS),
        build_one_hot(ARCHITECTURE_OF_SPECIES[tree.species], ARCHITECTURE_SLOTS),
        scalars,
    ])
