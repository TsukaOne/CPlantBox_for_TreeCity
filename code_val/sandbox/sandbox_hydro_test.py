"""Does hydrotropism steer roots towards water, when there is water to steer towards?
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataset.occupancy import voxelize_structural_roots
from grid import VoxelGrid
from obstacles.geometry import build_growth_geometry
from obstacles.layouts import NO_OBSTACLE, TREE_PIT_HALF_SIZE_RANGE_CM, draw_obstacle_layouts
from soil.archetypes import PIT_SUBSTRATE_ARCHETYPE, find_archetype
from soil.field import build_soil_field
from soil.growth_response import apply_bengough, apply_water_stress, compute_growth_scale
from soil.hydraulics import build_water_fields
from soil.pit import TREE_PIT_DEPTH_RANGE_CM, apply_planting_pit, build_pit_mask
from soil.profile import draw_soil_profile
from soil.wet_spots import WetSpot, apply_wet_spots, build_control_shell_mask, build_wet_spot_mask
from tree.growth import build_soil_grid, grow_root_system

SCENARIO_ARCHETYPES = (5, 2)  # sandy_dry: l'eau est limitante. medium_uniform: elle ne l'est pas.
SCENARIO_AGE_YEARS = 120.0
TREE_XML = Path("Picea_Abies_combined_v6.xml")  # l'arbre des chiffres du README
SCENARIO_SEED = 7
SCENARIO_RUNS = 24
BOOTSTRAP_DRAWS = 400
SEED_STRIDE = 100
OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "sandbox_hydro"

WET_SPOTS = (
    WetSpot("surface", depth_cm=45.0, bearing_degrees=0.0, distance_cm=150.0, radius_cm=75.0),
    WetSpot("milieu", depth_cm=135.0, bearing_degrees=180.0, distance_cm=150.0, radius_cm=75.0),
)


def build_scene(identifier: int, grid: VoxelGrid):
    rng = np.random.default_rng([SCENARIO_SEED, identifier])
    profile = draw_soil_profile(find_archetype(identifier), rng)
    ambient = build_soil_field(profile, grid, rng)
    pit = build_soil_field(draw_soil_profile(PIT_SUBSTRATE_ARCHETYPE, rng), grid, rng)
    field = apply_planting_pit(ambient, pit, build_pit_mask(
        float(rng.uniform(*TREE_PIT_HALF_SIZE_RANGE_CM)),
        float(rng.uniform(*TREE_PIT_DEPTH_RANGE_CM)), grid))
    field = apply_wet_spots(field, WET_SPOTS, grid)
    pressure_head = build_water_fields(field).pressure_head_cm
    return field, pressure_head, build_growth_geometry(draw_obstacle_layout(NO_OBSTACLE, rng), grid)


def count_spot_occupancy(geometry, elongation_grid, water_grid, grid: VoxelGrid, masks,
                        vtp_path: Path) -> dict:
    counts = {spot.name: [] for spot in WET_SPOTS}
    for run in range(SCENARIO_RUNS):
        roots = grow_root_system(geometry, elongation_grid, SCENARIO_SEED + run * SEED_STRIDE,
                                 SCENARIO_AGE_YEARS, TREE_XML, vtp_path if run == 0 else None,
                                 water_lookup=water_grid)
        occupancy = voxelize_structural_roots(roots.segments, roots.subtypes, grid).grid
        for spot in WET_SPOTS:
            inside, shell = masks[spot.name]
            counts[spot.name].append((occupancy[inside].sum(), occupancy[shell].sum()))
    return {name: np.array(pairs, dtype=float) for name, pairs in counts.items()}


def summarise_ratio(pairs: np.ndarray, inside_voxels: int, shell_voxels: int,
                    rng: np.random.Generator) -> tuple[float, float]:
    """Pooled rate ratio, with a bootstrap over seeds for the uncertainty. Averaging one ratio
    per seed instead is biased both ways: a seed that misses the pocket contributes a hard zero,
    a seed that grazes it contributes an unbounded number."""
    def ratio(sample: np.ndarray) -> float:
        control = sample[:, 1].sum() / shell_voxels
        return sample[:, 0].sum() / inside_voxels / control if control > 0 else np.nan

    draws = [ratio(pairs[rng.integers(0, len(pairs), len(pairs))]) for _ in range(BOOTSTRAP_DRAWS)]
    return ratio(pairs), float(np.nanstd(draws))


def run_archetype(identifier: int, grid: VoxelGrid) -> None:
    field, pressure_head, geometry = build_scene(identifier, grid)
    water = apply_water_stress(field.available_water_fraction)
    mechanical = apply_bengough(field.penetrometer_mpa)
    growth_scale = compute_growth_scale(field.penetrometer_mpa, field.available_water_fraction)
    elongation_grid = build_soil_grid(growth_scale, grid)
    water_grid = build_soil_grid(water, grid)
    masks = {spot.name: (build_wet_spot_mask(spot, grid), build_control_shell_mask(spot, grid))
             for spot in WET_SPOTS}

    name = find_archetype(identifier).name
    print(f"\n=== {name} ===")
    for spot in WET_SPOTS:
        inside, shell = masks[spot.name]
        print(f"  poche {spot.name:<8s} {int(inside.sum()):4d} voxels contre {int(shell.sum()):5d} "
              f"de temoin | eau {water[inside].mean():.3f} contre {water[shell].mean():.3f}"
              f" | bengough {mechanical[shell].mean():.3f}"
              f" | f_se {growth_scale[inside].mean():.3f} contre {growth_scale[shell].mean():.3f}")

    rng = np.random.default_rng(SCENARIO_SEED)
    for label, lookup in (("sans hydrotropisme", None), ("avec hydrotropisme", water_grid)):
        counts = count_spot_occupancy(geometry, elongation_grid, lookup, grid, masks,
                                      OUTPUT_DIRECTORY / f"{name}_{label.split()[0]}.vtp")
        parts = []
        for spot in WET_SPOTS:
            inside, shell = masks[spot.name]
            ratio, spread = summarise_ratio(counts[spot.name], int(inside.sum()),
                                            int(shell.sum()), rng)
            parts.append(f"{spot.name} {ratio:.2f} +/- {spread:.2f}")
        print(f"  {label:<20s} rapport poche/temoin : {'  '.join(parts)}")


def main() -> None:
    grid = VoxelGrid()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    print(f"{SCENARIO_RUNS} graines, {SCENARIO_AGE_YEARS:.0f} ans, sortie {OUTPUT_DIRECTORY}")
    for identifier in SCENARIO_ARCHETYPES:
        run_archetype(identifier, grid)


if __name__ == "__main__":
    main()
