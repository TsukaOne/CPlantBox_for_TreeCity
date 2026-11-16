"""Voxel grid shared by every stage of the pipeline.

Axis order is (depth, row, column) = (z, y, x). Depth index 0 is the soil
surface and increases downward. The trunk stands at the horizontal centre.
"""
from dataclasses import dataclass

import numpy as np

DEPTH_CELLS = 40
ROW_CELLS = 64
COLUMN_CELLS = 64
CELL_WIDTH_CM = 15.0
CELL_HEIGHT_CM = 9.0
# CPlantBox stops a root at the floor of the soil box but its last segment overshoots it by a fraction of a cm
# (0.26 cm at most on the sandbox trees): those points belong to the last layer, not to the outside.
FLOOR_TOLERANCE_CM = 1.0


@dataclass(frozen=True)
class VoxelGrid:
    depth_cells: int = DEPTH_CELLS
    row_cells: int = ROW_CELLS
    column_cells: int = COLUMN_CELLS
    cell_width_cm: float = CELL_WIDTH_CM
    cell_height_cm: float = CELL_HEIGHT_CM

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.depth_cells, self.row_cells, self.column_cells

    # Used to convert between world coordinates and grid indices, so the grid is always centred on the trunk.
    @property
    def half_width_cm(self) -> float:
        return 0.5 * self.column_cells * self.cell_width_cm
        
    # Used to convert between world coordinates and grid indices, so the grid is always centred on the trunk.
    @property
    def half_length_cm(self) -> float:
        return 0.5 * self.row_cells * self.cell_width_cm

    @property
    def depth_cm(self) -> float:
        return self.depth_cells * self.cell_height_cm

    def measure_layer_depths_cm(self) -> np.ndarray:
        """Depth of each layer centre, positive downward, shape (depth,)."""
        return (np.arange(self.depth_cells) + 0.5) * self.cell_height_cm

    def measure_trunk_distances_cm(self) -> np.ndarray:
        """Horizontal distance from the trunk axis, shape (row, column)."""
        columns = (np.arange(self.column_cells) + 0.5) * self.cell_width_cm - self.half_width_cm
        rows = (np.arange(self.row_cells) + 0.5) * self.cell_width_cm - self.half_length_cm
        return np.hypot(rows[:, None], columns[None, :])

    def measure_cell_centres_cm(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """World coordinates of every cell centre, each of shape (depth, row, column)."""
        depths = -self.measure_layer_depths_cm()
        rows = (np.arange(self.row_cells) + 0.5) * self.cell_width_cm - self.half_length_cm
        columns = (np.arange(self.column_cells) + 0.5) * self.cell_width_cm - self.half_width_cm
        return np.meshgrid(depths, rows, columns, indexing="ij")

    def locate_points(self, points: np.ndarray):
        """Map (N, 3) world coordinates in cm to grid indices plus an inside mask."""
        depth_cm = -points[:, 2]
        depth_index = np.floor(depth_cm / self.cell_height_cm).astype(np.intp)
        overshoot = (depth_cm >= self.depth_cm) & (depth_cm < self.depth_cm + FLOOR_TOLERANCE_CM)
        depth_index = np.where(overshoot, self.depth_cells - 1, depth_index)
        row_index = np.floor((points[:, 1] + self.half_length_cm) / self.cell_width_cm).astype(np.intp)
        column_index = np.floor((points[:, 0] + self.half_width_cm) / self.cell_width_cm).astype(np.intp)
        inside = (
            (depth_index >= 0) & (depth_index < self.depth_cells)
            & (row_index >= 0) & (row_index < self.row_cells)
            & (column_index >= 0) & (column_index < self.column_cells)
        )
        return depth_index, row_index, column_index, inside
