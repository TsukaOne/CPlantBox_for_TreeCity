"""Ce que les reseaux enterres imposent a une scene, independamment du sol qu'on y met.

Tout est deterministe : la partie aleatoire (le trace des reseaux, les fuites) est deja tiree dans
la configuration, donc ce calcul peut preceder ou suivre celui du sol sans changer un tirage.
"""
from dataclasses import dataclass

import numpy as np

from grid import VoxelGrid
from network.coverage import build_coverage, build_label_field, measure_cell_axes_cm
from network.leaks import build_plume_ramp
from network.primitives import measure_signed_distance
from network.shapes import build_scene_shapes
from soil.fill import measure_natural_share

CLEARANCE_CLIP_CM = 300.0


@dataclass
class NetworkLayers:
    shapes: object
    coverages: tuple
    sources: tuple
    natural_share: np.ndarray
    pipe_fraction: np.ndarray
    surround_fraction: np.ndarray
    backfill_fraction: np.ndarray
    pipe_clearance_cm: np.ndarray
    leak_plume: np.ndarray
    pipe_labels: np.ndarray


def measure_cell_points(grid: VoxelGrid) -> np.ndarray:
    depths, rows, columns = measure_cell_axes_cm(grid)
    depth, row, column = np.meshgrid(depths, rows, columns, indexing="ij")
    return np.stack([column.ravel(), row.ravel(), depth.ravel()], axis=1)


def measure_pipe_clearance_cm(lumens: tuple, grid: VoxelGrid) -> np.ndarray:
    if not lumens:
        return np.full(grid.shape, CLEARANCE_CLIP_CM, np.float32)
    points = measure_cell_points(grid)
    distances = np.min([measure_signed_distance(lumen, points) for lumen in lumens], axis=0)
    return np.clip(distances, 0.0, CLEARANCE_CLIP_CM).reshape(grid.shape).astype(np.float32)


def build_network_layers(street, leaks: tuple, grid: VoxelGrid) -> NetworkLayers:
    shapes = build_scene_shapes(street, grid)
    coverages = tuple(build_coverage(shape, grid) for shape, _ in shapes.fills)
    sources = tuple((build_plume_ramp(leak, grid), leak.available_water_fraction) for leak in leaks)
    natural_share = measure_natural_share(coverages, grid.shape)

    utility_count = len(street.utilities)
    pipe_fraction = np.clip(np.sum(coverages[:utility_count], axis=0), 0.0, 1.0) if coverages \
        else np.zeros(grid.shape, np.float32)
    surround_fraction = np.clip(np.sum(coverages[utility_count:2 * utility_count], axis=0)
                                - pipe_fraction, 0.0, 1.0) if coverages \
        else np.zeros(grid.shape, np.float32)
    plume = np.max([ramp for ramp, _ in sources], axis=0) if sources \
        else np.zeros(grid.shape, np.float32)

    return NetworkLayers(
        shapes=shapes,
        coverages=coverages,
        sources=sources,
        natural_share=natural_share,
        pipe_fraction=pipe_fraction.astype(np.float32),
        surround_fraction=surround_fraction.astype(np.float32),
        backfill_fraction=(1.0 - natural_share).astype(np.float32),
        pipe_clearance_cm=measure_pipe_clearance_cm(shapes.lumens, grid),
        leak_plume=plume.astype(np.float32),
        pipe_labels=build_label_field(shapes.lumens, grid),
    )
