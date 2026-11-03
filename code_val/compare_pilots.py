"""Compare deux dossiers de scenes (pilote avant / apres un changement), une ligne par scene.

Usage : python3 code_val/compare_pilots.py <dossier A> <dossier B>
        (ex. /tmp/pilote/my_Quercus_robur /tmp/pilote_apres/my_Quercus_robur)

Sortie : le sha du XML de chaque dossier, puis par scene : IDENTIQUE ou le nombre de cles du .npz qui
different, les segments, la probabilite moyenne et les durees (sol, croissance) de A puis de B.
Ne depend d'aucun module du depot.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def read_descriptor(directory: Path, identifier: int) -> dict:
    path = directory / f"scene_{identifier:05d}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def list_identifiers(directory: Path) -> list:
    return sorted(int(path.stem.split("_")[1]) for path in directory.glob("scene_*.npz"))


def differing_keys(first: Path, second: Path) -> list:
    with np.load(first) as a, np.load(second) as b:
        if set(a.files) != set(b.files):
            return ["jeu de cles different"]
        return [key for key in a.files if not np.array_equal(a[key], b[key])]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    arguments = parser.parse_args()

    common = sorted(set(list_identifiers(arguments.first)) & set(list_identifiers(arguments.second)))
    if not common:
        raise SystemExit("aucune scene commune")
    shas = []
    for directory in (arguments.first, arguments.second):
        versions = read_descriptor(directory, common[0]).get("versions", {})
        shas.append(str(versions.get("xml_sha256", "?"))[:16])
    print(f"xml sha : {shas[0]} -> {shas[1]}" + ("  (identique)" if shas[0] == shas[1] else "  (DIFFERENT)"))

    for identifier in common:
        name = f"scene_{identifier:05d}.npz"
        keys = differing_keys(arguments.first / name, arguments.second / name)
        diagnostics = [read_descriptor(directory, identifier).get("diagnostics", {})
                       for directory in (arguments.first, arguments.second)]
        verdict = "IDENTIQUE" if not keys else f"{len(keys)} cles differentes"
        print(f"scene {identifier}: {verdict}"
              f" | segments {diagnostics[0].get('segments_mean', 0):.0f} -> {diagnostics[1].get('segments_mean', 0):.0f}"
              f" | proba moy {diagnostics[0].get('mean_probability', 0):.5f} -> {diagnostics[1].get('mean_probability', 0):.5f}"
              f" | sol {diagnostics[0].get('soil_seconds', 0):.1f} -> {diagnostics[1].get('soil_seconds', 0):.1f} s"
              f" | croissance {diagnostics[0].get('growth_seconds', 0):.1f} -> {diagnostics[1].get('growth_seconds', 0):.1f} s")


if __name__ == "__main__":
    main()