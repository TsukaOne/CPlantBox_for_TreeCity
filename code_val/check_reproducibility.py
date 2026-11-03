"""Une scene seule, puis la meme apres une autre : meme resultat ?

Usage (depuis code_val/) : python check_reproducibility.py --tree my_Quercus_robur.xml [--target 2 --other 1 --runs 5]

Trois cas, chacun dans des processus spawn neufs, avec produce_scene de build_dataset_v3 (sortie : 3 lignes) :
  seule     : la scene cible, seule ;
  separes   : l'autre scene, puis la cible, dans deux processus differents (ce que fait le dataset) ;
  meme      : l'autre scene, puis la cible, dans le meme processus (l'ancien defaut, temoin).
Attendu : separes == seule. Si meme != seule, l'etat partage de CPlantBox est confirme ;
si meme == seule aussi, l'ancien probleme venait d'ailleurs et le spawn reste la precaution.
Les .npz sont compares cle par cle (entrees, cibles, comptes, polylignes) ; les durees ne sont pas comparees.
"""
import argparse
import multiprocessing
import shutil
import tempfile
from pathlib import Path

import numpy as np

from build_dataset_v3 import GRID, produce_scene
from generator.scene import draw_scene
from generator.writer import build_paths


def run_sequence(tasks: list) -> None:
    for task in tasks:
        produce_scene(task)  # la ligne de log n'est pas affichee : seul le verdict compte


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
    target = draw_scene(arguments.target, GRID, arguments.runs, tree_xml=tree_xml)
    other = draw_scene(arguments.other, GRID, arguments.runs, tree_xml=tree_xml)
    print(f"{tree_xml} | cible {target.identifier} (age {target.tree.age_years:.1f} ans) "
          f"| avant {other.identifier} (age {other.tree.age_years:.1f} ans) | {arguments.runs} tirages")

    root = Path(tempfile.mkdtemp(prefix="reproductibilite_"))
    directories = {name: root / name for name in ("seule", "separes", "meme")}

    def task(configuration, name):
        return (configuration, directories[name], False, False, False)

    run_in_new_process([task(target, "seule")])
    run_in_new_process([task(other, "separes")])
    run_in_new_process([task(target, "separes")])
    run_in_new_process([task(other, "meme"), task(target, "meme")])

    for name in ("separes", "meme"):
        keys = differing_keys(directories["seule"], directories[name], target.identifier)
        print(f"cible seule vs {name:8s} : " + ("IDENTIQUE" if not keys else "DIFFERENT sur " + ", ".join(keys)))

    if arguments.keep:
        print(f"dossiers gardes dans {root}")
    else:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()