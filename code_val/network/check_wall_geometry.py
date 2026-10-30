"""Check that CPlantBox and numpy agree on where every wall is, for each wall kind.

    python3 code_val/network/check_wall_geometry.py

The walls are laid on the street of a v3 scene. Points are drawn around them; the CPlantBox
distance to the union of a panel's solids is compared with the numpy distance inflated by the
same margin. Outside a box, CPlantBox measures a box distance and numpy a Euclidean one, so the
two only have to agree in sign, and in value close to the faces. CPlantBox also counts the
surface as a face of the wall, numpy does not: points near the surface are left out of the gap.
"""
import sys
from pathlib import Path

import numpy as np
import plantbox as pb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.scene import MASTER_SEED, build_generator, draw_scene
from grid import VoxelGrid
from network.wall_geometry import build_panel_solids
from network.wall_layouts import FOUNDATION, NARROW_STRIP, CONFINED_PIT, draw_wall_module
from network.wall_measures import measure_wall_distance
from network.walls import PIPE_EXCLUSION_MARGIN_CM

GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
SCENE = 1001
ANY_TREE_XML = "my_Picea_abies.xml"  # the street, the pit and the walls do not depend on the tree
CHECK_DOMAIN = 99
POINTS_PER_PANEL = 4000
SPREAD_CM = 60.0
SIGN_TOLERANCE_CM = 0.5
FACE_BAND_CM = 5.0


def draw_points_around(panel, rng: np.random.Generator) -> np.ndarray:
    path = np.asarray(panel.path_cm, float)
    weights = rng.random(POINTS_PER_PANEL)
    segments = rng.integers(len(path) - 1, size=POINTS_PER_PANEL)
    along = path[segments] + (path[segments + 1] - path[segments]) * weights[:, None]
    plan = along + rng.uniform(-SPREAD_CM, SPREAD_CM, (POINTS_PER_PANEL, 2))
    depth = rng.uniform(panel.bottom_cm - SPREAD_CM, 0.0, POINTS_PER_PANEL)
    inside_box = (np.abs(plan) < GRID.half_width_cm).all(axis=1)
    return np.column_stack([plan, depth])[inside_box]


def compare_panel(panel, rng: np.random.Generator) -> tuple:
    points = draw_points_around(panel, rng)
    union = pb.SDF_Union(build_panel_solids(panel))
    plantbox = np.array([union.getDist(pb.Vector3d(*point)) for point in points])
    expected = measure_wall_distance(panel, points) - PIPE_EXCLUSION_MARGIN_CM
    clear = np.abs(expected) > SIGN_TOLERANCE_CM
    agreement = float((np.sign(plantbox[clear]) == np.sign(expected[clear])).mean())
    near_face = (np.abs(expected) < FACE_BAND_CM) & (points[:, 2] < -FACE_BAND_CM)
    gap = float(np.abs(plantbox[near_face] - expected[near_face]).max()) if near_face.any() else 0.0
    return len(points), agreement, gap


def main() -> None:
    configuration = draw_scene(SCENE, GRID, tree_xml=ANY_TREE_XML)
    for kind in (FOUNDATION, NARROW_STRIP, CONFINED_PIT):
        rng = build_generator(MASTER_SEED, SCENE, CHECK_DOMAIN)
        module = draw_wall_module(kind, configuration.street, configuration.pit_radius_cm,
                                  configuration.pit_depth_cm, GRID, rng)
        print(f"{kind}: {len(module.panels)} panel(s), statuses {module.statuses}")
        for panel in module.panels:
            count, agreement, gap = compare_panel(panel, rng)
            print(f"  {panel.name}: depth {-panel.bottom_cm:.0f} cm, thickness"
                  f" {2 * panel.half_width_cm:.0f} cm, {count} points, sign agreement"
                  f" {agreement:.4f}, largest gap within {FACE_BAND_CM:.0f} cm of a face {gap:.2f} cm")


if __name__ == "__main__":
    main()
