"""Le sol d'une scene, du remblai brut aux objets que CPlantBox lit.

L'ordre porte le raisonnement et ne se permute pas :

  fosse avant remblais    - un reseau traverse la fosse comme le reste du sol ;
  remblais avant fuites   - un remblai arrive avec sa resistance et son humidite deja
                            coherentes, il ne doit pas etre re-echelonne par le couplage
                            humidite vers resistance que la fuite declenche ;
  Rosetta sur le champ composite, pas sur le profil d'origine ;
  geometrie en dernier    - grow_root_system appelle setSoil() puis initialize(), et
                            initialize() construit les tropismes a partir de ce qu'il tient a
                            cet instant.

La geometrie doit rester referencee pendant toute la boucle des tirages : CPlantBox la tient
par weak_ptr, et si elle est liberee le confinement s'arrete en silence.
"""
from dataclasses import dataclass

import numpy as np

from generator.network_layers import NetworkLayers, build_network_layers
from generator.scene import SceneConfiguration
from grid import VoxelGrid
from network.walls import build_street_geometry
from soil.field import build_mosaic_field, build_soil_field
from soil.fill import apply_fills
from soil.growth_response import (apply_bengough, apply_water_stress, compute_angle_scale,
                                  compute_growth_scale)
from soil.hydraulics import build_water_fields
from soil.leak import apply_leaks
from soil.mosaic import build_patch_weights
from soil.pit import apply_planting_pit, build_pit_mask


@dataclass
class SceneEnvironment:
    field: object
    moisture_m3_m3: np.ndarray
    pressure_head: np.ndarray
    growth_scale: np.ndarray
    water_scale: np.ndarray
    bengough: np.ndarray
    angle_scale: np.ndarray
    pipe_fraction: np.ndarray
    surround_fraction: np.ndarray
    backfill_fraction: np.ndarray
    pipe_clearance_cm: np.ndarray
    leak_plume: np.ndarray
    pit_mask: np.ndarray
    pipe_labels: np.ndarray
    patch_labels: np.ndarray
    lumens: tuple
    elongation_grid: object
    angle_grid: object
    water_lookup: object
    geometry: object


def build_soil(configuration: SceneConfiguration, grid: VoxelGrid, network: NetworkLayers, weights):
    rng = np.random.default_rng(configuration.soil_noise_seed)
    ambient = build_mosaic_field(configuration.soil, weights, grid, rng)
    pit = build_soil_field(configuration.pit_soil, grid, rng)
    field = apply_planting_pit(ambient, pit, build_pit_mask(configuration.pit_radius_cm,
                                                            configuration.pit_depth_cm, grid))

    field = apply_fills(field, tuple(horizon for _, horizon in network.shapes.fills), network.coverages)
    return apply_leaks(field, network.sources, network.natural_share)


def build_environment(configuration: SceneConfiguration, grid: VoxelGrid) -> SceneEnvironment:
    from tree.growth import build_interpolated_soil_grid, build_soil_grid

    network = build_network_layers(configuration.street, configuration.leaks, grid)
    weights = build_patch_weights(configuration.soil, grid)
    field = build_soil(configuration, grid, network, weights)

    water = build_water_fields(field)
    growth_scale = compute_growth_scale(field.penetrometer_mpa, field.available_water_fraction)
    water_scale = apply_water_stress(field.available_water_fraction).astype(np.float32)
    angle_scale = compute_angle_scale(field.penetrometer_mpa)

    return SceneEnvironment(
        field=field,
        moisture_m3_m3=water.moisture_m3_m3,
        pressure_head=water.pressure_head_cm,
        growth_scale=growth_scale,
        water_scale=water_scale,
        bengough=apply_bengough(field.penetrometer_mpa).astype(np.float32),
        angle_scale=angle_scale,
        pipe_fraction=network.pipe_fraction,
        surround_fraction=network.surround_fraction,
        backfill_fraction=network.backfill_fraction,
        pipe_clearance_cm=network.pipe_clearance_cm,
        leak_plume=network.leak_plume,
        pit_mask=build_pit_mask(configuration.pit_radius_cm, configuration.pit_depth_cm, grid),
        pipe_labels=network.pipe_labels,
        patch_labels=np.broadcast_to(weights.argmax(axis=0) + 1.0, grid.shape).astype(np.float32),
        lumens=network.shapes.lumens,
        elongation_grid=build_soil_grid(growth_scale, grid),
        angle_grid=build_soil_grid(angle_scale, grid),
        water_lookup=build_interpolated_soil_grid(water_scale, grid),
        geometry=build_street_geometry(network.shapes.lumens, grid),
    )
