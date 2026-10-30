"""Les canaux d'entree du reseau, et le vecteur de conditionnement.

Deux canaux de la v1 disparaissent. Le masque de voirie, parce qu'il n'y a plus de dalle de
surface : ce qui atteint les racines est l'excavation. Et la distance a l'obstacle, qui
supposait un tuyau axial infini et ne sait rien dire d'une diagonale coudee.

Le masque binaire de tuyau cede la place a une fraction : un tuyau de 15 cm a une section de
177 cm2 quand une colonne de voxel en fait 135, donc aucun voxel n'est jamais plein et le
masque ne pouvait dessiner qu'un escalier.

f_se et le facteur hydrique sont volontairement redondants avec les cinq premiers canaux : ce
sont les champs exacts que CPlantBox a lus, donc le reseau n'a pas a redecouvrir la chaine
Rosetta, van Genuchten et Bengough pour atteindre le label.

Le tenseur est un sur-ensemble : les 15 canaux de la baseline, puis les 4 que le modele hybride
ajoute. Chaque modele y lit sa liste par nom, ce qui permet de re-entrainer la baseline sur les
memes scenes que le modele hybride : sans cela, comparer leurs Dice ne dirait rien.
"""
import numpy as np

from dataset.tensors import (CROWN_DEPTH_RANGE_M, DBH_RANGE_CM, HEIGHT_RANGE_M, build_one_hot,
                             normalise)
from generator.network_layers import CLEARANCE_CLIP_CM
from generator.scene import TREE_PIT_RADIUS_RANGE_CM, SceneConfiguration
from hybrid.channels import ADDED_CHANNEL_NAMES, build_added_channels, select_hybrid_channel_names
from soil.archetypes import BULK_DENSITY_RANGE_G_CM3, PENETROMETER_RANGE_MPA
from soil.pit import TREE_PIT_DEPTH_RANGE_CM
from grid import VoxelGrid
from tree.attributes import AGE_RANGE_YEARS
from tree.species import ARCHITECTURE_OF_SPECIES, ARCHITECTURE_SLOTS, SPECIES_SLOTS

CHANNEL_SCHEMA = "v4"
BASELINE_CHANNEL_NAMES = ("penetrometer", "bulk_density", "available_water", "sand_fraction",
                          "clay_fraction", "water_scale", "growth_scale", "pipe_fraction",
                          "pipe_clearance", "backfill_fraction", "surround_fraction", "leak_plume",
                          "pit_mask", "depth", "prior")
CHANNEL_NAMES = BASELINE_CHANNEL_NAMES + ADDED_CHANNEL_NAMES
HYBRID_CHANNEL_NAMES = select_hybrid_channel_names(CHANNEL_NAMES)
FILM_NAMES = SPECIES_SLOTS + ARCHITECTURE_SLOTS + ("age_years", "dbh_cm", "height_m",
                                                   "crown_depth_m", "pit_radius_cm",
                                                   "pit_depth_cm", "utility_count")
UTILITY_COUNT_SCALE = 10.0


def build_input_tensor(environment, prior: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    field = environment.field
    depths = np.broadcast_to(grid.measure_layer_depths_cm()[:, None, None] / grid.depth_cm,
                             grid.shape)
    channels = (
        field.penetrometer_mpa / PENETROMETER_RANGE_MPA[1],
        normalise(field.bulk_density_g_cm3, BULK_DENSITY_RANGE_G_CM3),
        field.available_water_fraction,
        field.sand_fraction,
        field.clay_fraction,
        environment.water_scale,
        environment.growth_scale,
        environment.pipe_fraction,
        environment.pipe_clearance_cm / CLEARANCE_CLIP_CM,
        environment.backfill_fraction,
        environment.surround_fraction,
        environment.leak_plume,
        environment.pit_mask.astype(np.float32),
        depths,
        prior,
    )
    added = build_added_channels(environment.bengough, environment.water_scale, grid)
    return np.concatenate([np.stack(channels), added]).astype(np.float32)


def build_film_vector(configuration: SceneConfiguration) -> np.ndarray:
    tree = configuration.tree
    scalars = (
        normalise(tree.age_years, AGE_RANGE_YEARS),
        normalise(tree.dbh_cm, DBH_RANGE_CM),
        normalise(tree.height_m, HEIGHT_RANGE_M),
        normalise(tree.crown_depth_m, CROWN_DEPTH_RANGE_M),
        normalise(configuration.pit_radius_cm, TREE_PIT_RADIUS_RANGE_CM),
        normalise(configuration.pit_depth_cm, TREE_PIT_DEPTH_RANGE_CM),
        len(configuration.street.utilities) / UTILITY_COUNT_SCALE,
    )
    return np.concatenate([
        build_one_hot(tree.species, SPECIES_SLOTS),
        build_one_hot(ARCHITECTURE_OF_SPECIES[tree.species], ARCHITECTURE_SLOTS),
        np.array(scalars, np.float32),
    ]).astype(np.float32)
