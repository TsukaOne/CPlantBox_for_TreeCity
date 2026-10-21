"""Measures on the roots of simulated trees, and their summary over many trees.

Two things are measured on each tree, from its polylines (one polyline = one root):

- the shape of every structural root of at least 100 cm: tortuosity, share of vertical segments,
  maximal depth, and whether the measured window touches the floor of the grid;
- the structural root length per subtype, depth band and radius band.

A single tree says little: the roots of one tree share their soil, their pipes and their random
sequence. The uncertainty of a median is therefore estimated by resampling the trees, not the roots.
"""
import csv
from pathlib import Path

import numpy as np

from dataset.occupancy import STRUCTURAL_SUBTYPES
from generator.polylines import ROOT_ORGAN_TYPE
from generator.voxelise import build_polysegments, select_structural
from grid import VoxelGrid

# The tortuosity is measured between 40 and 100 cm along the root: the first centimetres of a
# root born almost horizontal bend towards the vertical, which says nothing about its sinuosity.
WINDOW_START_CM = 40.0
WINDOW_END_CM = 100.0
# A window deeper than this touches the floor of the grid (306 cm), where the roots slide sideways.
FLOOR_DEPTH_CM = 296.0
VERTICAL_UZ = -0.8

DEPTH_BANDS_CM = (0, 30, 60, 120, 200, 306)
RADIUS_BANDS_CM = (0, 100, 250, 700)
DEEP_BAND_START = 3        # index of the 120-200 cm band
FAR_RADIUS_BAND = 2        # index of the band beyond 250 cm from the trunk
BOOTSTRAP_DRAWS = 2000
SUMMARY_INDENT = " " * 18

ROOT_HEADER = ["arbre", "sous_type", "longueur_cm", "tortuosite_40_100cm", "part_verticale",
               "profondeur_cm", "touche_fond"]
LENGTH_HEADER = ["arbre", "sous_type", "bande_profondeur", "bande_rayon", "longueur_cm"]


def measure_root_shapes(polydata) -> list:
    """One row per root of at least 100 cm:
    (subtype, length, tortuosity 40-100 cm, vertical share, maximal depth, touches the floor)."""
    offsets = polydata.offsets
    starts = offsets - np.diff(offsets, prepend=0)
    records = []
    for line, (first, last) in enumerate(zip(starts, offsets)):
        if polydata.cell_arrays["organType"][line] != ROOT_ORGAN_TYPE or last - first < 3:
            continue
        points = polydata.points[first:last]
        steps = np.diff(points, axis=0)
        lengths = np.linalg.norm(steps, axis=1)
        if lengths.min() < 1e-9 or lengths.sum() < WINDOW_END_CM:
            continue
        cumulative = np.r_[0.0, np.cumsum(lengths)]
        first_node = int(np.searchsorted(cumulative, WINDOW_START_CM))
        last_node = int(np.searchsorted(cumulative, WINDOW_END_CM))
        chord = np.linalg.norm(points[last_node] - points[first_node])
        if last_node <= first_node or chord < 1e-9:
            continue
        directions = steps / lengths[:, None]
        vertical = float((directions[len(directions) // 2:, 2] < VERTICAL_UZ).mean())
        touches_floor = int(-points[first_node:last_node + 1, 2].min() > FLOOR_DEPTH_CM)
        records.append((int(polydata.cell_arrays["subType"][line]), float(cumulative[-1]),
                        float((cumulative[last_node] - cumulative[first_node]) / chord),
                        vertical, float(-points[:, 2].min()), touches_floor))
    return records


def measure_length_distribution(polydata) -> list:
    """Structural root length per (subtype, depth band, radius band), for one tree."""
    segments = select_structural(build_polysegments(polydata, np.zeros(len(polydata.points))))
    middle = 0.5 * (segments.starts + segments.ends)
    length = np.linalg.norm(segments.ends - segments.starts, axis=1)
    depth, radius = -middle[:, 2], np.hypot(middle[:, 0], middle[:, 1])
    rows = []
    for subtype in np.unique(segments.subtype):
        chosen = segments.subtype == subtype
        table, _, _ = np.histogram2d(depth[chosen], radius[chosen],
                                     bins=(DEPTH_BANDS_CM, RADIUS_BANDS_CM), weights=length[chosen])
        rows += [(int(subtype), d, r, float(table[d, r]))
                 for d in range(table.shape[0]) for r in range(table.shape[1])]
    return rows


def measure_occupancy_shape(probability: np.ndarray, grid: VoxelGrid) -> tuple:
    """Where the root mass sits: distance to the trunk and depth, weighted by occupancy.
    Segment counts are blind to f_sa by construction, since a scaled insertion angle moves
    roots around without changing how much length gets grown."""
    total = probability.sum()
    if total == 0.0:
        return 0.0, 0.0
    distances = grid.measure_trunk_distances_cm()[None, :, :]
    depths = grid.measure_layer_depths_cm()[:, None, None]
    return (float((probability * distances).sum() / total),
            float((probability * depths).sum() / total))


def summarise_by_tree(per_tree_records: list, subtype: int, rng: np.random.Generator):
    """Pooled median tortuosity and its 90 % interval, resampling the TREES. Roots that touch the
    floor are left out. Returns None when no root of this subtype was measured."""
    trees = [np.array([r[2] for r in records if r[0] == subtype and r[5] == 0])
             for records in per_tree_records]
    trees = [tree for tree in trees if len(tree)]
    if not trees:
        return None
    medians = [np.median(np.concatenate([trees[i] for i in rng.integers(0, len(trees), len(trees))]))
               for _ in range(BOOTSTRAP_DRAWS)]
    return float(np.median(np.concatenate(trees))), np.percentile(medians, [5, 95]), len(trees)


def print_shape_summary(per_tree_records: list) -> None:
    rng = np.random.default_rng(0)
    for subtype in sorted(STRUCTURAL_SUBTYPES):
        summary = summarise_by_tree(per_tree_records, subtype, rng)
        if summary is None:
            continue
        median, (low, high), trees = summary
        print(f"{SUMMARY_INDENT} ST{subtype} tortuosite 40-100 cm {median:.3f} [{low:.3f} ; {high:.3f}]"
              f" sur {trees} arbres")


def print_depth_summary(per_tree_lengths: list) -> None:
    shares, deep_far = [], []
    for rows in per_tree_lengths:
        table = np.zeros((len(DEPTH_BANDS_CM) - 1, len(RADIUS_BANDS_CM) - 1))
        for _, depth_band, radius_band, length in rows:
            table[depth_band, radius_band] += length
        if table.sum() == 0.0:
            continue
        shares.append(table.sum(axis=1) / table.sum())
        deep = table[DEEP_BAND_START:]
        if deep.sum() > 0.0:
            deep_far.append(deep[:, FAR_RADIUS_BAND].sum() / deep.sum())
    if not shares:
        return
    shares = np.array(shares)
    for index, (low, high) in enumerate(zip(DEPTH_BANDS_CM[:-1], DEPTH_BANDS_CM[1:])):
        print(f"{SUMMARY_INDENT} longueur {low:3d}-{high:3d} cm : "
              f"{shares[:, index].mean():5.1%} +/- {shares[:, index].std():5.1%}")
    if deep_far:
        print(f"{SUMMARY_INDENT} sous {DEPTH_BANDS_CM[DEEP_BAND_START]} cm, part a plus de "
              f"{RADIUS_BANDS_CM[FAR_RADIUS_BAND]} cm du tronc : {np.mean(deep_far):5.1%}")


def save_root_records(csv_path: Path, per_tree_records: list) -> None:
    with open(csv_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(ROOT_HEADER)
        for tree_index, records in enumerate(per_tree_records):
            for record in records:
                writer.writerow([tree_index, *record])


def save_length_distribution(csv_path: Path, per_tree_lengths: list) -> None:
    """bande_profondeur : 0 = 0-30, 1 = 30-60, 2 = 60-120, 3 = 120-200, 4 = 200-306 cm.
    bande_rayon : 0 = 0-100, 1 = 100-250, 2 = beyond 250 cm from the trunk."""
    with open(csv_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(LENGTH_HEADER)
        for tree_index, rows in enumerate(per_tree_lengths):
            for row in rows:
                writer.writerow([tree_index, *row])
