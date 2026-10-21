"""Paired scenes side by side: the v3 root target and the v4 one, seen from the side.

    python3 code_val/visualisation/pilot_pairs.py code_val/dataset_v3 code_val/pilot_v4 1 13 101

The occupancy is summed along the rows (y) of the box, so each panel is depth against x. Both
panels of a scene share one colour scale.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compare_pilot_v4 import GRID, read_scene
from visualisation.soil_columns import DENSITY_RAMP, INK, SURFACE

OUTPUT_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "output" / "pilot_v4"
PANEL_WIDTH_INCHES = 6.5
PANEL_HEIGHT_INCHES = 2.6
TITLE_FONT_SIZE = 8
DPI = 120
VERSIONS = ("v3", "v4")


def describe(descriptor: dict) -> str:
    configuration = descriptor["configuration"]
    slot = configuration["slot"]
    return (f"{slot['profile'] or 'fill'} {slot['city']}, pit {slot['pit_variant']},"
            f" walls {configuration['walls']['kind']},"
            f" age {configuration['tree']['age_years']:.0f} y")


def paint_pair(axes_pair, identifier: int, targets: tuple, description: str, colours):
    extent = (-GRID.half_width_cm, GRID.half_width_cm, GRID.depth_cm, 0.0)
    sides = [target.sum(axis=1) for target in targets]
    top = max(side.max() for side in sides)
    for axes, version, side, target in zip(axes_pair, VERSIONS, sides, targets):
        image = axes.imshow(side, extent=extent, aspect="auto", cmap=colours, vmin=0.0, vmax=top)
        axes.set_title(f"scene {identifier} {version}: mass {target.mean():.5f}"
                       + (f" | {description}" if version == VERSIONS[-1] else ""),
                       fontsize=TITLE_FONT_SIZE, color=INK)
        axes.set_ylabel("depth (cm)", color=INK)
    return image


def main() -> None:
    v3_directory, v4_directory = Path(sys.argv[1]), Path(sys.argv[2])
    identifiers = [int(argument) for argument in sys.argv[3:]]
    colours = LinearSegmentedColormap.from_list("occupancy", (SURFACE,) + DENSITY_RAMP)
    figure, grid_axes = plt.subplots(len(identifiers), len(VERSIONS), squeeze=False,
                                     facecolor=SURFACE, layout="constrained",
                                     figsize=(len(VERSIONS) * PANEL_WIDTH_INCHES,
                                              len(identifiers) * PANEL_HEIGHT_INCHES))
    for row, identifier in enumerate(identifiers):
        _, v3_target = read_scene(v3_directory, identifier)
        v4_descriptor, v4_target = read_scene(v4_directory, identifier)
        image = paint_pair(grid_axes[row], identifier, (v3_target, v4_target),
                           describe(v4_descriptor), colours)
        figure.colorbar(image, ax=grid_axes[row].tolist(), label="occupancy summed along y")
    for axes in grid_axes[-1]:
        axes.set_xlabel("x (cm)", color=INK)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIRECTORY / f"pairs_{'_'.join(map(str, identifiers))}.png"
    figure.savefig(path, dpi=DPI, facecolor=SURFACE)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
