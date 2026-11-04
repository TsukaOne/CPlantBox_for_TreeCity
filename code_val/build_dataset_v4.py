"""Generate dataset v4: the v3 scenes with the urban soil library, the walls, and a 3.0 MPa stop.

    python3 code_val/build_dataset_v4.py --tree my_Picea_abies.xml --pilot
    python3 code_val/build_dataset_v4.py --tree my_Quercus_robur.xml --scenes 2 --output code_val/tmp/v4_smoke
    python3 code_val/build_dataset_v4.py --tree my_Picea_abies.xml --pilot --identifiers 28 37 90

One folder per tree: <dataset>/<xml file>/. --tree is required: one or more files of parameters/.
The tree only changes the tree attributes, so scene k is the same street and soil for every tree.

One scene per identifier, in parallel and resumable: a scene already written is skipped. The plan
is written to design.json on the first run, with the XML, its fingerprint and the growth options,
and a rerun with other settings, a modified XML or other options is refused. The pilot takes
identifiers 1 to 128, eight full blocks of the design, which are also the first scenes of the
dataset; scene k is paired with v3 scene k of the same tree. --identifiers builds only some scenes
of the design, which a later full run completes. The .vti (85 % of a scene on disk) is written
only by the pilot or with --vti.
"""
import argparse
import json
import multiprocessing
import os
from collections import deque
from dataclasses import asdict
from multiprocessing.connection import wait
from pathlib import Path

from generator.scene import MASTER_SEED, MONTE_CARLO_RUNS, SCENE_COUNT
from generator.writer import is_complete
from generator_v4.build import GROWTH_OPTIONS, build_scene_v4
from generator_v4.design import BLOCK_SIZE
from generator_v4.scene import draw_scene_v4
from generator_v4.writer import write_scene_v4
from grid import VoxelGrid
from network.intrusion import measure_largest_growth_step_cm
from network.walls import BOX_MARGIN_CM, PIPE_EXCLUSION_MARGIN_CM
from tree.attributes import AGE_RANGE_YEARS
from tree.species import PARAMETERS_DIRECTORY, hash_xml, identify_species, secondary_growth_for

DATASET_DIRECTORY = Path(__file__).resolve().parent / "dataset_v4"
PILOT_DIRECTORY = Path(__file__).resolve().parent / "pilot_v4"
PILOT_BLOCKS = 8
VTP_SUBDIRECTORY = "vtp"
GRID = VoxelGrid()


def guard_design(directory: Path, scenes: int, runs: int, tree_xml: str) -> None:
    design = {"scenes": scenes, "monte_carlo_runs": runs, "master_seed": MASTER_SEED,
              "grid": [GRID.depth_cells, GRID.row_cells, GRID.column_cells],
              "cell_cm": [GRID.cell_width_cm, GRID.cell_height_cm],
              "age_range_years": list(AGE_RANGE_YEARS),
              "box_margin_cm": BOX_MARGIN_CM,
              "tree_xml": tree_xml, "species": identify_species(tree_xml),
              "tree_xml_sha256": hash_xml(tree_xml), "growth_options": asdict(GROWTH_OPTIONS)}
    path = directory / "design.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != design:
        raise SystemExit(f"{path} describes another design, another version of the XML or other "
                         "growth options: choose another directory")
    path.write_text(json.dumps(design, indent=2), encoding="utf-8")


def build_and_write_scene(configuration, directory: Path, write_vtp: bool, write_vti: bool) -> str:
    parameters = secondary_growth_for(configuration.tree.species)
    example = build_scene_v4(configuration, GRID, parameters,
                             directory / VTP_SUBDIRECTORY if write_vtp else None)
    write_scene_v4(directory, configuration, example, GRID, parameters, write_vti)

    slot, diagnostics = configuration.slot, example.diagnostics
    return (f"{slot.kind:9s} {slot.profile or '-':3s}"
            f" {slot.city:8s} pit {slot.pit_variant:9s} walls {configuration.walls.kind:12s}"
            f"  age {configuration.tree.age_years:5.1f}  segments {diagnostics['segments_mean']:6.0f}"
            f"  target {diagnostics['mean_probability']:.5f}"
            f"  intrusions {diagnostics['intrusions'] or 'none'}"
            f"  {diagnostics['runtime_seconds']:5.1f} s")


def run_in_process(task: tuple) -> None:
    configuration, directory, write_vtp, write_vti = task
    heading = f"{Path(configuration.tree_xml).stem}  scene {configuration.identifier:5d}"
    line = build_and_write_scene(configuration, directory, write_vtp, write_vti)
    print(f"{heading}  {line}", flush=True)


def run_tasks(tasks: list, workers: int) -> list:
    """One scene = one spawn process: a Pool reuses its processes and does not see a worker
    killed for lack of memory. A scene that raises leaves its traceback on stderr and an exit
    code 1. Returns the failed scenes."""
    context = multiprocessing.get_context("spawn")
    os.environ["PYTHONUNBUFFERED"] = "1"  # not passed to spawn children by "python -u"
    waiting, running, failed = deque(tasks), {}, []
    while waiting or running:
        while waiting and len(running) < workers:
            task = waiting.popleft()
            process = context.Process(target=run_in_process, args=(task,))
            process.start()
            running[process] = task
        wait([process.sentinel for process in running])
        for process in [p for p in running if p.exitcode is not None]:
            process.join()
            configuration = running.pop(process)[0]
            if process.exitcode != 0:
                failed.append(f"{Path(configuration.tree_xml).stem} scene {configuration.identifier} "
                              f"(code {process.exitcode}, -9 = out of memory)")
                print(f"FAILED, left unwritten: {failed[-1]}", flush=True)
    return failed


def select_identifiers(arguments: argparse.Namespace, scenes: int) -> list:
    identifiers = arguments.identifiers or list(range(1, scenes + 1))
    outside = [identifier for identifier in identifiers if not 1 <= identifier <= scenes]
    if outside:
        raise SystemExit(f"scenes {outside} are outside the design (1 to {scenes})")
    return identifiers


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", nargs="+", required=True, metavar="XML",
                        help="CPlantBox XML files (parameters/ folder)")
    parser.add_argument("--pilot", action="store_true", help=f"the first {PILOT_BLOCKS} blocks")
    parser.add_argument("--scenes", type=int, default=SCENE_COUNT)
    parser.add_argument("--identifiers", nargs="+", type=int, metavar="K",
                        help="only these scenes of the design, e.g. a few pilot scenes")
    parser.add_argument("--runs", type=int, default=MONTE_CARLO_RUNS)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--vtp", action="store_true", help="also write the vtp of the first run")
    parser.add_argument("--vti", action="store_true",
                        help="also write the ParaView .vti of the soil and occupancy fields")
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
    identifiers = select_identifiers(arguments, scenes)

    tasks = []
    for tree_xml in trees:
        directory = base / Path(tree_xml).stem
        directory.mkdir(parents=True, exist_ok=True)
        guard_design(directory, scenes, arguments.runs, tree_xml)
        tasks += [(draw_scene_v4(identifier, GRID, arguments.runs, tree_xml=tree_xml), directory,
                   arguments.vtp or arguments.pilot, arguments.vti or arguments.pilot)
                  for identifier in identifiers]

    pending = [task for task in tasks if not is_complete(task[1], task[0].identifier)]
    print(f"{len(tasks) - len(pending)} scenes already written, {len(pending)} to produce", flush=True)
    failed = run_tasks(pending, arguments.workers)
    if failed:
        raise SystemExit("scenes failed and were left unwritten (rerun the same command to retry them):\n  " + "\n  ".join(failed))


if __name__ == "__main__":
    main()
