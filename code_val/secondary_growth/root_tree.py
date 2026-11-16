"""Reconstruction de l'arbre parent/enfant a partir d'un vtp CPlantBox.

Organism::writeVTP ecrit une polyligne par organe avec une numerotation de points
strictement sequentielle : la topologie n'est pas dans le fichier. Chaque laterale
stocke en revanche une copie bit a bit du noeud de son parent, ce qui permet de
recoller l'arbre par egalite exacte des coordonnees. L'egalite doit rester exacte,
une tolerance creerait de faux liens entre noeuds voisins.
"""
from collections import defaultdict
from typing import NamedTuple

import numpy as np

from secondary_growth.parameters import SecondaryGrowthParameters

NO_PARENT = -1


class RootTree(NamedTuple):
    parent_indices: np.ndarray      # (n_points,), NO_PARENT au collet
    levels: list                    # indices de noeuds groupes par profondeur, collet en tete
    primary_radii: np.ndarray       # (n_points,), le rayon CPlantBox
    ages: np.ndarray                # (n_points,), jours depuis la creation du noeud
    is_structural: np.ndarray       # (n_points,), booleen
    ambiguous_links: int
    subtypes: np.ndarray            # (n_points,), sous-type CPlantBox de l'organe du noeud
    axis_distances_cm: np.ndarray   # (n_points,), distance le long de l'organe depuis son premier noeud
    previous_axis_distances_cm: np.ndarray  # idem pour le noeud precedent de l'organe (0 au premier noeud)
    organ_indices: np.ndarray       # (n_points,), indice de l'organe (polyligne) de chaque noeud
    organ_identifiers: np.ndarray   # (n_organs,), identifiant CPlantBox, dans l'ordre de creation
    organ_starts: np.ndarray        # (n_organs,), indice du premier noeud de chaque organe
    organ_sizes: np.ndarray         # (n_organs,), nombre de noeuds de chaque organe


def measure_polyline_sizes(offsets: np.ndarray) -> np.ndarray:
    return np.diff(offsets, prepend=0)


def measure_axis_distances(points: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Distance cumulee le long de chaque polyligne (un organe = un axe), 0 a son premier noeud."""
    sizes = measure_polyline_sizes(offsets)
    starts = offsets - sizes
    steps = np.zeros(len(points))
    steps[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1)
    steps[starts] = 0.0
    cumulative = np.cumsum(steps)
    return cumulative - np.repeat(cumulative[starts], sizes)


def expand_to_points(values: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Etale une valeur par organe sur tous les noeuds de cet organe."""
    return np.repeat(values, measure_polyline_sizes(offsets))


def group_points_by_coordinate(points: np.ndarray) -> dict:
    lookup = defaultdict(list)
    for index, coordinate in enumerate(map(tuple, points)):
        lookup[coordinate].append(index)
    return lookup


def find_lateral_parents(candidates: list, owners: np.ndarray, orders: np.ndarray,
                         identifiers: np.ndarray, line: int) -> list:
    """Les noeuds coincidents appartenant a un organe pere plausible, plus jeune exclu."""
    return [index for index in candidates
            if owners[index] != line
            and orders[owners[index]] == orders[line] - 1
            and identifiers[owners[index]] < identifiers[line]]


def build_parent_indices(points: np.ndarray, offsets: np.ndarray, orders: np.ndarray,
                         identifiers: np.ndarray) -> tuple:
    owners = expand_to_points(np.arange(len(offsets)), offsets)
    starts = offsets - measure_polyline_sizes(offsets)
    lookup = group_points_by_coordinate(points)

    parent_indices = np.arange(len(points)) - 1
    parent_indices[starts] = NO_PARENT
    ambiguous_links = 0

    for line in np.flatnonzero(orders > 0):
        start = starts[line]
        parents = find_lateral_parents(lookup[tuple(points[start])], owners, orders, identifiers, line)
        if not parents:
            continue
        ambiguous_links += len(parents) > 1
        # Les identifiants d'organes suivent l'ordre de creation : le pere est le plus recent des candidats.
        parent_indices[start] = max(parents, key=lambda index: identifiers[owners[index]])

    return parent_indices, ambiguous_links


def measure_depths(parent_indices: np.ndarray) -> np.ndarray:
    """Distance topologique au collet, par relaxation jusqu'a stabilisation."""
    has_parent = parent_indices != NO_PARENT
    parents = np.where(has_parent, parent_indices, 0)
    depths = np.zeros(len(parent_indices), dtype=np.intp)

    # Un arbre ne peut pas etre plus profond que son nombre de noeuds : au dela, il y a un cycle.
    for _ in range(len(parent_indices)):
        updated = np.where(has_parent, depths[parents] + 1, 0)
        if np.array_equal(updated, depths):
            return depths
        depths = updated

    raise ValueError("cycle dans l'arbre racinaire reconstruit")


def group_levels(parent_indices: np.ndarray) -> list:
    """Les noeuds groupes par profondeur, du collet vers les pointes.

    Traiter les niveaux dans un sens puis dans l'autre donne les deux parcours
    topologiques dont les modeles ont besoin, sans recursion.
    """
    depths = measure_depths(parent_indices)
    return np.split(np.argsort(depths, kind="stable"), np.cumsum(np.bincount(depths))[:-1])


def measure_node_ages(polydata) -> np.ndarray:
    """L'age d'un noeud est le temps ecoule depuis sa creation a la fin de la simulation."""
    simulation_time = np.max(polydata.cell_arrays["creationTime"] + polydata.cell_arrays["age"])
    return np.clip(simulation_time - polydata.point_arrays["time"], 0.0, None)


def build_root_tree(polydata, parameters: SecondaryGrowthParameters) -> RootTree:
    offsets = polydata.offsets
    orders = polydata.cell_arrays["order"].astype(np.intp)
    identifiers = polydata.cell_arrays["id"].astype(np.intp)

    parent_indices, ambiguous_links = build_parent_indices(polydata.points, offsets, orders, identifiers)
    subtypes = expand_to_points(polydata.cell_arrays["subType"].astype(np.intp), offsets)
    distances = measure_axis_distances(polydata.points, offsets)
    previous_distances = np.concatenate([[0.0], distances[:-1]])
    sizes = measure_polyline_sizes(offsets)
    previous_distances[offsets - sizes] = 0.0

    return RootTree(
        parent_indices=parent_indices,
        levels=group_levels(parent_indices),
        primary_radii=expand_to_points(polydata.cell_arrays["radius"], offsets),
        ages=measure_node_ages(polydata),
        is_structural=np.isin(subtypes, list(parameters.structural_subtypes)),
        ambiguous_links=ambiguous_links,
        subtypes=subtypes,
        axis_distances_cm=distances,
        previous_axis_distances_cm=previous_distances,
        organ_indices=expand_to_points(np.arange(len(offsets)), offsets),
        organ_identifiers=identifiers,
        organ_starts=offsets - sizes,
        organ_sizes=sizes,
    )
