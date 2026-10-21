"""Compare a v4 pilot with dataset v3, scene by scene.

    python3 code_val/compare_pilot_v4.py code_val/dataset_v3/my_Picea_abies code_val/pilot_v4/my_Picea_abies

Scene k of v4 has the tree XML, tree, pit, street, leaks and root seeds of v3 scene k; this is
checked first. Each pair is then compared on its root target: mass ratio v4/v3, shift of the
occupancy-weighted depth and radius, share of the mass below 50 and 100 cm, and the overlap
2 sum(a b) / (sum(a^2) + sum(b^2)). Pairs are grouped by profile, city, scene kind, pit variant,
wall kind and water module; a sign test says whether the mass moves one way more than chance.
Writes comparison_v3.csv next to the pilot.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from grid import VoxelGrid

GRID = VoxelGrid(34, 64, 64, 15.0, 9.0)
PAIRED_KEYS = ("tree", "pit_radius_cm", "pit_depth_cm", "street", "leaks", "root_seeds")
SHALLOW_DEPTHS_CM = (50.0, 100.0)
STILLBORN_SEGMENTS = 50
GROUP_KEYS = ("kind", "profile", "city", "pit", "walls", "water")
TINY = np.finfo(float).tiny


def read_scene(directory: Path, identifier: int) -> tuple:
    stem = f"scene_{identifier:05d}"
    descriptor = json.loads((directory / f"{stem}.json").read_text(encoding="utf-8"))
    with np.load(directory / f"{stem}.npz") as archive:
        return descriptor, archive["target"].astype(np.float64)


def describe_target(target: np.ndarray) -> dict:
    layer_depths_cm = GRID.measure_layer_depths_cm()
    total = max(target.sum(), TINY)
    shares = {f"below_{depth:.0f}_cm": float(target[layer_depths_cm > depth].sum() / total)
              for depth in SHALLOW_DEPTHS_CM}
    return {"mass": float(target.mean()),
            "depth_cm": float((target * layer_depths_cm[:, None, None]).sum() / total),
            "radius_cm": float((target * GRID.measure_trunk_distances_cm()[None]).sum() / total),
            **shares}


def measure_overlap(first: np.ndarray, second: np.ndarray) -> float:
    return float(2.0 * np.sum(first * second) / max(np.sum(first ** 2) + np.sum(second ** 2), TINY))


def compare_scene(identifier: int, v3_directory: Path, v4_directory: Path) -> dict:
    v3_descriptor, v3_target = read_scene(v3_directory, identifier)
    v4_descriptor, v4_target = read_scene(v4_directory, identifier)
    v3_configuration = v3_descriptor["configuration"]
    v4_configuration = v4_descriptor["configuration"]
    unpaired = [key for key in PAIRED_KEYS if v3_configuration[key] != v4_configuration[key]]
    if v3_descriptor["versions"]["xml"] != v4_descriptor["versions"]["xml"]:
        unpaired.append("xml")
    if unpaired:
        raise SystemExit(f"scene {identifier} is not paired with v3: {unpaired}")

    before, after = describe_target(v3_target), describe_target(v4_target)
    slot, water = v4_configuration["slot"], v4_configuration["soil"]["water"]
    modules = [name for name in ("drought", "runoff") if water[name]]
    return {"scene": identifier, "kind": slot["kind"], "profile": slot["profile"] or "fill",
            "city": slot["city"], "pit": slot["pit_variant"],
            "walls": v4_configuration["walls"]["kind"], "water": "+".join(modules) or "normal",
            "age_years": v4_configuration["tree"]["age_years"],
            "mass_ratio": after["mass"] / max(before["mass"], TINY),
            "depth_shift_cm": after["depth_cm"] - before["depth_cm"],
            "radius_shift_cm": after["radius_cm"] - before["radius_cm"],
            **{f"{key}_v3": value for key, value in before.items()},
            **{f"{key}_v4": value for key, value in after.items()},
            "overlap": measure_overlap(v3_target, v4_target),
            "stillborn_v4": v4_descriptor["diagnostics"]["segments_mean"] < STILLBORN_SEGMENTS,
            "intrusions_v4": len(v4_descriptor["diagnostics"]["intrusions"])}


def summarise(rows: list, label: str) -> str:
    ratios = np.array([row["mass_ratio"] for row in rows])
    low, median, high = np.percentile(ratios, [25, 50, 75])
    higher = int((ratios > 1.0).sum())
    return (f"{label:18s} n {len(rows):3d}  mass v4/v3 median {median:5.2f}"
            f" [{low:4.2f}-{high:4.2f}]  higher {higher:3d}/{len(rows):3d}"
            f" (sign test p {binomtest(higher, len(ratios)).pvalue:.3f})"
            f"  depth {np.median([row['depth_shift_cm'] for row in rows]):+6.1f} cm"
            f"  radius {np.median([row['radius_shift_cm'] for row in rows]):+6.1f} cm"
            f"  overlap {np.median([row['overlap'] for row in rows]):.2f}")


def main() -> None:
    v3_directory, v4_directory = Path(sys.argv[1]), Path(sys.argv[2])
    identifiers = sorted(int(path.stem.split("_")[1]) for path in v4_directory.glob("scene_*.json"))
    rows = [compare_scene(identifier, v3_directory, v4_directory) for identifier in identifiers]
    print(f"{len(rows)} scenes paired with v3;"
          f" stillborn in v4: {sum(row['stillborn_v4'] for row in rows)},"
          f" with intrusions: {sum(row['intrusions_v4'] > 0 for row in rows)}")
    print(summarise(rows, "all"))
    for key in GROUP_KEYS:
        print(f"by {key}")
        for value in sorted({row[key] for row in rows}):
            print("  " + summarise([row for row in rows if row[key] == value], value))
    with open(v4_directory / "comparison_v3.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
