"""A vertical section through the trunk, across the street (along y), of a soil .vti written by
soil_scene.py.

    python3 code_val/visualisation/soil_section.py output/soil_v4/scene_01001_P08_helsinki_none.vti

Black lines outline the planting pit, white lines the pipes, orange lines the walls.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paraview import read_voxel_grids
from soil_v4.resistance import MAXIMUM_RESISTANCE_MPA
from visualisation.soil_columns import DENSITY_LIMITS_G_CM3, DENSITY_RAMP, INK, SURFACE
from visualisation.soil_scene import GRID

PANELS = (("density", "fine-earth density (g/cm3)", DENSITY_LIMITS_G_CM3),
          ("resistance_mean", "resistance, mean state (MPa)", (0.0, MAXIMUM_RESISTANCE_MPA)),
          ("air_mean", "air-filled porosity, mean state", (0.0, 0.4)),
          ("rootable", "rootable fraction", (0.0, 1.0)),
          ("f_se_mean", "f_se, mean state", (0.0, 1.0)),
          ("f_se_summer", "f_se, summer", (0.0, 1.0)))
PANEL_COLUMNS = 3
FIGURE_SIZE_INCHES = (18, 8)
DPI = 120
OUTLINE_LEVEL = 0.5
WALL_COLOUR = "#eb6834"


def paint_section(axes, fields: dict, name: str, label: str, limits: tuple, colours) -> None:
    column = GRID.column_cells // 2
    extent = (-GRID.half_length_cm, GRID.half_length_cm, GRID.depth_cm, 0.0)
    image = axes.imshow(fields[name][:, :, column], extent=extent, aspect="auto", cmap=colours,
                        vmin=limits[0], vmax=limits[1], interpolation="nearest")
    rows_cm = (np.arange(GRID.row_cells) + 0.5) * GRID.cell_width_cm - GRID.half_length_cm
    for outline, colour in (("pit", INK), ("pipes", SURFACE), ("walls", WALL_COLOUR)):
        axes.contour(rows_cm, GRID.measure_layer_depths_cm(),
                     fields[outline][:, :, column] > OUTLINE_LEVEL, levels=[OUTLINE_LEVEL],
                     colors=colour)
    axes.set_title(label, color=INK)
    axes.set_xlabel("distance from the trunk across the street, y (cm)", color=INK)
    axes.set_ylabel("depth (cm)", color=INK)
    plt.colorbar(image, ax=axes)


def main() -> None:
    path = Path(sys.argv[1])
    fields = read_voxel_grids(path, GRID)
    colours = LinearSegmentedColormap.from_list("magnitude", DENSITY_RAMP)
    rows = -(-len(PANELS) // PANEL_COLUMNS)
    figure, grid_axes = plt.subplots(rows, PANEL_COLUMNS, figsize=FIGURE_SIZE_INCHES,
                                     facecolor=SURFACE, layout="constrained")
    for axes, (name, label, limits) in zip(grid_axes.ravel(), PANELS):
        paint_section(axes, fields, name, label, limits, colours)
    figure.suptitle(f"{path.stem}: section through the trunk", color=INK)
    output = path.with_suffix(".png")
    figure.savefig(output, dpi=DPI, facecolor=SURFACE)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
