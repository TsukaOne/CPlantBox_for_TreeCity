"""Les deux mesures qui decident des phases B et C, sur un dossier au format hybride.

Phase B : Dice doux du prior seul, geometrique puis prior_v2 pour chaque B, apres la calibration
k = taux de base / moyenne du prior. Le document situe le prior geometrique a 0,028, et une
prediction parfaitement calibree (p = t) a 0,233 : ce second chiffre controle que ce Dice est bien
celui de l'entrainement.
Phase C : part de la cible dans les voxels qu'un masque dur interdirait.

Sur un dossier de scenes, un rapport readiness.json y est ecrit. Sur dataset_v3/, qui contient un
sous-dossier par arbre, un rapport est ecrit dans chaque sous-dossier : le prior et le taux de base
different d'une espece a l'autre, une calibration commune de k les melangerait.
"""
import argparse
import json
import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from hybrid.channels import read_channel
from hybrid.masks import (GROWTH_BLOCK_SCALE, PIPE_BLOCK_FRACTION, build_forbidden_zones,
                          measure_forbidden_mass)
from hybrid.prior import (LEAK_PRIOR_BOOSTS, build_prior_v2, calibrate_prior, compute_soft_dice,
                          measure_dice_terms)

DEFAULT_DATASET = Path(__file__).resolve().parent / "dataset_v2_hybrid"
REPORT_NAME = "readiness.json"
HIT_COUNTS = {"radius": "hit_count", "centreline": "hit_count_centreline"}


def build_priors(archive) -> dict:
    inputs, names = archive["inputs"], tuple(archive["channel_names"])
    prior, pipe_fraction, leak_plume = (read_channel(inputs, names, name)
                                        for name in ("prior", "pipe_fraction", "leak_plume"))
    growth_scale = read_channel(inputs, names, "bengough") * read_channel(inputs, names, "water_scale")
    priors = {"perfect_calibration": archive["target"].astype(np.float32), "geometric": prior}
    for boost in LEAK_PRIOR_BOOSTS:
        priors[f"v2_boost_{boost:g}"] = build_prior_v2(prior, growth_scale, pipe_fraction,
                                                       leak_plume, boost)
    return priors, build_forbidden_zones(pipe_fraction, growth_scale)


def measure_scene(path: Path) -> dict:
    with np.load(path) as archive:
        priors, zones = build_priors(archive)
        target = archive["target"].astype(np.float32)
        return {"dice_terms": {name: measure_dice_terms(prior, target) for name, prior in priors.items()},
                "prior_peak": {name: float(prior.max()) for name, prior in priors.items()},
                "mass": {label: {"total": int(archive[key].sum(dtype=np.int64)),
                                 **measure_forbidden_mass(archive[key], zones)}
                         for label, key in HIT_COUNTS.items()}}


def summarise_priors(scenes: list) -> dict:
    report = {}
    for name in scenes[0]["dice_terms"]:
        terms = np.array([scene["dice_terms"][name] for scene in scenes])
        scale = calibrate_prior(terms)
        peak = max(scene["prior_peak"][name] for scene in scenes)
        report[name] = {"k": scale, "dice_calibrated": compute_soft_dice(terms, scale),
                        "dice_raw": compute_soft_dice(terms, 1.0), "saturates": scale * peak > 1.0}
    return report


def summarise_masks(scenes: list) -> dict:
    report = {}
    for label in HIT_COUNTS:
        total = sum(scene["mass"][label]["total"] for scene in scenes)
        zones = [name for name in scenes[0]["mass"][label] if name != "total"]
        report[label] = {zone: {"share": sum(scene["mass"][label][zone] for scene in scenes) / total,
                                "scenes_touched": sum(scene["mass"][label][zone] > 0 for scene in scenes)}
                         for zone in zones}
    return report


def list_scene_groups(dataset: Path) -> list:
    """Le dossier lui-meme s'il porte des scenes, sinon un groupe par sous-dossier d'arbre."""
    if any(dataset.glob("scene_*.npz")):
        return [dataset]
    return sorted(folder for folder in dataset.iterdir()
                  if folder.is_dir() and any(folder.glob("scene_*.npz")))


def build_report(directory: Path, pool) -> dict:
    scenes = pool.map(measure_scene, sorted(directory.glob("scene_*.npz")), chunksize=8)
    return {"dataset": directory.name, "scenes": len(scenes),
            "thresholds": {"pipe_block_fraction": PIPE_BLOCK_FRACTION,
                           "growth_block_scale": GROWTH_BLOCK_SCALE},
            "priors": summarise_priors(scenes), "forbidden_mass": summarise_masks(scenes)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    arguments = parser.parse_args()

    groups = list_scene_groups(arguments.dataset)
    if not groups:
        raise SystemExit(f"aucun scene_*.npz dans {arguments.dataset} ni dans ses sous-dossiers")

    with Pool(arguments.workers) as pool:
        for directory in groups:
            report = build_report(directory, pool)
            (directory / REPORT_NAME).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
