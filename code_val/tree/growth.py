"""Grow one root system in CPlantBox and return its segments.

The soil acts through f_se, the elongation scale CPlantBox reads at every apex, and
optionally through f_sa, the insertion angle scale read once at the birth of each lateral.
Both are pushed into a native EquidistantGrid3D so the hot loop stays in C++; a Python
SoilLookUp subclass would be called once per apex per time step.
"""
from pathlib import Path
from typing import NamedTuple, Optional

import numpy as np
import plantbox as pb

from grid import VoxelGrid
from tree.attributes import DAYS_PER_YEAR

TIME_STEP_DAYS = 10.0
HYDROTROPIC_SUBTYPES = (5, 6)
HYDROTROPISM = 3 
# TropismS
HYDROTROPIC_TROPISM_STRENGTH = 0.10
XML_PATH = Path(__file__).resolve().parent.parent / "parameters" / "Picea_Abies_combined_v6.xml"


class RootSystem(NamedTuple):
    segments: np.ndarray
    subtypes: np.ndarray


def pad_for_lookup(values: np.ndarray, grid: VoxelGrid) -> np.ndarray:
    """CPlantBox maps a coordinate onto n-1 intervals, so the lookup needs one extra node
    per axis to land on exactly the same cells as the voxel grid. Its depth index runs
    upward, hence the flip. The replicated border makes the field flat outside the domain."""
    padded = np.empty((grid.depth_cells + 1, grid.row_cells + 1, grid.column_cells + 1))
    padded[:-1, :-1, :-1] = values[::-1, :, :]
    padded[-1, :, :] = padded[-2, :, :]
    padded[:, -1, :] = padded[:, -2, :]
    padded[:, :, -1] = padded[:, :, -2]
    return padded


def build_soil_grid(values: np.ndarray, grid: VoxelGrid) -> pb.EquidistantGrid3D:
    lookup = pb.EquidistantGrid3D(
        -grid.half_width_cm, grid.half_width_cm, grid.column_cells + 1,
        -grid.half_length_cm, grid.half_length_cm, grid.row_cells + 1,
        -grid.depth_cm, 0.0, grid.depth_cells + 1)
    lookup.data = pad_for_lookup(values, grid).ravel().tolist()
    return lookup


def build_interpolated_soil_grid(values: np.ndarray, grid: VoxelGrid) -> pb.InterpolatedGrid3D:
    """Same data, read with trilinear interpolation. A tropism samples candidate directions
    well under a centimetre apart, so it needs a field whose gradient is not zero inside a cell."""
    lookup = pb.InterpolatedGrid3D(
        -grid.half_width_cm, grid.half_width_cm, grid.column_cells + 1,
        -grid.half_length_cm, grid.half_length_cm, grid.row_cells + 1,
        -grid.depth_cm, 0.0, grid.depth_cells + 1)
    lookup.data = pad_for_lookup(values, grid).ravel().tolist()
    return lookup


def assign_soil_hooks(plant: pb.Plant, elongation_grid, angle_grid) -> None:
    """f_sa is left at its default on subType 1: CPlantBox skips it when the parent is the
    seed, so wiring it there would be silently dead."""
    for parameter in plant.getOrganRandomParameter(pb.OrganTypes.root):
        parameter.f_se = elongation_grid
        if angle_grid is not None:
            parameter.f_sa = angle_grid


def assign_hydrotropism(plant: pb.Plant, water_lookup) -> None:
    """setSoil() has to precede initialize(): the tropism callbacks are built there, out of
    the soil the plant holds at that instant. Feed it the dimensionless water scale rather
    than raw matric potential - CPlantBox blends hydro and gravitropism 10:1, and a psi
    running to 1e5 would swamp the gravitropic term instead of outweighing it."""
    plant.setSoil(water_lookup)
    for parameter in plant.getOrganRandomParameter(pb.OrganTypes.root):
        if parameter.subType in HYDROTROPIC_SUBTYPES:
            parameter.tropismT = HYDROTROPISM
            parameter.tropismS = HYDROTROPIC_TROPISM_STRENGTH


def extract_root_system(plant: pb.Plant) -> RootSystem:
    edges = np.asarray([[int(s.x), int(s.y)] for s in plant.getSegments()], dtype=int)
    if edges.size == 0:
        return RootSystem(np.zeros((0, 6)), np.zeros(0, dtype=int))
    nodes = np.asarray([[n.x, n.y, n.z] for n in plant.getNodes()], dtype=float)
    segments = np.hstack([nodes[edges[:, 0]], nodes[edges[:, 1]]])
    subtypes = np.rint(pb.SegmentAnalyser(plant).getParameter("subType")).astype(int)
    return RootSystem(segments, subtypes)


def create_plant(geometry, elongation_grid, seed: int, angle_grid: Optional[pb.EquidistantGrid3D], water_lookup: Optional[pb.SoilLookUp]) -> pb.Plant:
    plant = pb.Plant()
    plant.readParameters(str(XML_PATH))
    plant.setSeed(seed)
    plant.setGeometry(geometry)
    assign_soil_hooks(plant, elongation_grid, angle_grid)
    if water_lookup is not None:
        assign_hydrotropism(plant, water_lookup)
    plant.initialize(False)
    return plant


def grow_plant(geometry, elongation_grid, seed: int, age_years: float, vtp_path: Optional[Path] = None, time_step_days: float = TIME_STEP_DAYS, angle_grid: Optional[pb.EquidistantGrid3D] = None, water_lookup: Optional[pb.SoilLookUp] = None) -> pb.Plant:
    plant = create_plant(geometry, elongation_grid, seed, angle_grid, water_lookup)
    for _ in range(round(age_years * DAYS_PER_YEAR / time_step_days)):
        plant.simulate(time_step_days, False)

    if vtp_path is not None:
        vtp_path.parent.mkdir(parents=True, exist_ok=True)
        plant.write(str(vtp_path))
    return plant


def grow_root_system(geometry, elongation_grid, seed: int, age_years: float, vtp_path: Optional[Path] = None, time_step_days: float = TIME_STEP_DAYS, angle_grid: Optional[pb.EquidistantGrid3D] = None, water_lookup: Optional[pb.SoilLookUp] = None) -> RootSystem:
    return extract_root_system(grow_plant(geometry, elongation_grid, seed, age_years, vtp_path,
                                          time_step_days, angle_grid, water_lookup))
