"""Les fichiers d'une scene : le .npz pour l'entrainement, le .json pour savoir ce qu'il y a
dedans, le .vti pour aller regarder, et la scene redite dans le contrat d'inference.

Le descripteur est l'image de la configuration : tout ce qui a ete tire y figure parce qu'il
figure dans la dataclass, sans liste a tenir a jour separement.

L'ecriture passe par un fichier temporaire puis un renommage, et le .json vient en dernier :
c'est lui qui atteste qu'une scene est complete. La v1 testait l'existence du .npz, donc une
archive tronquee par une interruption passait pour finie.
"""
import json
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np

from generator.build import PACKED_OCCUPANCIES, Example
from generator.scene import SCHEMA_VERSION, SceneConfiguration
from generator.site_request import build_site_request
from generator.tensors import (BASELINE_CHANNEL_NAMES, CHANNEL_NAMES, CHANNEL_SCHEMA,
                               FILM_NAMES, HYBRID_CHANNEL_NAMES)
from generator.voxelise import (DIAMETER_CLASSES, MAJOR_DIAMETER_CM, RADIUS_BIN_EDGES_CM,
                                SAMPLE_STEP_CM)
from grid import VoxelGrid
from hybrid.channels import GRADIENT_LENGTH_CM
from hybrid.prior import LEAK_PRIOR_BOOST
from paraview import write_voxel_grids
from dataset.occupancy import STRUCTURAL_SUBTYPES
from tree.species import hash_xml
from versions import read_commit

SCENE_NAME_TEMPLATE = "scene_{identifier:05d}"
SITE_REQUEST_SUBDIRECTORY = "site_request"

# Les cles historiques (target, hit_count, occupancy_runs) gardent la cible entiere, pour que
# le loader de la baseline lise la v3 sans changement.
TARGET_KEYS = {"radius": "target", "centreline": "target_centreline",
               "radius_major": "target_major", "radius_minor": "target_minor"}
HIT_COUNT_KEYS = {"radius": "hit_count", "centreline": "hit_count_centreline",
                  "radius_major": "hit_count_major", "radius_minor": "hit_count_minor",
                  "centreline_major": "hit_count_centreline_major",
                  "centreline_minor": "hit_count_centreline_minor"}
RUN_KEYS = {"radius": "occupancy_runs", "centreline": "centreline_runs",
            "radius_major": "occupancy_runs_major", "radius_minor": "occupancy_runs_minor"}


def build_paths(directory: Path, identifier: int) -> tuple:
    stem = SCENE_NAME_TEMPLATE.format(identifier=identifier)
    return (directory / f"{stem}.npz", directory / f"{stem}.json", directory / f"{stem}.vti",
            directory / SITE_REQUEST_SUBDIRECTORY / f"{stem}.json")


def is_complete(directory: Path, identifier: int) -> bool:
    return build_paths(directory, identifier)[1].exists()


def build_descriptor(configuration: SceneConfiguration, example: Example, grid: VoxelGrid,
                     parameters) -> dict:
    secondary = asdict(parameters)
    secondary["structural_subtypes"] = sorted(secondary["structural_subtypes"])
    return {
        "schema_version": SCHEMA_VERSION,
        "channel_schema": CHANNEL_SCHEMA,
        "channel_names": list(CHANNEL_NAMES),
        "baseline_channel_names": list(BASELINE_CHANNEL_NAMES),
        "hybrid_channel_names": list(HYBRID_CHANNEL_NAMES),
        "film_names": list(FILM_NAMES),
        "grid": asdict(grid),
        "configuration": asdict(configuration),
        "secondary_growth": secondary,
        "voxelisation": {"monte_carlo_runs": len(configuration.root_seeds),
                         "structural_subtypes": sorted(STRUCTURAL_SUBTYPES),
                         "diameter_classes": list(DIAMETER_CLASSES),
                         "major_diameter_cm": MAJOR_DIAMETER_CM,
                         "sample_step_cm": SAMPLE_STEP_CM,
                         "radius_bin_edges_cm": list(RADIUS_BIN_EDGES_CM),
                         "packed_runs": [RUN_KEYS[name] for name in PACKED_OCCUPANCIES],
                         "packed_runs_shape": [len(configuration.root_seeds), *grid.shape]},
        "hybrid": {"leak_prior_boost": LEAK_PRIOR_BOOST, "gradient_length_cm": GRADIENT_LENGTH_CM},
        "versions": {"commit": read_commit(), "xml": configuration.tree_xml,
                     "xml_sha256": hash_xml(configuration.tree_xml)},
        "diagnostics": example.diagnostics,
    }


def build_arrays(example: Example, runs: int) -> dict:
    return {
        "inputs": example.inputs.astype(np.float16),
        "channel_names": np.array(CHANNEL_NAMES),
        "film": example.film,
        "prior_v2": example.prior_v2.astype(np.float16),
        "root_volume": example.root_volume.astype(np.float16),
        **{key: (example.hit_counts[name] / runs).astype(np.float16)
           for name, key in TARGET_KEYS.items()},
        **{key: example.hit_counts[name] for name, key in HIT_COUNT_KEYS.items()},
        **{key: example.packed_runs[name] for name, key in RUN_KEYS.items()},
        **{f"polyline_{name}": values for name, values in example.polylines.items()},
    }


def write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(content, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def write_scene(directory: Path, configuration: SceneConfiguration, example: Example,
                grid: VoxelGrid, parameters, write_vti: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    archive_path, descriptor_path, voxel_path, request_path = build_paths(directory,
                                                                         configuration.identifier)

    # numpy ajoute .npz au nom qu'on lui passe, mais pas a un fichier deja ouvert.
    temporary = archive_path.with_suffix(".npz.tmp")
    with open(temporary, "wb") as handle:
        np.savez_compressed(handle, **build_arrays(example, len(configuration.root_seeds)))
    os.replace(temporary, archive_path)

    if write_vti:
        write_voxel_grids(voxel_path, example.fields, grid)
    write_json(request_path, build_site_request(configuration, directory.name))
    write_json(descriptor_path, build_descriptor(configuration, example, grid, parameters))
    return archive_path
