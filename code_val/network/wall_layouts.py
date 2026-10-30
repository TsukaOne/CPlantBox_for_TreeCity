"""The wall module: a building foundation, the two walls of a narrow strip between a facade and a
kerb, or the walls of a confined planting pit. All are vertical barriers no root crosses.

Buildings stand on the sidewalk side, opposite the kerb. Every dimension is an estimate.
"""
from dataclasses import dataclass

import numpy as np

from grid import VoxelGrid
from network.primitives import TrenchSlab
from network.street import CORRIDOR, StreetScene
from network.wall_panels import build_ring_panel, build_straight_panel, resolve_panel

NO_WALL, FOUNDATION, NARROW_STRIP, CONFINED_PIT = "none", "foundation", "narrow_strip", "confined_pit"
WALL_KINDS = (NO_WALL, FOUNDATION, NARROW_STRIP, CONFINED_PIT)
WALL_PROBABILITIES = (0.55, 0.20, 0.10, 0.15)

FACADE_DISTANCE_RANGE_CM = (240.0, 450.0)
FOUNDATION_DEPTH_RANGE_CM = (150.0, 300.0)
FOUNDATION_THICKNESS_RANGE_CM = (30.0, 50.0)
STRIP_GAP_RANGE_CM = (20.0, 60.0)
STRIP_DEPTH_RANGE_CM = (40.0, 100.0)
STRIP_THICKNESS_RANGE_CM = (20.0, 30.0)
PIT_WALL_THICKNESS_RANGE_CM = (15.0, 25.0)


@dataclass(frozen=True)
class WallModule:
    kind: str
    panels: tuple[TrenchSlab, ...]
    statuses: tuple[str, ...]


def draw_wall_kind(rng: np.random.Generator) -> str:
    return WALL_KINDS[rng.choice(len(WALL_KINDS), p=WALL_PROBABILITIES)]


def request_foundation(street: StreetScene, pit_radius_cm: float, pit_depth_cm: float,
                       reach_cm: float, rng: np.random.Generator) -> list:
    facade_cm = float(rng.uniform(*FACADE_DISTANCE_RANGE_CM))
    thickness_cm = float(rng.uniform(*FOUNDATION_THICKNESS_RANGE_CM))

    def build_foundation(shift_cm: float, depth_cm: float) -> TrenchSlab:
        lateral_cm = -(facade_cm + shift_cm + 0.5 * thickness_cm)
        return build_straight_panel(FOUNDATION, lateral_cm, thickness_cm, depth_cm,
                                    street.bearing_deg, reach_cm)

    return [(build_foundation, float(rng.uniform(*FOUNDATION_DEPTH_RANGE_CM)))]


def request_narrow_strip(street: StreetScene, pit_radius_cm: float, pit_depth_cm: float,
                         reach_cm: float, rng: np.random.Generator) -> list:
    facade_cm = pit_radius_cm + float(rng.uniform(*STRIP_GAP_RANGE_CM))
    thickness_cm = float(rng.uniform(*STRIP_THICKNESS_RANGE_CM))

    def build_facade(shift_cm: float, depth_cm: float) -> TrenchSlab:
        lateral_cm = -(facade_cm + shift_cm + 0.5 * thickness_cm)
        return build_straight_panel("strip_facade", lateral_cm, thickness_cm, depth_cm,
                                    street.bearing_deg, reach_cm)

    def build_kerb(shift_cm: float, depth_cm: float) -> TrenchSlab:
        lateral_cm = street.curb_offset_cm + shift_cm + 0.5 * thickness_cm
        return build_straight_panel("strip_kerb", lateral_cm, thickness_cm, depth_cm,
                                    street.bearing_deg, reach_cm)

    return [(build_facade, float(rng.uniform(*STRIP_DEPTH_RANGE_CM))),
            (build_kerb, float(rng.uniform(*STRIP_DEPTH_RANGE_CM)))]


def request_confined_pit(street: StreetScene, pit_radius_cm: float, pit_depth_cm: float,
                         reach_cm: float, rng: np.random.Generator) -> list:
    thickness_cm = float(rng.uniform(*PIT_WALL_THICKNESS_RANGE_CM))

    def build_pit_walls(shift_cm: float, depth_cm: float) -> TrenchSlab:
        half_side_cm = pit_radius_cm + shift_cm + 0.5 * thickness_cm
        return build_ring_panel(CONFINED_PIT, half_side_cm, thickness_cm, depth_cm,
                                street.bearing_deg)

    return [(build_pit_walls, pit_depth_cm)]


REQUESTS = {FOUNDATION: request_foundation, NARROW_STRIP: request_narrow_strip,
            CONFINED_PIT: request_confined_pit}


def draw_wall_module(kind: str, street: StreetScene, pit_radius_cm: float, pit_depth_cm: float,
                     grid: VoxelGrid, rng: np.random.Generator) -> WallModule:
    if kind == NO_WALL:
        return WallModule(kind, (), ())
    corridors = tuple(run for run in street.utilities if run.role == CORRIDOR)
    reach_cm = grid.half_width_cm + grid.half_length_cm
    requests = REQUESTS[kind](street, pit_radius_cm, pit_depth_cm, reach_cm, rng)
    resolved = [resolve_panel(build, depth_cm, corridors) for build, depth_cm in requests]
    return WallModule(kind, tuple(panel for panel, _ in resolved if panel is not None),
                      tuple(status for _, status in resolved))
