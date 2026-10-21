"""The files of a v4 scene, in the v3 layout: .npz, .vti, site_request/ and the descriptor last.

The v3 writers are reused as they are; only what differs is overwritten: the channel and FiLM
names, the schema versions, the soil physics, and the contract the scene is redescribed in.
"""
import os
from pathlib import Path

import numpy as np

from generator.writer import build_arrays, build_descriptor, build_paths, write_json
from generator_v4.build import STOPPED_GROWTH_RESISTANCE_MPA
from generator_v4.scene import SCHEMA_VERSION, SceneConfigurationV4
from generator_v4.site_request import build_site_request_v3
from generator_v4.tensors import (BASELINE_CHANNEL_NAMES, CHANNEL_NAMES, CHANNEL_SCHEMA, FILM_NAMES,
                                  HYBRID_CHANNEL_NAMES)
from grid import VoxelGrid
from paraview import write_voxel_grids
from soil_v4.water import MEAN_STATE


def build_descriptor_v4(configuration: SceneConfigurationV4, example, grid: VoxelGrid,
                        parameters) -> dict:
    descriptor = build_descriptor(configuration, example, grid, parameters)
    descriptor.update({"schema_version": SCHEMA_VERSION,
                       "channel_schema": CHANNEL_SCHEMA,
                       "channel_names": list(CHANNEL_NAMES),
                       "baseline_channel_names": list(BASELINE_CHANNEL_NAMES),
                       "hybrid_channel_names": list(HYBRID_CHANNEL_NAMES),
                       "film_names": list(FILM_NAMES),
                       "soil_physics": {"water_state": MEAN_STATE,
                                        "stopped_growth_mpa": STOPPED_GROWTH_RESISTANCE_MPA}})
    return descriptor


def write_scene_v4(directory: Path, configuration: SceneConfigurationV4, example, grid: VoxelGrid,
                   parameters) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    archive_path, descriptor_path, voxel_path, request_path = build_paths(directory,
                                                                         configuration.identifier)
    arrays = build_arrays(example, len(configuration.root_seeds))
    arrays["channel_names"] = np.array(CHANNEL_NAMES)
    temporary = archive_path.with_suffix(".npz.tmp")
    with open(temporary, "wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary, archive_path)

    write_voxel_grids(voxel_path, example.fields, grid)
    write_json(request_path, build_site_request_v3(configuration, directory.name))
    write_json(descriptor_path, build_descriptor_v4(configuration, example, grid, parameters))
    return archive_path
