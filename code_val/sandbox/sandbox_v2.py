"""Grow a few contrasted scenes (CPlantBox xml chosen with --tree) and dump one VTP plus one occupancy grid each.
"""
import argparse
import sys
import time
from pathlib import Path
import datetime as dt
import dataclasses

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import root_metrics
import sandbox_v1
from dataset.occupancy import compute_occupancy_probability, voxelize_structural_roots
from grid import VoxelGrid
from obstacles.coverage import build_coverage, build_label_field
from obstacles.intrusion import find_intrusions, measure_largest_growth_step_cm
from obstacles.layouts import TREE_PIT_HALF_SIZE_RANGE_CM
from obstacles.leakage import build_plume_ramp, build_scene_leaks
from obstacles.shapes import build_scene_shapes
from obstacles.street import draw_street_scene
from obstacles.walls import PIPE_EXCLUSION_MARGIN_CM, build_street_geometry
from paraview import write_voxel_grids
from soil.archetypes import PIT_SUBSTRATE_ARCHETYPE, find_archetype
from soil.field import build_soil_field
from soil.fill import apply_fills, measure_natural_share
from soil.growth_response import (apply_bengough, apply_water_stress, compute_angle_scale,
								  compute_growth_scale)
from soil.hydraulics import build_water_fields
from soil.leak import apply_leaks
from soil.pit import TREE_PIT_DEPTH_RANGE_CM, apply_planting_pit, build_pit_mask
from soil.profile import draw_soil_profile
from tree.growth import (build_interpolated_soil_grid, build_soil_grid, extract_root_system,
						 grow_plant)
from tree.species import PARAMETERS_DIRECTORY
from generator.polylines import extract_polydata

SANDBOX_PARENT = Path(__file__).resolve().parent
# Archetype identifiers (soil/archetypes.py): 1 loose_uniform, 2 medium_uniform, 3 compacted_uniform,
# 4 very_compacted, 5 sandy_dry, 6 clayey_wet, 7 compacted_top, 8 hardpan_below, 9 hard_base_at_50,
# 10 sand_over_clay
SANDBOX_ARCHETYPE_IDENTIFIERS = (1, )
SANDBOX_AGE_YEARS = 120.0
SANDBOX_SEED = 7
SANDBOX_RUNS = 50
SEED_STRIDE = 100
VTP_RUNS_KEPT = 3


def measure_maximum_depth_cm(segments: np.ndarray) -> float:
	if len(segments) == 0:
		return 0.0
	return float(-min(segments[:, 2].min(), segments[:, 5].min()))


def grow_repeatedly(geometry, elongation_grid, angle_grid, water_lookup, shapes,
					grid: VoxelGrid, vtp_path: Path, tree: Path):
	segment_counts, depths, occupancies, intrusions = [], [], [], {}
	per_tree_records, per_tree_lengths = [], []
	date = dt.datetime.now().strftime("%Y%m%d_%H-%M")
	for run in range(SANDBOX_RUNS):
		path = vtp_path.with_name(f"{vtp_path.stem}_{date}_seed{run:02d}.vtp") if run < VTP_RUNS_KEPT else None
		plant = grow_plant(geometry, elongation_grid, SANDBOX_SEED + run * SEED_STRIDE,
						   SANDBOX_AGE_YEARS, tree, path,
						   angle_grid=angle_grid, water_lookup=water_lookup)
		polydata = extract_polydata(plant)
		per_tree_records.append(root_metrics.measure_root_shapes(polydata))
		per_tree_lengths.append(root_metrics.measure_length_distribution(polydata))
		roots = extract_root_system(plant)
		segment_counts.append(len(roots.segments))
		depths.append(measure_maximum_depth_cm(roots.segments))
		occupancies.append(voxelize_structural_roots(roots.segments, roots.subtypes, grid).grid)
		for name, depth_cm in find_intrusions(roots.segments, shapes).items():
			intrusions[name] = max(intrusions.get(name, 0.0), depth_cm)
	return (np.array(segment_counts), np.array(depths), occupancies, intrusions, 
         	per_tree_records, per_tree_lengths)


def save_scene_fields(directory: Path, name: str, fields: dict[str, np.ndarray],
					  occupancy: np.ndarray, grid: VoxelGrid) -> None:
	# np.save(directory / f"{name}.npy", occupancy)
	date = dt.datetime.now().strftime("%Y%m%d_%H-%M")
	write_voxel_grids(directory / f"{name}_{date}.vti", fields, grid)


def build_soil_v2(profile, scene, shapes, coverages, sources, grid, rng):
	# Shared noise, per-voxel Rosetta, planting pit, trench fills, leaks that soften as well as wet.
	# Order matters: a fill arrives with its resistance and its moisture already consistent, so it
	# lands before the leak rescales resistance from moisture, and is never rescaled itself.
	ambient = build_soil_field(profile, grid, rng)
	pit = build_soil_field(draw_soil_profile(PIT_SUBSTRATE_ARCHETYPE, rng), grid, rng)
	field = apply_planting_pit(ambient, pit,
							   build_pit_mask(scene.pit_radius_cm, scene.pit_depth_cm, grid))

	field = apply_fills(field, tuple(horizon for _, horizon in shapes.fills), coverages)
	field = apply_leaks(field, sources, measure_natural_share(coverages, grid.shape))

	return (field, build_water_fields(field).pressure_head_cm,
			compute_growth_scale(field.penetrometer_mpa, field.available_water_fraction))


def build_soil_v1(profile, scene, shapes, coverages, sources, grid, rng):
	# Independent noise per channel, Rosetta per horizon; both pipelines multiply now
	field = sandbox_v1.build_soil_field(profile, grid, rng)
	field = apply_fills(field, tuple(horizon for _, horizon in shapes.fills), coverages)
	field = apply_leaks(field, sources, measure_natural_share(coverages, grid.shape))
	pressure_head = sandbox_v1.build_pressure_head_field(field, profile, grid)
	return (field, pressure_head,
			sandbox_v1.compute_growth_scale(field.penetrometer_mpa, field.available_water_fraction))


def run_scene(archetype_identifier: int, grid: VoxelGrid, build_soil, directory: Path, is_scale_angle: bool, is_hydro: bool, no_street: bool, tree: Path) -> None:
	# Random soil profile, drawn before either pipeline so both modes get the same soil
	#---- SOIL -----
	rng = np.random.default_rng([SANDBOX_SEED, archetype_identifier])
	profile = draw_soil_profile(find_archetype(archetype_identifier), rng)

	# ---- SCENE -----
	scene_rng = np.random.default_rng(SANDBOX_SEED)
	scene = draw_street_scene(float(scene_rng.uniform(*TREE_PIT_HALF_SIZE_RANGE_CM)),float(scene_rng.uniform(*TREE_PIT_DEPTH_RANGE_CM)),grid.half_width_cm, scene_rng)
	if no_street:
		scene = dataclasses.replace(scene, utilities=())   # NamedTuple : scene._replace(utilities=())


	street_leaks = build_scene_leaks(scene.utilities, scene_rng)
	shapes = build_scene_shapes(scene, grid)
	sources = tuple((build_plume_ramp(leak, grid), leak.available_water_fraction) for leak in street_leaks)
	if no_street:
		assert not shapes.lumens and not shapes.fills and not sources, "des tuyaux ou remblais restent dans la scene"

	coverages = tuple(build_coverage(shape, grid) for shape, _ in shapes.fills)

	field, pressure_head, growth_scale = build_soil(profile, scene, shapes, coverages, sources, grid, rng)

	#---- MECHANICAL -----
	mechanical = apply_bengough(field.penetrometer_mpa)
	water = apply_water_stress(field.available_water_fraction)

	#---- HOOKS -----
	elongation_grid = build_soil_grid(growth_scale, grid)
	angle_scale = compute_angle_scale(field.penetrometer_mpa) if is_scale_angle else None
	angle_grid = build_soil_grid(angle_scale, grid) if is_scale_angle else None
	water_lookup = build_interpolated_soil_grid(water, grid) if is_hydro else None

	growth_started = time.perf_counter()

	geometry = build_street_geometry(shapes, grid)
	(segment_counts, depths, occupancies, intrusions, 
  	per_tree_records, per_tree_lengths) = grow_repeatedly( geometry, elongation_grid, angle_grid, water_lookup, shapes, grid, directory / f"{profile.archetype_name}.vtp", tree)
	date = dt.datetime.now().strftime("%Y%m%d_%H-%M")
	root_metrics.save_root_records(directory / f"{profile.archetype_name}_{date}_roots.csv", per_tree_records)
	root_metrics.save_length_distribution(directory / f"{profile.archetype_name}_{date}_profile.csv", per_tree_lengths)
 
	growth_seconds = time.perf_counter() - growth_started

	# Compute occupany voxels grid
	ensemble = compute_occupancy_probability(occupancies)

	mean_radius_cm, mean_depth_cm = root_metrics.measure_occupancy_shape(ensemble.probability, grid)
	scene_fields = {"f_se": growth_scale, "bengough": mechanical, "eau": water,
					"psi": pressure_head, "occupancy": ensemble.probability,
					"fuites": np.max([ramp for ramp, _ in sources], axis=0) if sources
					else np.zeros(grid.shape, np.float32),
					# Numbered in the order of street.NETWORK_TEMPLATES, so a pipe is identifiable.
					"tuyaux": build_label_field(shapes.lumens, grid),
					"remblais": 1.0 - measure_natural_share(coverages, grid.shape)}
	if angle_scale is not None:
		scene_fields["f_sa"] = angle_scale
	save_scene_fields(directory, profile.archetype_name, scene_fields, ensemble.probability, grid)

	print(f"{profile.archetype_name:<18s}"
		  f" bengough {mechanical.mean():.3f}"
		  f" eau {water.mean():.3f}"
		  f" -> f_se {growth_scale.mean():.3f}"
		  f"{f' f_sa {angle_scale.mean():.3f}' if is_scale_angle else ''}"
		  f"{' hydro' if is_hydro else ''}")
	print(f"{'':<18s}"
		  f" segments {segment_counts.mean():7.0f} +/- {segment_counts.std():5.0f}"
		  f" profondeur {depths.mean():6.1f} +/- {depths.std():5.1f} cm"
		  f" support {(ensemble.probability > 0).mean():.4f}"
		  f" masse {ensemble.probability.mean():.5f}"
		  f" rayon {mean_radius_cm:5.1f} cm profondeur_moy {mean_depth_cm:5.1f} cm"
		  f" croissance {growth_seconds:6.2f} s", flush=True)
	leaking = ",".join(leak.name for leak in street_leaks) or "aucune"
	print(f"{'':<18s}"
		  f" fuites {leaking}"
		  f" intrusions {intrusions or 'aucune'}", flush=True)
	root_metrics.print_shape_summary(per_tree_records)
	root_metrics.print_depth_summary(per_tree_lengths)


def parse_arguments() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--v1", action="store_true",
						help="pipeline sol de v1, pour comparer les memes scenes")
	parser.add_argument("--f-sa", action="store_true",
						help="brancher aussi f_sa, l'angle d'insertion des laterales")
	parser.add_argument("--hydro", action="store_true",
						help="brancher l'hydrotropisme sur le champ d'eau interpole")
	parser.add_argument("--output", type=Path, default=None,
						help="dossier de sortie personnalisé (défaut: sandbox_v2 ou sandbox_v1)")
	parser.add_argument("--tree", nargs="+", required=True, metavar="XML",
						help="fichiers xml de CPlantBox (dossier parameters/)")
	parser.add_argument("--no-street", action="store_true",
						help="scene sans reseaux ni fuites, pour isoler l'effet des tropismes")
	return parser.parse_args()


def main() -> None:
	args = parse_arguments()

	version = "v1" if args.v1 else "v2"
	build_soil = build_soil_v1 if args.v1 else build_soil_v2

	suffix = "".join(part for part, enabled in (("_fsa", args.f_sa), ("_hydro", args.hydro), ("_nostreet", args.no_street)) if enabled)
	parent_directory = args.output if args.output else SANDBOX_PARENT / f"sandbox_{version}{suffix}"
	parent_directory.mkdir(parents=True, exist_ok=True)
	
	grid = VoxelGrid(34, 64, 64, 15.0, 9.0)

	for tree in map(Path, args.tree):
		directory = parent_directory / tree.stem
		directory.mkdir(parents=True, exist_ok=True)
	 
		largest_step_cm = measure_largest_growth_step_cm(PARAMETERS_DIRECTORY / tree)
		assert PIPE_EXCLUSION_MARGIN_CM > largest_step_cm, (
			f"exlcusion margin {PIPE_EXCLUSION_MARGIN_CM} cm <= bigger dx {largest_step_cm} cm")

		for identifier in SANDBOX_ARCHETYPE_IDENTIFIERS:
			run_scene(identifier, grid, build_soil, directory, args.f_sa, args.hydro, args.no_street, tree)


if __name__ == "__main__":
	main()
