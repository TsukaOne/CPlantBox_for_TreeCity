"""One v4 scene, from its configuration to its tensors and fields.

Roots grow in the mean water state, stopped at 3.0 MPa: the stop threshold of trees rather than
of crops (Day & Bassuk 1994, Watson 2014), chosen at the sandbox checkpoint. The growth, the
secondary growth and the voxelisation are the v3 ones; the intrusion check adds the walls.
"""
import time

import numpy as np

from dataset.tensors import build_prior
from generator.build import Example, grow_ensemble, grow_once
from generator_v4.environment import build_environment_v4, find_pipe_and_wall_intrusions
from generator_v4.scene import SceneConfigurationV4
from generator_v4.tensors import build_film_vector_v5, build_input_tensor_v5
from grid import VoxelGrid
from hybrid.prior import LEAK_PRIOR_BOOST, build_prior_v2
from secondary_growth.parameters import SecondaryGrowthParameters
from soil_v4.resistance import CALIBRATED_SUCTION_RANGE_KPA, convert_head_to_suction_kpa
from soil_v4.retention import ROSETTA_MAXIMUM_DENSITY_G_CM3
from soil_v4.water import MEAN_STATE

STOPPED_GROWTH_RESISTANCE_MPA = 3.0


def build_fields(environment, hit_counts: dict, runs: int) -> dict:
    mean, soil = environment.states[MEAN_STATE], environment.soil
    return {"f_se": mean.growth_scale, "f_sa": mean.angle_scale, "bengough": mean.bengough,
            "eau": mean.water_scale, "theta": mean.moisture_m3_m3, "psi": mean.pressure_head_cm,
            "resistance": mean.penetrometer_mpa, "air": mean.air_filled_porosity,
            "density": soil.static.fine_earth_density_g_cm3,
            "rootable": soil.static.rootable_fraction,
            "walls": soil.wall_fraction, "saturated": soil.saturated_fraction,
            "occupancy": hit_counts["radius"] / runs,
            "occupancy_major": hit_counts["radius_major"] / runs,
            "occupancy_minor": hit_counts["radius_minor"] / runs,
            "occupancy_mediane": hit_counts["centreline"] / runs,
            "fuites": environment.network.leak_plume, "tuyaux": environment.network.pipe_labels,
            "remblais": environment.network.backfill_fraction,
            "patches": np.broadcast_to(soil.weights.argmax(axis=0) + 1.0, soil.pit_mask.shape)}


def measure_soil_diagnostics(environment) -> dict:
    soil, mean = environment.soil, environment.states[MEAN_STATE]
    rootable = soil.static.rootable_fraction > 0.0
    suction_kpa = convert_head_to_suction_kpa(mean.pressure_head_cm[rootable])
    low_kpa, high_kpa = CALIBRATED_SUCTION_RANGE_KPA
    return {"density_capped_for_rosetta": float((soil.static.fine_earth_density_g_cm3
                                                 > ROSETTA_MAXIMUM_DENSITY_G_CM3).mean()),
            "suction_outside_whalley_range": float(((suction_kpa < low_kpa)
                                                    | (suction_kpa > high_kpa)).mean()),
            "wall_statuses": list(environment.walls.statuses)}


def build_scene_v4(configuration: SceneConfigurationV4, grid: VoxelGrid,
                   parameters: SecondaryGrowthParameters, vtp_directory) -> Example:
    started = time.perf_counter()
    environment = build_environment_v4(configuration.street, configuration.leaks, configuration.soil,
                                       configuration.walls, STOPPED_GROWTH_RESISTANCE_MPA, grid)
    soil_seconds = time.perf_counter() - started
    ensemble = grow_ensemble(configuration, environment, grid, parameters, vtp_directory, grow_once,
                             find_pipe_and_wall_intrusions)
    prior = build_prior(configuration.tree, grid)
    mean = environment.states[MEAN_STATE]
    return Example(
        inputs=build_input_tensor_v5(environment, prior, grid),
        film=build_film_vector_v5(configuration),
        prior_v2=build_prior_v2(prior, mean.growth_scale, environment.network.pipe_fraction,
                                environment.network.leak_plume, LEAK_PRIOR_BOOST),
        hit_counts=ensemble.hit_counts,
        packed_runs=ensemble.packed_runs,
        root_volume=ensemble.root_volume,
        polylines=ensemble.polylines,
        fields=build_fields(environment, ensemble.hit_counts, len(configuration.root_seeds)),
        diagnostics={"runtime_seconds": round(time.perf_counter() - started, 1),
                     "soil_seconds": round(soil_seconds, 1),
                     **ensemble.diagnostics, **measure_soil_diagnostics(environment)})
