"""What a scene's v4 soil is made of, and what limits growth in it, printed for soil_scene.py."""
import numpy as np

from grid import VoxelGrid
from soil_v4.retention import ROSETTA_MAXIMUM_DENSITY_G_CM3

LIMITING_FACTORS = ("bengough", "water_scale", "aeration_scale")


def print_scene_report(scene, walls, soil, state, grid: VoxelGrid) -> None:
    pit_bottom_cm = (np.flatnonzero(soil.pit_mask.any(axis=(1, 2))).max() + 1) * grid.cell_height_cm
    seasons = ", ".join(f"{value:.2f}" for value in scene.water.seasonal_water_fraction)
    substrate = scene.pit.substrate
    print(f"city {scene.city}, patches {[patch.profile.recipe for patch in scene.mosaic.patches]}")
    print(f"pit {scene.pit.variant} {substrate.component} {substrate.compaction_class}"
          f" {substrate.fine_earth_density_g_cm3:.2f} g/cm3, bottom {pit_bottom_cm:.0f} cm")
    print(f"water by season {seasons}, drought {scene.water.drought}, runoff {scene.water.runoff}")
    print(f"walls {walls.kind}, panels {[panel.name for panel in walls.panels]},"
          f" statuses {walls.statuses}")
    print(f"mean state f_se: pit {state.growth_scale[soil.pit_mask].mean():.2f},"
          f" outside {state.growth_scale[~soil.pit_mask].mean():.2f}")

    factors = {"barrier": soil.static.rootable_fraction,
               **{name: getattr(state, name) for name in LIMITING_FACTORS}}
    weakest = np.stack(list(factors.values())).argmin(axis=0)
    for index, name in enumerate(factors):
        share = ((weakest == index) & (state.growth_scale < 1.0)).mean()
        print(f"  limited by {name}: {share:.1%} of voxels")
    capped = (soil.static.fine_earth_density_g_cm3 > ROSETTA_MAXIMUM_DENSITY_G_CM3).mean()
    print(f"  density capped for Rosetta: {capped:.1%} of voxels")
