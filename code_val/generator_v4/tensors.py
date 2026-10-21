"""The input channels and the conditioning vector of a v4 scene.

The 19 v3 channels come first and in the same order, built by generator.tensors itself from the
mean water state, so a loader reading them by name works on both datasets. Their meaning moves on
two of them: `penetrometer` is now derived, and `bulk_density` is the fine-earth density. Seven
channels follow. The FiLM vector gains the city's water, never the city or the profile type: a
one-hot would let the network learn a table and break the held-out city and profile tests.
"""
from types import SimpleNamespace

import numpy as np

from generator.tensors import (BASELINE_CHANNEL_NAMES as V3_BASELINE_CHANNEL_NAMES,
                               CHANNEL_NAMES as V3_CHANNEL_NAMES, FILM_NAMES as V3_FILM_NAMES,
                               build_film_vector, build_input_tensor)
from grid import VoxelGrid
from hybrid.channels import select_hybrid_channel_names
from soil_v4.water import MEAN_STATE

CHANNEL_SCHEMA = "v5"
APPENDED_CHANNEL_NAMES = ("organic_carbon", "coarse_fraction", "rootable", "wall_fraction",
                          "air_filled_porosity", "aeration_scale", "saturated_fraction")
CHANNEL_NAMES = V3_CHANNEL_NAMES + APPENDED_CHANNEL_NAMES
BASELINE_CHANNEL_NAMES = V3_BASELINE_CHANNEL_NAMES + APPENDED_CHANNEL_NAMES
HYBRID_CHANNEL_NAMES = select_hybrid_channel_names(CHANNEL_NAMES)
FILM_NAMES = V3_FILM_NAMES + ("annual_water_fraction", "seasonal_water_amplitude", "frozen_winter")
ORGANIC_CARBON_SCALE_PERCENT = 5.0


def view_as_v3(environment) -> SimpleNamespace:
    """The attributes generator.tensors.build_input_tensor reads, taken from the mean state."""
    mean, static = environment.states[MEAN_STATE], environment.soil.static
    network = environment.network
    field = SimpleNamespace(penetrometer_mpa=mean.penetrometer_mpa,
                            bulk_density_g_cm3=static.fine_earth_density_g_cm3,
                            available_water_fraction=mean.available_water_fraction,
                            sand_fraction=static.sand_fraction, clay_fraction=static.clay_fraction)
    return SimpleNamespace(field=field, water_scale=mean.water_scale, growth_scale=mean.growth_scale,
                           pipe_fraction=network.pipe_fraction,
                           pipe_clearance_cm=network.pipe_clearance_cm,
                           backfill_fraction=network.backfill_fraction,
                           surround_fraction=network.surround_fraction,
                           leak_plume=network.leak_plume, pit_mask=environment.soil.pit_mask,
                           bengough=mean.bengough)


def build_input_tensor_v5(environment, prior: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    mean, soil = environment.states[MEAN_STATE], environment.soil
    appended = np.stack([soil.static.organic_carbon_percent / ORGANIC_CARBON_SCALE_PERCENT,
                         soil.static.coarse_fraction, soil.static.rootable_fraction,
                         soil.wall_fraction, mean.air_filled_porosity, mean.aeration_scale,
                         soil.saturated_fraction])
    return np.concatenate([build_input_tensor(view_as_v3(environment), prior, grid),
                           appended]).astype(np.float32)


def build_film_vector_v5(configuration) -> np.ndarray:
    seasons = np.array(configuration.soil.water.seasonal_water_fraction)
    water = (seasons.mean(), seasons.max() - seasons.min(),
             float(configuration.soil.water.frozen_winter))
    return np.concatenate([build_film_vector(configuration), np.array(water, np.float32)])
