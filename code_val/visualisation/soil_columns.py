"""One drawn profile for every profile type and city, as stacked layers.

    python3 code_val/visualisation/soil_columns.py

Colour is the fine-earth bulk density; each layer is labelled with its material, compaction class
and density. Barriers are grey and hatched.
"""
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grid import VoxelGrid
from soil_library.cities import CITIES
from soil_library.draw import SOIL, DrawnLayer, DrawnProfile, draw_profile
from soil_library.profiles import PROFILES

SEED = 7
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "output" / "soil_v4" / "soil_columns.png"
FIGURE_SIZE_INCHES = (24, 13)
DPI = 130
DENSITY_LIMITS_G_CM3 = (0.8, 2.2)
DENSITY_RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
DARK_FILL_THRESHOLD = 0.55
BARRIER_FILL = "#8a8984"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_ON_DARK = "#fcfcfb"
WATER_TABLE_COLOUR = "#eb6834"
LABEL_MIN_THICKNESS_CM = 18.0
TITLE_WIDTH_CHARACTERS = 18
LABEL_FONT_SIZE = 7
GAP_WIDTH = 1.5


def describe_layer(layer: DrawnLayer) -> str:
    if layer.kind != SOIL:
        return layer.name
    return f"{layer.component} {layer.compaction_class}\n{layer.fine_earth_density_g_cm3:.2f}"


def paint_layer(axes, layer: DrawnLayer, depth_cm: float, colours, norm) -> None:
    bottom_cm = depth_cm if layer.bottom_cm is None else layer.bottom_cm
    thickness_cm = bottom_cm - layer.top_cm
    is_soil = layer.kind == SOIL
    shade = norm(layer.fine_earth_density_g_cm3) if is_soil else 1.0
    axes.add_patch(Rectangle((0.0, layer.top_cm), 1.0, thickness_cm,
                             facecolor=colours(shade) if is_soil else BARRIER_FILL,
                             hatch=None if is_soil else "//", edgecolor=SURFACE, linewidth=GAP_WIDTH))
    if thickness_cm >= LABEL_MIN_THICKNESS_CM:
        axes.text(0.5, layer.top_cm + thickness_cm / 2, describe_layer(layer), ha="center",
                  va="center", fontsize=LABEL_FONT_SIZE,
                  color=INK_ON_DARK if shade > DARK_FILL_THRESHOLD else INK)


def paint_column(axes, profile: DrawnProfile, depth_cm: float, colours, norm) -> None:
    for layer in profile.layers:
        paint_layer(axes, layer, depth_cm, colours, norm)
    if profile.water_table_depth_cm is not None:
        axes.axhline(profile.water_table_depth_cm, color=WATER_TABLE_COLOUR, linestyle="--")
        axes.text(0.02, profile.water_table_depth_cm, "water table", va="bottom",
                  fontsize=LABEL_FONT_SIZE, color=INK)
    axes.set_xlim(0.0, 1.0)
    axes.set_ylim(depth_cm, 0.0)
    axes.set_xticks([])


def main() -> None:
    depth_cm = VoxelGrid().depth_cm
    colours = LinearSegmentedColormap.from_list("density", DENSITY_RAMP)
    norm = Normalize(*DENSITY_LIMITS_G_CM3)
    figure, grid_axes = plt.subplots(len(CITIES), len(PROFILES), figsize=FIGURE_SIZE_INCHES,
                                     sharey=True, facecolor=SURFACE, layout="constrained")
    for city_index, city in enumerate(CITIES):
        for profile_index, recipe in enumerate(PROFILES):
            axes = grid_axes[city_index, profile_index]
            rng = np.random.default_rng([SEED, profile_index, city_index])
            paint_column(axes, draw_profile(recipe, city, rng), depth_cm, colours, norm)
            title = f"{recipe.identifier}\n{textwrap.fill(recipe.name, TITLE_WIDTH_CHARACTERS)}"
            axes.set_title(title if city_index == 0 else "",
                           fontsize=LABEL_FONT_SIZE + 1, color=INK)
        grid_axes[city_index, 0].set_ylabel(f"{city.name}\ndepth (cm)", color=INK)

    figure.colorbar(plt.cm.ScalarMappable(norm, colours), ax=grid_axes, fraction=0.015,
                    label="fine-earth bulk density (g/cm3)")
    figure.suptitle(f"Drawn profile types (seed {SEED}): colour = density, hatched grey = barrier, "
                    "dashes = water table", color=INK)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=DPI, facecolor=SURFACE)
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
