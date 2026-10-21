"""Sandbox on top of the v3 generator: grow one scene at a time and measure the roots.

Same scene model as the dataset (network/ streets, v3 environment, secondary growth, voxelisation
by diameter class, 19 input channels), but built by hand so that one thing varies at a time:
one soil archetype (a single patch), one street seeded independently of the soil and of the
tree, the age and the seeds of your choice. sandbox_v2.py stays the reference for the axis-aligned
prototype of obstacles/.

Per XML file given with --tree, per archetype, it writes in
sandbox_v3[_nofsa][_nohydro][_nostreet]/<xml>/ :
  <stem>_seedNN.vtp     the first trees, for ParaView
  <stem>.vti            the fields of the scene and the occupancy probability
  <stem>_roots.csv      one row per structural root of at least 100 cm, for every tree
  <stem>_profile.csv    structural root length per subtype, depth band and radius band
  npz/scene_NNNNN.*     with --npz: the files of the dataset (.npz, .json, site_request; the .vti is the one above)
"""
import argparse
import dataclasses
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import root_metrics
from generator.build import GrowthOptions, build_scene
from generator.scene import (NOISE, PIT, SOIL, STREET, TREE_PIT_RADIUS_RANGE_CM,
                             SceneConfiguration, build_generator)
from generator.writer import write_scene
from grid import VoxelGrid
from network.intrusion import measure_largest_growth_step_cm
from network.leaks import build_scene_leaks
from network.street import DENSITY_CLASSES, draw_street_scene
from network.walls import PIPE_EXCLUSION_MARGIN_CM
from paraview import write_voxel_grids
from soil.archetypes import PIT_SUBSTRATE_ARCHETYPE, find_archetype
from soil.mosaic import single_patch_mosaic
from soil.pit import TREE_PIT_DEPTH_RANGE_CM
from soil.profile import draw_soil_profile
from tree.attributes import (DBH_AGE_EXPONENT, DBH_COEFFICIENT, TreeAttributes,
                             estimate_crown_depth_m, estimate_height_m)
from tree.species import PARAMETERS_DIRECTORY, identify_species, secondary_growth_for

SANDBOX_PARENT = Path(__file__).resolve().parent
GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
SANDBOX_AGE_YEARS = 120.0
SANDBOX_SEED = 7
SANDBOX_RUNS = 50
SEED_STRIDE = 100
VTP_RUNS_KEPT = 3
DEFAULT_ARCHETYPES = (1,)
DEFAULT_STREET_CLASS = "dense"
STREET_SEED_ATTEMPTS = 200
NPZ_SUBDIRECTORY = "npz"
CLASS_NAMES = tuple(name for name, _, _ in DENSITY_CLASSES)


def build_tree_attributes(species: str, age_years: float) -> TreeAttributes:
    """The nominal allometries, without the random spread of the dataset: one age, one tree."""
    dbh_cm = float(DBH_COEFFICIENT * age_years ** DBH_AGE_EXPONENT)
    height_m = estimate_height_m(dbh_cm)
    return TreeAttributes(species, age_years, dbh_cm, height_m, estimate_crown_depth_m(height_m))


def draw_street(street_class: str, pit_radius_cm: float, pit_depth_cm: float, seed: int) -> tuple:
    """The first street, from this seed on, whose density class is the one asked for.
    Returns the street, the generator that drew it (the leaks come next) and the seed used."""
    for attempt in range(STREET_SEED_ATTEMPTS):
        rng = build_generator(seed + attempt, 0, STREET)
        street = draw_street_scene(pit_radius_cm, pit_depth_cm, GRID, rng)
        if street.density_class == street_class:
            return street, rng, seed + attempt
    raise SystemExit(f"no street of class '{street_class}' in {STREET_SEED_ATTEMPTS} seeds from {seed}")


def build_sandbox_configuration(archetype_identifier: int, tree_xml: str, age_years: float, runs: int,
                                with_street: bool, street_class: str, seed: int) -> tuple:
    """The pit and the street are seeded without the archetype and without the tree: every soil and
    every XML meets the same pit and the same pipes, so a difference can only come from them."""
    pit_rng = build_generator(seed, 0, PIT)
    pit_radius_cm = float(pit_rng.uniform(*TREE_PIT_RADIUS_RANGE_CM))
    pit_depth_cm = float(pit_rng.uniform(*TREE_PIT_DEPTH_RANGE_CM))
    pit_soil = draw_soil_profile(PIT_SUBSTRATE_ARCHETYPE, pit_rng)

    street, street_rng, street_seed = draw_street(street_class, pit_radius_cm, pit_depth_cm, seed)
    if not with_street:
        street = dataclasses.replace(street, utilities=())
    leaks = build_scene_leaks(street.utilities, street_rng)

    soil_rng = build_generator(seed, archetype_identifier, SOIL)
    profile = draw_soil_profile(find_archetype(archetype_identifier), soil_rng)
    configuration = SceneConfiguration(
        identifier=archetype_identifier,
        tree=build_tree_attributes(identify_species(tree_xml), age_years),
        pit_radius_cm=pit_radius_cm,
        pit_depth_cm=pit_depth_cm,
        pit_soil=pit_soil,
        soil=single_patch_mosaic(profile),
        street=street,
        leaks=leaks,
        soil_noise_seed=int(build_generator(seed, archetype_identifier, NOISE).integers(1, 2 ** 31)),
        root_seeds=tuple(seed + run * SEED_STRIDE for run in range(runs)),
        tree_xml=tree_xml,
    )
    return configuration, street_seed


def rename_vtp(directory: Path, identifier: int, stem: str, kept: int) -> None:
    """build_scene names the first trees scene_NNNNN_run_RR.vtp: give them the name of the sandbox."""
    for run in range(1, kept + 1):
        source = directory / f"scene_{identifier:05d}_run_{run:02d}.vtp"
        if source.exists():
            source.replace(directory / f"{stem}_seed{run - 1:02d}.vtp")


def run_scene(archetype_identifier: int, tree_xml: str, directory: Path, options: GrowthOptions,
              with_street: bool, street_class: str, runs: int, age_years: float, seed: int,
              write_npz: bool, raw_vtp: bool) -> None:
    configuration, street_seed = build_sandbox_configuration(
        archetype_identifier, tree_xml, age_years, runs, with_street, street_class, seed)
    parameters = secondary_growth_for(configuration.tree.species)
    archetype = find_archetype(archetype_identifier)
    stem = f"{archetype.name}_{datetime.now():%Y%m%d_%H-%M}"

    per_tree_records, per_tree_lengths = [], []

    def observe(run_index, polydata, radii, segments) -> None:
        per_tree_records.append(root_metrics.measure_root_shapes(polydata))
        per_tree_lengths.append(root_metrics.measure_length_distribution(polydata))

    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    example = build_scene(configuration, GRID, parameters, vtp_directory=directory, options=options,
                          vtp_runs=VTP_RUNS_KEPT, observer=observe, raw_vtp=raw_vtp)
    elapsed = time.perf_counter() - started
    rename_vtp(directory, archetype_identifier, stem, VTP_RUNS_KEPT)

    write_voxel_grids(directory / f"{stem}.vti", example.fields, GRID)
    root_metrics.save_root_records(directory / f"{stem}_roots.csv", per_tree_records)
    root_metrics.save_length_distribution(directory / f"{stem}_profile.csv", per_tree_lengths)
    if write_npz:
        write_scene(directory / NPZ_SUBDIRECTORY, configuration, example, GRID, parameters, write_vti=False)

    fields, diagnostics = example.fields, example.diagnostics
    mean_radius_cm, mean_depth_cm = root_metrics.measure_occupancy_shape(fields["occupancy"], GRID)
    street_text = (f"rue {configuration.street.density_class} (graine {street_seed}, "
                   f"{len(configuration.street.utilities)} reseaux)" if with_street else "sans rue")
    print(f"{archetype.name:<18s} {Path(tree_xml).stem} | {street_text}"
          f" | f_sa {'oui' if options.use_angle_scale else 'non'}"
          f" hydro {'oui' if options.use_hydrotropism else 'non'} | croissance secondaire appliquee")
    print(f"{'':<18s} bengough {fields['bengough'].mean():.3f} eau {fields['eau'].mean():.3f}"
          f" -> f_se {fields['f_se'].mean():.3f}")
    print(f"{'':<18s} segments {diagnostics['segments_mean']:7.0f} +/- {diagnostics['segments_std']:5.0f}"
          f" profondeur {diagnostics['max_depth_cm_mean']:6.1f} +/- {diagnostics['max_depth_cm_std']:5.1f} cm"
          f" support {diagnostics['support_voxel_fraction']:.4f} masse {diagnostics['mean_probability']:.5f}"
          f" (major {diagnostics['mean_probability_major']:.5f})"
          f" distance_moy {mean_radius_cm:5.1f} cm profondeur_moy {mean_depth_cm:5.1f} cm"
          f" duree {elapsed:6.1f} s", flush=True)
    leaking = ",".join(leak.name for leak in configuration.leaks) or "aucune"
    print(f"{'':<18s} fuites {leaking} intrusions {diagnostics['intrusions'] or 'aucune'}"
          f" echantillons hors grille {diagnostics['samples_outside_grid']}", flush=True)
    root_metrics.print_shape_summary(per_tree_records)
    root_metrics.print_depth_summary(per_tree_lengths)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--tree", nargs="+", required=True, metavar="XML",
                        help="CPlantBox xml files (parameters/ folder)")
    parser.add_argument("--archetype", type=int, nargs="+", default=list(DEFAULT_ARCHETYPES),
                        help="soil archetype identifiers (1 = loose_uniform ... 10 = sand_over_clay)")
    parser.add_argument("--no-street", action="store_true", help="no network and no leak in the scene")
    parser.add_argument("--street-class", choices=CLASS_NAMES, default=DEFAULT_STREET_CLASS,
                        help="density class of the street (ignored with --no-street)")
    parser.add_argument("--no-f-sa", action="store_true", help="do not wire f_sa (the dataset does)")
    parser.add_argument("--no-hydro", action="store_true", help="do not wire the hydrotropism (the dataset does)")
    parser.add_argument("--vtp-raw", action="store_true",
                        help="leave the .vtp as CPlantBox wrote it, without the secondary-growth radii")
    parser.add_argument("--npz", action="store_true", help="also write the files of the dataset (npz/ folder)")
    parser.add_argument("--runs", type=int, default=SANDBOX_RUNS, help="trees per scene")
    parser.add_argument("--age", type=float, default=SANDBOX_AGE_YEARS, help="tree age [years]")
    parser.add_argument("--seed", type=int, default=SANDBOX_SEED)
    parser.add_argument("--output", type=Path, default=None, help="output folder")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    options = GrowthOptions(use_angle_scale=not arguments.no_f_sa, use_hydrotropism=not arguments.no_hydro)
    trees = [Path(name) for name in arguments.tree]

    suffix = "".join(part for part, enabled in (("_nofsa", arguments.no_f_sa),
                                                ("_nohydro", arguments.no_hydro),
                                                ("_nostreet", arguments.no_street)) if enabled)
    parent_directory = arguments.output or SANDBOX_PARENT / f"sandbox_v3{suffix}"

    for tree in trees:
        identify_species(tree)
        largest_step_cm = measure_largest_growth_step_cm(PARAMETERS_DIRECTORY / tree)
        assert PIPE_EXCLUSION_MARGIN_CM > largest_step_cm, (
            f"{tree}: exclusion margin {PIPE_EXCLUSION_MARGIN_CM} cm <= largest dx {largest_step_cm} cm")
        for identifier in arguments.archetype:
            run_scene(identifier, tree.name, parent_directory / tree.stem, options,
                      not arguments.no_street, arguments.street_class, arguments.runs,
                      arguments.age, arguments.seed, arguments.npz, arguments.vtp_raw)


if __name__ == "__main__":
    main()
