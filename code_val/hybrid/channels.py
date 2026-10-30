"""Les canaux que le modele hybride ajoute, et ceux qu'il retire.

Ajoutes : bengough, grandeur atomique mesurable au penetrometre, et le gradient du facteur hydrique,
la direction que suit l'hydrotropisme. Retires : depth, constant d'une scene a l'autre, et
growth_scale, qui n'est pas une mesure mais la recette du generateur (bengough x water_scale) :
l'exposer apprendrait au reseau un raccourci qu'aucune autre source de donnees ne reproduira.
"""
import numpy as np

from grid import VoxelGrid

# Variation par metre : exprime par centimetre, un gradient doux tombe dans les sous-normaux du
# float16 dans lequel les canaux sont stockes.
GRADIENT_LENGTH_CM = 100.0

ADDED_CHANNEL_NAMES = ("bengough", "water_gradient_down", "water_gradient_row",
                       "water_gradient_column")
BASELINE_ONLY_CHANNEL_NAMES = ("depth", "growth_scale")
# f_se as CPlantBox read it; v3 archives carry only the first two factors.
GROWTH_FACTOR_CHANNEL_NAMES = ("bengough", "water_scale", "aeration_scale", "rootable")


def build_water_gradients(water_scale: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    """En pas physiques : la grille est anisotrope (9 cm contre 15 cm), sans quoi la composante
    verticale serait surestimee d'un facteur 1,67. L'axe de profondeur croit vers le bas."""
    steps_cm = (grid.cell_height_cm, grid.cell_width_cm, grid.cell_width_cm)
    return np.stack(np.gradient(water_scale.astype(np.float64), *steps_cm)) * GRADIENT_LENGTH_CM


def build_added_channels(bengough: np.ndarray, water_scale: np.ndarray,
                         grid: VoxelGrid) -> np.ndarray:
    return np.concatenate([bengough[None], build_water_gradients(water_scale, grid)]).astype(np.float32)


def select_hybrid_channel_names(channel_names: tuple) -> tuple:
    return tuple(name for name in channel_names if name not in BASELINE_ONLY_CHANNEL_NAMES)


def read_channel(inputs: np.ndarray, channel_names, name: str) -> np.ndarray:
    return inputs[list(channel_names).index(name)].astype(np.float32)


def compute_growth_scale(inputs: np.ndarray, channel_names) -> np.ndarray:
    factors = [read_channel(inputs, channel_names, name)
               for name in GROWTH_FACTOR_CHANNEL_NAMES if name in channel_names]
    return np.prod(factors, axis=0)
