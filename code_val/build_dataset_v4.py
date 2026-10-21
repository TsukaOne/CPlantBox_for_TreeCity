"""Generate dataset v4: the v3 scenes with the urban soil library, the walls, and a 3.0 MPa stop.

    python3 code_val/build_dataset_v4.py --tree my_Picea_abies.xml --pilot
    python3 code_val/build_dataset_v4.py --tree my_Quercus_robur.xml --scenes 2 --output code_val/tmp/v4_smoke

One folder per tree: <dataset>/<xml file>/. --tree is required: one or more files of parameters/.
The tree only changes the tree attributes, so scene k is the same street and soil for every tree.

One scene per identifier, in parallel and resumable: a scene already written is skipped. The plan
is written to design.json on the first run, with the XML and its fingerprint, and a rerun with other
settings or a modified XML is refused. The pilot takes identifiers 1 to 128, eight full blocks of
the design, which are also the first scenes of the dataset; scene k is paired with v3 scene k of
the same tree.
"""
import argparse
import json
import os
from multiprocessing import Pool
from pathlib import Path

from generator.scene import MASTER_SEED, MONTE_CARLO_RUNS, SCENE_COUNT
from generator.writer import is_complete
from generator_v4.build import build_scene_v4
from generator_v4.design import BLOCK_SIZE
from generator_v4.scene import draw_scene_v4
from generator_v4.writer import write_scene_v4
from grid import VoxelGrid
from network.intrusion import measure_largest_growth_step_cm
from network.walls import PIPE_EXCLUSION_MARGIN_CM
from tree.species import PARAMETERS_DIRECTORY, hash_xml, identify_species, secondary_growth_for

DATASET_DIRECTORY = Path(__file__).resolve().parent / "dataset_v4"
PILOT_DIRECTORY = Path(__file__).resolve().parent / "pilot_v4"
PILOT_BLOCKS = 8
VTP_SUBDIRECTORY = "vtp"
GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)


def guard_design(directory: Path, scenes: int, runs: int, tree_xml: str) -> None:
    design = {"scenes": scenes, "monte_carlo_runs": runs, "master_seed": MASTER_SEED,
              "grid": [GRID.depth_cells, GRID.row_cells, GRID.column_cells],
              "tree_xml": tree_xml, "species": identify_species(tree_xml),
              "tree_xml_sha256": hash_xml(tree_xml)}
    path = directory / "design.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != design:
        raise SystemExit(f"{path} describes another design or another version of the XML: "
                         "choose another directory")
    path.write_text(json.dumps(design, indent=2), encoding="utf-8")


def produce_scene(task: tuple) -> str:
    configuration, directory, write_vtp = task
    label = Path(configuration.tree_xml).stem
    if is_complete(directory, configuration.identifier):
        return f"{label}  scene {configuration.identifier:5d} already written, skipped"

    parameters = secondary_growth_for(configuration.tree.species)
    example = build_scene_v4(configuration, GRID, parameters,
                             directory / VTP_SUBDIRECTORY if write_vtp else None)
    write_scene_v4(directory, configuration, example, GRID, parameters)

    slot, diagnostics = configuration.slot, example.diagnostics
    return (f"{label}  scene {configuration.identifier:5d}  {slot.kind:9s} {slot.profile or '-':3s}"
            f" {slot.city:8s} pit {slot.pit_variant:9s} walls {configuration.walls.kind:12s}"
            f"  age {configuration.tree.age_years:5.1f}  segments {diagnostics['segments_mean']:6.0f}"
            f"  target {diagnostics['mean_probability']:.5f}"
            f"  intrusions {diagnostics['intrusions'] or 'none'}"
            f"  {diagnostics['runtime_seconds']:5.1f} s")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", nargs="+", required=True, metavar="XML",
                        help="CPlantBox XML files (parameters/ folder)")
    parser.add_argument("--pilot", action="store_true", help=f"the first {PILOT_BLOCKS} blocks")
    parser.add_argument("--scenes", type=int, default=SCENE_COUNT)
    parser.add_argument("--runs", type=int, default=MONTE_CARLO_RUNS)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--vtp", action="store_true", help="also write the vtp of the first run")
    parser.add_argument("--output", type=Path, default=None,
                        help="output directory (replaces dataset_v4/ or pilot_v4/), "
                             "one subfolder per tree is created in it")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    trees = [Path(name).name for name in arguments.tree]
    for tree_xml in trees:
        identify_species(tree_xml)
        largest_step_cm = measure_largest_growth_step_cm(PARAMETERS_DIRECTORY / tree_xml)
        assert PIPE_EXCLUSION_MARGIN_CM > largest_step_cm, (
            f"{tree_xml}: the exclusion margin does not cover the largest growth step of the XML")

    scenes = PILOT_BLOCKS * BLOCK_SIZE if arguments.pilot else arguments.scenes
    default_directory = PILOT_DIRECTORY if arguments.pilot else DATASET_DIRECTORY
    base = (arguments.output or default_directory).resolve()

    tasks = []
    for tree_xml in trees:
        directory = base / Path(tree_xml).stem
        directory.mkdir(parents=True, exist_ok=True)
        guard_design(directory, scenes, arguments.runs, tree_xml)
        tasks += [(draw_scene_v4(identifier, GRID, arguments.runs, tree_xml=tree_xml), directory,
                   arguments.vtp or arguments.pilot) for identifier in range(1, scenes + 1)]

    with Pool(arguments.workers) as pool:
        for message in pool.imap_unordered(produce_scene, tasks):
            print(message, flush=True)


if __name__ == "__main__":
    main()
