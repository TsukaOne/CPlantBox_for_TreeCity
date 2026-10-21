"""Scene description, from its configuration to its voxels.
"""
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dataset.tensors import build_prior
from generator.environment import build_environment
from generator.polylines import extract_polydata
from generator.scene import SceneConfiguration
from generator.tensors import build_film_vector, build_input_tensor
from generator.voxelise import (DIAMETER_CLASSES, accumulate_volume, build_polysegments,
                                sample_segments, select_structural, stamp_classes)
from grid import VoxelGrid
from hybrid.prior import LEAK_PRIOR_BOOST, build_prior_v2
from network.intrusion import find_intrusions
from secondary_growth.parameters import SecondaryGrowthParameters
from secondary_growth.radii import build_final_radii
from tree.growth import grow_plant

VTP_RUNS_PER_SCENE = 1
PACKED_OCCUPANCIES = ("radius", "centreline", "radius_major", "radius_minor")


@dataclass
class Example:
    inputs: np.ndarray
    film: np.ndarray
    prior_v2: np.ndarray
    hit_counts: dict
    packed_runs: dict
    root_volume: np.ndarray
    polylines: dict
    fields: dict
    diagnostics: dict


def measure_maximum_depth_cm(starts: np.ndarray, ends: np.ndarray) -> float:
    if len(starts) == 0:
        return 0.0
    return float(-min(starts[:, 2].min(), ends[:, 2].min()))


def measure_plant(plant, grid: VoxelGrid, parameters: SecondaryGrowthParameters) -> tuple:
    polydata = extract_polydata(plant)
    radii, _ = build_final_radii(polydata, parameters)
    segments = build_polysegments(polydata, radii)

    occupancies, outside = stamp_classes(sample_segments(select_structural(segments)), grid)
    return (occupancies, accumulate_volume(sample_segments(segments), grid),
            polydata, radii, segments, outside)


def grow_once(configuration: SceneConfiguration, environment, grid: VoxelGrid, seed: int,
              parameters: SecondaryGrowthParameters, vtp_path) -> tuple:
    plant = grow_plant(environment.geometry, environment.elongation_grid, seed,
                       configuration.tree.age_years, vtp_path,
                       angle_grid=environment.angle_grid, water_lookup=environment.water_lookup)
    return measure_plant(plant, grid, parameters)


def find_lumen_intrusions(environment, segments: np.ndarray) -> dict:
    return find_intrusions(segments, environment.lumens)


def build_fields(environment, hit_counts: dict, runs: int) -> dict:
    return {"f_se": environment.growth_scale,
            "f_sa": environment.angle_scale,
            "bengough": environment.bengough,
            "eau": environment.water_scale,
            "theta": environment.moisture_m3_m3,
            "psi": environment.pressure_head,
            "occupancy": hit_counts["radius"] / runs,
            "occupancy_major": hit_counts["radius_major"] / runs,
            "occupancy_minor": hit_counts["radius_minor"] / runs,
            "occupancy_mediane": hit_counts["centreline"] / runs,
            "fuites": environment.leak_plume,
            "tuyaux": environment.pipe_labels,
            "remblais": environment.backfill_fraction,
            "patches": environment.patch_labels}


@dataclass
class Ensemble:
    hit_counts: dict
    packed_runs: dict
    root_volume: np.ndarray
    polylines: dict
    diagnostics: dict


def grow_ensemble(configuration, environment, grid: VoxelGrid,
                  parameters: SecondaryGrowthParameters, vtp_directory: Path,
                  grow_run=grow_once, find_run_intrusions=find_lumen_intrusions) -> Ensemble:
    """grow_run and find_run_intrusions let v4 grow through the seasons and check its walls."""
    stacks, volumes = defaultdict(list), []
    segment_counts, depths, intrusions, outside = [], [], {}, 0
    polylines = {}

    growth_started = time.perf_counter()
    for run, seed in enumerate(configuration.root_seeds, start=1):
        path = None if vtp_directory is None or run > VTP_RUNS_PER_SCENE else \
            vtp_directory / f"scene_{configuration.identifier:05d}_run_{run:02d}.vtp"
        occupancies, volume, polydata, radii, segments, missed = grow_run(
            configuration, environment, grid, seed, parameters, path)

        for name, occupancy in occupancies.items():
            stacks[name].append(occupancy)
        volumes.append(volume)
        segment_counts.append(len(segments.starts))
        depths.append(measure_maximum_depth_cm(segments.starts, segments.ends))
        outside += missed
        for name, depth in find_run_intrusions(environment,
                                               np.hstack([segments.starts, segments.ends])).items():
            intrusions[name] = max(intrusions.get(name, 0.0), depth)
        if run == 1:
            polylines = {"points": polydata.points.astype(np.float32),
                         "offsets": polydata.offsets.astype(np.int32),
                         "radius": radii.astype(np.float32),
                         "subtype": polydata.cell_arrays["subType"].astype(np.int16)}
    growth_seconds = time.perf_counter() - growth_started

    runs = len(configuration.root_seeds)
    hit_counts = {name: np.sum(stack, axis=0, dtype=np.uint16) for name, stack in stacks.items()}
    target = hit_counts["radius"] / runs
    return Ensemble(
        hit_counts=hit_counts,
        packed_runs={name: np.packbits(np.stack(stacks[name])) for name in PACKED_OCCUPANCIES},
        root_volume=np.mean(volumes, axis=0).astype(np.float32),
        polylines=polylines,
        diagnostics={"growth_seconds": round(growth_seconds, 1),
                     "segments_mean": float(np.mean(segment_counts)),
                     "segments_std": float(np.std(segment_counts)),
                     "max_depth_cm_mean": float(np.mean(depths)),
                     "max_depth_cm_std": float(np.std(depths)),
                     "mean_probability": float(target.mean()),
                     "mean_probability_centreline": float(hit_counts["centreline"].mean() / runs),
                     **{f"mean_probability_{name}": float(hit_counts[f"radius_{name}"].mean() / runs)
                        for name in DIAMETER_CLASSES},
                     "support_voxel_fraction": float((target > 0).mean()),
                     "samples_outside_grid": int(outside),
                     "intrusions": {name: float(depth) for name, depth in intrusions.items()}},
    )


def build_scene(configuration: SceneConfiguration, grid: VoxelGrid,
                parameters: SecondaryGrowthParameters = SecondaryGrowthParameters(),
                vtp_directory: Path = None) -> Example:
    started = time.perf_counter()
    environment = build_environment(configuration, grid)
    soil_seconds = time.perf_counter() - started

    ensemble = grow_ensemble(configuration, environment, grid, parameters, vtp_directory)
    prior = build_prior(configuration.tree, grid)

    return Example(
        inputs=build_input_tensor(environment, prior, grid),
        film=build_film_vector(configuration),
        prior_v2=build_prior_v2(prior, environment.growth_scale, environment.pipe_fraction,
                                environment.leak_plume, LEAK_PRIOR_BOOST),
        hit_counts=ensemble.hit_counts,
        packed_runs=ensemble.packed_runs,
        root_volume=ensemble.root_volume,
        polylines=ensemble.polylines,
        fields=build_fields(environment, ensemble.hit_counts, len(configuration.root_seeds)),
        diagnostics={"runtime_seconds": round(time.perf_counter() - started, 1),
                     "soil_seconds": round(soil_seconds, 1),
                     **ensemble.diagnostics},
    )
