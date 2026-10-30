"""Penetration resistance, air and f_se down every drawn profile, season by season, one figure
per city. The profiles are the ones of soil_columns.png (same seeds).

    python3 code_val/visualisation/soil_states.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grid import VoxelGrid
from soil.growth_response import STOPPED_GROWTH_RESISTANCE_MPA
from soil_library.cities import CITIES
from soil_library.draw import draw_profile
from soil_library.profiles import PROFILES
from soil_v4.column import build_column
from soil_v4.resistance import MAXIMUM_RESISTANCE_MPA
from soil_v4.retention import estimate_retention
from soil_v4.state import compute_soil_state
from soil_v4.water import (MEAN_STATE, SEASONS, build_available_water, build_saturated_fraction,
                           draw_water_regime, list_state_fractions)
from visualisation.soil_columns import INK, LABEL_FONT_SIZE, SEED, SURFACE

TREE_STOPPED_GROWTH_RESISTANCE_MPA = 3.0
OUTPUT_DIRECTORY = Path(__file__).resolve().parent.parent.parent / "output" / "soil_v4"
FIGURE_SIZE_INCHES = (26, 12)
DPI = 110
SEASON_STYLES = {"spring": ("#2a78d6", "-"), "summer": ("#eb6834", "-"),
                 "autumn": ("#1baf7a", "--"), "winter": ("#eda100", ":")}
SEASON_LINE_WIDTH = 1.0
MEAN_LINE_WIDTH = 2.0
BARRIER_SHADE = "#d9d8d4"
THRESHOLD_COLOUR = "#8a8984"
QUANTITIES = (("penetrometer_mpa", "resistance (MPa)", MAXIMUM_RESISTANCE_MPA),
              ("air_filled_porosity", "air-filled porosity", 0.4),
              ("growth_scale", "f_se", 1.0))


def compute_states(recipe, city, profile_index: int, city_index: int, grid: VoxelGrid) -> tuple:
    rng = np.random.default_rng([SEED, profile_index, city_index])
    profile = draw_profile(recipe, city, rng)
    column = build_column(profile, grid, rng)
    regime = draw_water_regime(city, profile.sealed_surface, rng)
    retention = estimate_retention(column)
    saturated = build_saturated_fraction(profile.water_table_depth_cm, grid)
    sealed_share = float(profile.sealed_surface)
    states = {name: compute_soil_state(column, retention, build_available_water(fraction, sealed_share),
                                       saturated, STOPPED_GROWTH_RESISTANCE_MPA)
              for name, fraction in list_state_fractions(regime).items()}
    tree_state = compute_soil_state(column, retention, states[MEAN_STATE].available_water_fraction,
                                    saturated, TREE_STOPPED_GROWTH_RESISTANCE_MPA)
    return column, states, tree_state, regime


def paint_panel(axes, depths_cm, column, states: dict, tree_state, name: str, limit: float) -> None:
    axes.fill_betweenx(depths_cm, 0.0, limit, where=column.rootable_fraction < 1.0,
                       color=BARRIER_SHADE, step="mid")
    for season in SEASONS:
        colour, style = SEASON_STYLES[season]
        axes.plot(getattr(states[season], name), depths_cm, color=colour, linestyle=style,
                  linewidth=SEASON_LINE_WIDTH, label=season)
    axes.plot(getattr(states[MEAN_STATE], name), depths_cm, color=INK, linewidth=MEAN_LINE_WIDTH,
              label=f"mean, stop {STOPPED_GROWTH_RESISTANCE_MPA} MPa")
    if name == "growth_scale":
        axes.plot(tree_state.growth_scale, depths_cm, color=INK, linestyle="--",
                  linewidth=MEAN_LINE_WIDTH, label=f"mean, stop {TREE_STOPPED_GROWTH_RESISTANCE_MPA} MPa")
    if name == "penetrometer_mpa":
        for threshold in (STOPPED_GROWTH_RESISTANCE_MPA, TREE_STOPPED_GROWTH_RESISTANCE_MPA):
            axes.axvline(threshold, color=THRESHOLD_COLOUR, linestyle=":")
    axes.set_xlim(0.0, limit)
    axes.tick_params(labelsize=LABEL_FONT_SIZE)


def plot_city(city, city_index: int, grid: VoxelGrid) -> Path:
    depths_cm = grid.measure_layer_depths_cm()
    figure, grid_axes = plt.subplots(len(QUANTITIES), len(PROFILES), figsize=FIGURE_SIZE_INCHES,
                                     sharey=True, facecolor=SURFACE, layout="constrained")
    for profile_index, recipe in enumerate(PROFILES):
        column, states, tree_state, regime = compute_states(recipe, city, profile_index, city_index, grid)
        for row, (name, label, limit) in enumerate(QUANTITIES):
            axes = grid_axes[row, profile_index]
            paint_panel(axes, depths_cm, column, states, tree_state, name, limit)
            axes.set_xlabel(label, fontsize=LABEL_FONT_SIZE, color=INK)
        water = ", ".join(f"{value:.2f}" for value in regime.seasonal_water_fraction)
        grid_axes[0, profile_index].set_title(f"{recipe.identifier}\nwater {water}",
                                              fontsize=LABEL_FONT_SIZE, color=INK)
    grid_axes[0, 0].set_ylim(grid.depth_cm, 0.0)
    for row in range(len(QUANTITIES)):
        grid_axes[row, 0].set_ylabel("depth (cm)", color=INK)
    handles, labels = grid_axes[-1, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="outside lower center", ncol=len(labels))
    figure.suptitle(f"{city.name}: seasonal soil states of the drawn profiles (seed {SEED}),"
                    " grey = barrier", color=INK)
    path = OUTPUT_DIRECTORY / f"soil_states_{city.name.lower()}.png"
    figure.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(figure)
    return path


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    grid = VoxelGrid()
    for city_index, city in enumerate(CITIES):
        print(f"wrote {plot_city(city, city_index, grid)}")


if __name__ == "__main__":
    main()
