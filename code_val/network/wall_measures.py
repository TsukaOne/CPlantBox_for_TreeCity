"""How far a point is from a wall, how much room a wall leaves a pipe, and how much of each voxel
it fills.

A wall is a TrenchSlab: a plan path with a half thickness, extruded from the surface down to its
bottom. Its plan distance is the one measure_plan_distance gives a trench, with rounded ends.
"""
import numpy as np

from grid import VoxelGrid
from network.coverage import build_coverage
from network.primitives import TrenchSlab, measure_plan_distance
from network.street import MINIMUM_LUMEN_CLEARANCE_CM, UtilityRun, sample_run


def measure_wall_distance(panel: TrenchSlab, points: np.ndarray) -> np.ndarray:
    """Signed 3-D distance from (x, y, z) points, negative inside the wall."""
    plan = measure_plan_distance(panel, points[:, :2])
    below = panel.bottom_cm - points[:, 2]
    inside = (plan < 0.0) & (below < 0.0)
    outside = np.hypot(np.maximum(plan, 0.0), np.maximum(below, 0.0))
    return np.where(inside, np.maximum(plan, below), outside)


def measure_wall_deficit_cm(panel: TrenchSlab, corridors: tuple[UtilityRun, ...]) -> float:
    clearances = [float((measure_wall_distance(panel, sample_run(run)) - run.radius_cm).min())
                  for run in corridors]
    return MINIMUM_LUMEN_CLEARANCE_CM - min(clearances, default=np.inf)


def measure_wall_fraction(panels: tuple[TrenchSlab, ...], grid: VoxelGrid) -> np.ndarray:
    if not panels:
        return np.zeros(grid.shape, np.float32)
    return np.clip(np.sum([build_coverage(panel, grid) for panel in panels], axis=0), 0.0, 1.0)


def find_wall_intrusions(segments: np.ndarray, panels: tuple[TrenchSlab, ...]) -> dict:
    """Against the true wall, at the nodes, as network/intrusion.py does for the pipes."""
    if len(segments) == 0:
        return {}
    nodes = np.vstack([segments[:, :3], segments[:, 3:6]])
    depths = {panel.name: -float(measure_wall_distance(panel, nodes).min()) for panel in panels}
    return {name: depth for name, depth in depths.items() if depth > 0.0}
