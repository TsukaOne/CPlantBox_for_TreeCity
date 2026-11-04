"""Genere le dataset v3 : une scene par configuration, en parallele et reprenable.

Un dossier par arbre : <dataset>/<fichier xml>/. Les scenes sont les memes pour tous les arbres
(sol, fosse, rue, graines : ce sont des flux independants de l'espece), seul le fichier de
parametres de CPlantBox change. --tree est obligatoire : un ou plusieurs fichiers du dossier parameters/.

Une scene deja ecrite est ignoree, donc on peut interrompre et relancer. Le plan d'experience
est note dans design.json a la premiere execution, avec le fichier xml et son empreinte, et une
relance avec d'autres reglages ou un xml modifie est refusee : un identifiant de scene n'a de
sens qu'a l'interieur d'un plan, et melanger deux versions d'un xml dans un dossier produirait
des exemples incompatibles.
"""
import argparse
import json
import os
import multiprocessing
from collections import deque
from multiprocessing.connection import wait
from pathlib import Path

from generator.build import build_scene
from generator.scene import MASTER_SEED, MONTE_CARLO_RUNS, SCENE_COUNT, draw_scenes
from generator.writer import is_complete, write_scene
from grid import VoxelGrid
from network.intrusion import measure_largest_growth_step_cm
from network.walls import PIPE_EXCLUSION_MARGIN_CM
from tree.attributes import AGE_RANGE_YEARS
from tree.species import PARAMETERS_DIRECTORY, hash_xml, identify_species, secondary_growth_for

DATASET_DIRECTORY = Path(__file__).resolve().parent / "dataset_v3"
PILOT_DIRECTORY = Path(__file__).resolve().parent / "pilot_v3"
PILOT_SCENES = 20
VTP_SUBDIRECTORY = "vtp"
GRID = VoxelGrid()


def guard_design(directory: Path, scenes: int, runs: int, tree_xml: str) -> None:
    design = {"scenes": scenes, "monte_carlo_runs": runs, "master_seed": MASTER_SEED,
              "grid": [GRID.depth_cells, GRID.row_cells, GRID.column_cells],
              "cell_cm": [GRID.cell_width_cm, GRID.cell_height_cm],
              "age_range_years": list(AGE_RANGE_YEARS),
              "tree_xml": tree_xml, "species": identify_species(tree_xml),
              "tree_xml_sha256": hash_xml(tree_xml)}
    path = directory / "design.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != design:
        raise SystemExit(f"{path} decrit un autre plan d'experience ou une autre version du xml : "
                         "choisir un autre dossier")
    path.write_text(json.dumps(design, indent=2), encoding="utf-8")


def produce_scene(task: tuple) -> str:
    configuration, directory, write_vtp, raw_vtp, write_vti = task
    label = Path(configuration.tree_xml).stem

    parameters = secondary_growth_for(configuration.tree.species)
    example = build_scene(configuration, GRID, parameters,
                          directory / VTP_SUBDIRECTORY if write_vtp else None, raw_vtp=raw_vtp)
    write_scene(directory, configuration, example, GRID, parameters, write_vti=write_vti)

    diagnostics = example.diagnostics
    return (f"{label}  scene {configuration.identifier:5d}"
            f"  {len(configuration.street.utilities):2d} reseaux"
            f"  age {configuration.tree.age_years:5.1f} ans"
            f"  segments {diagnostics['segments_mean']:7.0f}"
            f"  cible {diagnostics['mean_probability']:.5f}"
            f" (major {diagnostics['mean_probability_major']:.5f})"
            f"  intrusions {diagnostics['intrusions'] or 'aucune'}"
            f"  {diagnostics['runtime_seconds']:5.1f} s")


def run_in_process(task: tuple) -> None:
    print(produce_scene(task), flush=True)


def run_tasks(tasks: list, workers: int) -> list:
    """Une scene = un processus spawn, comme dans sandbox_v3.py : l'etat de CPlantBox partage entre deux
    scenes faussait la seconde et bloquait la troisieme. Un Pool reutilise ses processus et ne voit pas
    un worker tue (OOM) : il attendrait indefiniment. Retourne les scenes echouees."""
    context = multiprocessing.get_context("spawn")
    # "python -u" n'est pas transmis aux enfants spawn : sans cela leur sortie C++ reste bufferisee.
    os.environ["PYTHONUNBUFFERED"] = "1"
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
                              f"(code {process.exitcode}, -9 = memoire)")
                print(f"ECHEC {failed[-1]}", flush=True)
    return failed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", nargs="+", required=True, metavar="XML",
                        help="fichiers xml de CPlantBox (dossier parameters/)")
    parser.add_argument("--pilot", action="store_true", help=f"{PILOT_SCENES} scenes reparties")
    parser.add_argument("--scenes", type=int, default=SCENE_COUNT)
    parser.add_argument("--runs", type=int, default=MONTE_CARLO_RUNS)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--vtp", action="store_true", help="ecrire aussi le vtp du premier tirage")
    parser.add_argument("--vti", action="store_true", help="ecrire aussi le .vti de chaque scene (7,5 Mo, pour ParaView)")
    parser.add_argument("--vtp-raw", action="store_true",
                        help="vtp tel que CPlantBox l'ecrit, sans les rayons de croissance secondaire")
    parser.add_argument("--output", type=Path, default=None,
                        help="dossier de sortie (remplace dataset_v3/ ou pilot_v3/), "
                             "un sous-dossier par arbre y est cree")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    trees = [Path(name).name for name in arguments.tree]
    for tree_xml in trees:
        identify_species(tree_xml)
        largest_step_cm = measure_largest_growth_step_cm(PARAMETERS_DIRECTORY / tree_xml)
        assert PIPE_EXCLUSION_MARGIN_CM > largest_step_cm, (
            f"{tree_xml} : la marge d'exclusion ne couvre pas le plus grand pas de croissance du xml")

    if arguments.output is not None:
        base = arguments.output.resolve()
    elif arguments.pilot:
        base = PILOT_DIRECTORY
    else:
        base = DATASET_DIRECTORY

    tasks = []
    for tree_xml in trees:
        scenes = draw_scenes(arguments.scenes, GRID, arguments.runs, tree_xml=tree_xml)
        if arguments.pilot:
            scenes = scenes[::max(1, len(scenes) // PILOT_SCENES)][:PILOT_SCENES]
        directory = base / Path(tree_xml).stem
        directory.mkdir(parents=True, exist_ok=True)
        guard_design(directory, arguments.scenes, arguments.runs, tree_xml)
        tasks += [(configuration, directory, arguments.vtp or arguments.pilot, arguments.vtp_raw,
                   arguments.vti or arguments.pilot) for configuration in scenes]

    pending = [task for task in tasks if not is_complete(task[1], task[0].identifier)]
    print(f"{len(tasks) - len(pending)} scenes deja presentes, {len(pending)} a produire", flush=True)
    failed = run_tasks(pending, arguments.workers)
    if failed:
        raise SystemExit("scenes echouees (relancer la meme commande reprend les manquantes) :\n  "
                         + "\n  ".join(failed))


if __name__ == "__main__":
    main()
