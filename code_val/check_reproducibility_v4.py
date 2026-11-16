"""Une scene v4 seule, puis la meme apres une autre : meme resultat ?

Usage (racine du depot) : python3 code_val/check_reproducibility_v4.py --tree my_Quercus_robur.xml [--target 2 --other 1 --runs 5]

Variante v4 de check_reproducibility.py : memes trois cas (seule, separes, meme), chacun dans des
processus spawn neufs, avec build_and_write_scene de build_dataset_v4 (sortie : 3 lignes).
Attendu : separes == seule et meme == seule. TREECITY_BOX_MARGIN_CM est herite par les enfants :
lancer avec et sans. Les .npz sont compares cle par cle ; les durees ne sont pas comparees.
"""
import argparse
import multiprocessing
import shutil
import tempfile
from pathlib import Path

import numpy as np

from build_dataset_v4 import GRID, build_and_write_scene
from generator.writer import build_paths
from generator_v4.scene import draw_scene_v4


def run_sequence(tasks: list) -> None:
    for configuration, directory in tasks:
        build_and_write_scene(configuration, directory, False, False)  # log non affiche


def run_in_new_process(tasks: list) -> None:
    process = multiprocessing.get_context("spawn").Process(target=run_sequence, args=(tasks,))
    process.start()
    process.join()
    if process.exitcode != 0:
        raise SystemExit(f"processus arrete, code {process.exitcode} (-9 = memoire)")


def differing_keys(reference: Path, other: Path, identifier: int) -> list:
    with np.load(build_paths(reference, identifier)[0]) as first, \
            np.load(build_paths(other, identifier)[0]) as second:
        if set(first.files) != set(second.files):
            return ["jeu de cles different"]
        return [key for key in first.files if not np.array_equal(first[key], second[key])]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, metavar="XML")
    parser.add_argument("--target", type=int, default=2, help="identifiant de la scene testee")
    parser.add_argument("--other", type=int, default=1, help="identifiant de la scene qui passe avant")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--keep", action="store_true", help="garder les dossiers temporaires")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    tree_xml = Path(arguments.tree).name
    target = draw_scene_v4(arguments.target, GRID, arguments.runs, tree_xml=tree_xml)
    other = draw_scene_v4(arguments.other, GRID, arguments.runs, tree_xml=tree_xml)
    print(f"{tree_xml} v4 | cible {target.identifier} (age {target.tree.age_years:.1f} ans) "
          f"| avant {other.identifier} (age {other.tree.age_years:.1f} ans) | {arguments.runs} tirages")

    root = Path(tempfile.mkdtemp(prefix="reproductibilite_v4_"))
    directories = {name: root / name for name in ("seule", "separes", "meme")}

    run_in_new_process([(target, directories["seule"])])
    run_in_new_process([(other, directories["separes"])])
    run_in_new_process([(target, directories["separes"])])
    run_in_new_process([(other, directories["meme"]), (target, directories["meme"])])

    for name in ("separes", "meme"):
        keys = differing_keys(directories["seule"], directories[name], target.identifier)
        print(f"cible seule vs {name:8s} : " + ("IDENTIQUE" if not keys else "DIFFERENT sur " + ", ".join(keys)))

    if arguments.keep:
        print(f"dossiers gardes dans {root}")
    else:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()