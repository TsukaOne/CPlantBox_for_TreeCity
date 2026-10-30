"""A wall panel in the street frame, and where it can stand without sitting on a pipe.

A panel that leaves a corridor less than the minimum clearance is moved away from the trunk, then
made shallower, and dropped as a last resort. Only corridors count: connections and pit services
may cross a wall, as they do through a real foundation.
"""
import numpy as np

from network.primitives import TrenchSlab
from network.street import build_frame
from network.wall_measures import measure_wall_deficit_cm

PLACED, SHIFTED, SHALLOWED, SKIPPED = "placed", "shifted", "shallowed", "skipped"
SHIFT_STEP_CM = 30.0
SHIFT_ATTEMPTS = 5
SHALLOWING_STEP_CM = 10.0
MINIMUM_WALL_DEPTH_CM = 30.0
SQUARE_CORNERS = ((1, 1), (-1, 1), (-1, -1), (1, -1), (1, 1))


def build_straight_panel(name: str, lateral_cm: float, thickness_cm: float, depth_cm: float,
                         bearing_deg: float, reach_cm: float) -> TrenchSlab:
    along, across = build_frame(bearing_deg)
    centre = across * lateral_cm
    path = (tuple(centre - along * reach_cm), tuple(centre + along * reach_cm))
    return TrenchSlab(name, path, 0.5 * thickness_cm, -depth_cm)


def build_ring_panel(name: str, half_side_cm: float, thickness_cm: float, depth_cm: float,
                     bearing_deg: float) -> TrenchSlab:
    along, across = build_frame(bearing_deg)
    path = tuple(tuple((along * sign_along + across * sign_across) * half_side_cm)
                 for sign_along, sign_across in SQUARE_CORNERS)
    return TrenchSlab(name, path, 0.5 * thickness_cm, -depth_cm)


def resolve_panel(build, depth_cm: float, corridors: tuple) -> tuple:
    """build(shift_cm, depth_cm) -> TrenchSlab, the shift moving the panel away from the trunk."""
    for attempt in range(SHIFT_ATTEMPTS):
        panel = build(attempt * SHIFT_STEP_CM, depth_cm)
        if measure_wall_deficit_cm(panel, corridors) <= 0.0:
            return panel, PLACED if attempt == 0 else SHIFTED
    for shallower_cm in np.arange(depth_cm - SHALLOWING_STEP_CM, MINIMUM_WALL_DEPTH_CM,
                                  -SHALLOWING_STEP_CM):
        panel = build(0.0, float(shallower_cm))
        if measure_wall_deficit_cm(panel, corridors) <= 0.0:
            return panel, SHALLOWED
    return None, SKIPPED
