"""Bords de grille : faces franchies par les noeuds de racine, et accumulation sur le bord et au fond.

Usage (depuis la racine du depot) : python3 code_val/check_grid_edges.py <dossier ou .npz> [...] [--detail]
Par defaut : 3 lignes (total, profil de bord, profil de fond). --detail : une ligne par scene en plus.

Lit polyline_points (noeuds du premier tirage, pas les echantillons du tampon : les segments font
quelques cm, la face franchie et l'ordre de grandeur sont les memes) et target (probabilite).
Une meme racine peut sortir par plusieurs faces (coin) : les faces ne s'additionnent pas.

ratio bord = moyenne de la cible sur la rangee de cellules la plus externe (tous les niveaux)
             / moyenne sur la rangee suivante ; 1 = pas d'accumulation, > 1 = les racines butent.
ratio fond = moyenne de la cible de la derniere couche / celle de l'avant-derniere.
profil     = moyenne de la cible par rang depuis la paroi (rang 0 = paroi, couche 0 = fond),
             divisee par celle du rang PROFILE_WIDTH ; il montre sur quelle epaisseur ca s'accumule.
"""
import argparse
from pathlib import Path

import numpy as np

from build_dataset_v3 import GRID
from grid import FLOOR_TOLERANCE_CM

FACES = ("dessus", "fond", "cote_x", "cote_y")
PROFILE_WIDTH = 6


def split_by_face(points: np.ndarray) -> dict:
    depth_cm = -points[:, 2]
    return {"dessus": depth_cm < 0,
            "fond": depth_cm >= GRID.depth_cm + FLOOR_TOLERANCE_CM,
            "cote_x": np.abs(points[:, 0]) >= GRID.half_width_cm,
            "cote_y": np.abs(points[:, 1]) >= GRID.half_length_cm}


def build_ring_index(rows: int, columns: int) -> np.ndarray:
    """Rang de chaque colonne de cellules depuis la paroi laterale (0 = la plus externe)."""
    row_index, column_index = np.meshgrid(np.arange(rows), np.arange(columns), indexing="ij")
    return np.minimum.reduce([row_index, column_index, rows - 1 - row_index, columns - 1 - column_index])


def safe_ratio(numerator: np.ndarray, denominator: float) -> np.ndarray:
    return numerator / denominator if denominator > 0 else np.full(np.shape(numerator), np.nan)


def measure_profiles(target: np.ndarray) -> tuple:
    """(profil bord, profil fond), chacun de longueur PROFILE_WIDTH, normalise par le rang PROFILE_WIDTH."""
    ring = build_ring_index(*target.shape[1:])
    edge = np.array([target[:, ring == k].mean() for k in range(PROFILE_WIDTH + 1)])
    floor = np.array([target[-1 - k].mean() for k in range(PROFILE_WIDTH + 1)])
    return (safe_ratio(edge[:PROFILE_WIDTH], edge[PROFILE_WIDTH]),
            safe_ratio(floor[:PROFILE_WIDTH], floor[PROFILE_WIDTH]))


def divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else float("nan")


def average(values) -> np.ndarray:
    """Moyenne en ignorant les nan ; nan seulement si tout est nan."""
    array = np.asarray(values, dtype=float)
    finite = np.isfinite(array)
    count = finite.sum(axis=0)
    return np.where(count > 0, np.where(finite, array, 0.0).sum(axis=0) / np.maximum(count, 1), np.nan)


def list_archives(arguments: list) -> list:
    paths = []
    for argument in arguments:
        path = Path(argument)
        paths += sorted(path.rglob("scene_*.npz")) if path.is_dir() else [path]
    return paths


def format_profile(values: np.ndarray) -> str:
    return " ".join(f"{value:5.2f}" for value in values)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("paths", nargs="+", help="dossiers ou .npz")
    parser.add_argument("--detail", action="store_true", help="une ligne par scene")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    paths = list_archives(arguments.paths)
    if not paths:
        raise SystemExit("aucun .npz trouve")
    totals = dict.fromkeys(FACES, 0)
    nodes_total = outside_total = 0
    reach_max = 0.0
    edge_profiles, floor_profiles = [], []
    for path in paths:
        with np.load(path) as data:
            points = data["polyline_points"].astype(np.float64)
            target = data["target"].astype(np.float64)
        *_, inside = GRID.locate_points(points)
        faces = split_by_face(points)
        counts = {face: int(mask.sum()) for face, mask in faces.items()}
        outside = int((~inside).sum())
        reach = float(np.abs(points[:, :2]).max())
        edge_profile, floor_profile = measure_profiles(target)
        edge_profiles.append(edge_profile)
        floor_profiles.append(floor_profile)
        if arguments.detail:
            print(f"{path.parent.parent.name}/{path.parent.name}/{path.name}  noeuds {len(points):6d}"
                  f"  hors grille {outside:5d}  portee {reach:6.1f} cm"
                  f"  bord rang0/rang1 {divide(edge_profile[0], edge_profile[1]):5.2f}"
                  f"  fond couche0/couche1 {divide(floor_profile[0], floor_profile[1]):5.2f}")
        nodes_total += len(points)
        outside_total += outside
        reach_max = max(reach_max, reach)
        for face in FACES:
            totals[face] += counts[face]
    print(f"{len(paths)} scenes | noeuds {nodes_total} | hors grille {outside_total} ("
          + ", ".join(f"{face} {totals[face]}" for face in FACES)
          + f") | portee laterale max {reach_max:.1f} cm (demi-largeur {GRID.half_width_cm:.0f})")
    print(f"profil bord  (rang 0 = paroi, / rang {PROFILE_WIDTH}) : {format_profile(average(edge_profiles))}")
    print(f"profil fond  (couche 0 = fond, / couche {PROFILE_WIDTH}) : {format_profile(average(floor_profiles))}")


if __name__ == "__main__":
    main()