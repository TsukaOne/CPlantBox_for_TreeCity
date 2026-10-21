"""Walls as CPlantBox solids, and the scene domain: the soil box minus every pipe and wall.

A panel is one box per segment of its path plus a vertical cylinder at each node, which rounds
its ends and closes its corners as measure_plan_distance does. Like a pipe it is inflated by
PIPE_EXCLUSION_MARGIN_CM, sideways and downwards, and only here: coverages and intrusion checks
read the true wall. The v3 build_street_geometry stays as it was.
"""
import math

import numpy as np
import plantbox as pb

from grid import VoxelGrid
from network.primitives import TrenchSlab
from network.walls import (AZIMUTH_AXIS, PIPE_EXCLUSION_MARGIN_CM, ROUND_CROSS_SECTION,
                           build_segment_solid, build_wall_segments)

SURFACE_CM = 0.0


def build_panel_solids(panel: TrenchSlab) -> list:
    half_width_cm = panel.half_width_cm + PIPE_EXCLUSION_MARGIN_CM
    depth_cm = PIPE_EXCLUSION_MARGIN_CM - panel.bottom_cm
    nodes = np.asarray(panel.path_cm, float)
    solids = []
    for start, end in zip(nodes[:-1], nodes[1:]):
        direction = end - start
        middle = 0.5 * (start + end)
        box = pb.SDF_PlantBox(float(np.linalg.norm(direction)), 2.0 * half_width_cm, depth_cm)
        angle_degrees = math.degrees(math.atan2(direction[1], direction[0]))
        solids.append(pb.SDF_RotateTranslate(box, angle_degrees, AZIMUTH_AXIS,
                                             pb.Vector3d(middle[0], middle[1], SURFACE_CM)))
    for node in nodes:
        cap = pb.SDF_PlantContainer(half_width_cm, half_width_cm, depth_cm, ROUND_CROSS_SECTION)
        solids.append(pb.SDF_RotateTranslate(cap, pb.Vector3d(node[0], node[1], SURFACE_CM)))
    return solids


def build_scene_geometry(lumens: tuple, panels: tuple, grid: VoxelGrid) -> pb.SignedDistanceFunction:
    soil_box = pb.SDF_PlantBox(2.0 * grid.half_width_cm, 2.0 * grid.half_length_cm, grid.depth_cm)
    pipes = [build_segment_solid(segment) for segment in build_wall_segments(lumens)]
    walls = [solid for panel in panels for solid in build_panel_solids(panel)]
    return pb.SDF_Difference([soil_box] + pipes + walls)
