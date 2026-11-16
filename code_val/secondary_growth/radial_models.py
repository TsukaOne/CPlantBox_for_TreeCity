"""Rayons secondaires : loi d'age et section conservee (secondary_growth_modifications.md).

La section conservee est la recurrence depuis les pointes,
coefficient * (somme des r_fille^exposant)^(1/exposant), avec un coefficient neutre (1) :
propagate_from_tips la porte pour ST1 et les fines, compute_organ_profiles pour ST2/4/6/7.
"""
import numpy as np

from secondary_growth.parameters import NEUTRAL_AXIS_TAPER
from secondary_growth.root_tree import NO_PARENT

NEUTRAL_COEFFICIENT = 1.0
PRIMARY_AXIS_SUBTYPE = 1
MAIN_AXIS_SUBTYPES = (2,)
CM_PER_M = 100.0


def compute_age_radius(primary_radii: np.ndarray, ages: np.ndarray, is_structural: np.ndarray,
                       growth_rate: float, allometric_exponent: float) -> np.ndarray:
    """Loi d'age : r_age = r0 + k.t^alpha, les racines fines gardent leur rayon primaire."""
    increment = growth_rate * ages ** allometric_exponent
    return primary_radii + np.where(is_structural, increment, 0.0)


def propagate_from_tips(parent_indices: np.ndarray, levels: list, primary_radii: np.ndarray,
                        exponent: float, coefficient: float, segment_gain: np.ndarray = None,
                        fixed_radii: np.ndarray = None) -> np.ndarray:
    """Section conservee : remontee niveau par niveau, des pointes vers le collet.

    Une pointe n'accumule rien et garde son rayon primaire, sans traitement particulier.
    segment_gain : facteur par noeud applique a son rayon en le transmettant a son parent, pour
    l'effilement le long d'une racine (sans lui, une racine sans laterale garde un rayon constant).
    fixed_radii : rayon impose par noeud, NaN si libre. Un noeud impose n'est pas recalcule, il transmet
    seulement son rayon a son parent.
    """
    gain = np.ones(len(primary_radii)) if segment_gain is None else segment_gain
    radii = primary_radii.copy()
    imposed = np.zeros(len(primary_radii), dtype=bool)
    if fixed_radii is not None:
        imposed = ~np.isnan(fixed_radii)
        radii[imposed] = fixed_radii[imposed]
    accumulated = np.zeros(len(primary_radii))

    for level in reversed(levels):
        free = level[~imposed[level]]
        radii[free] = np.maximum(primary_radii[free], coefficient * accumulated[free] ** (1.0 / exponent))
        linked = level[parent_indices[level] != NO_PARENT]
        np.add.at(accumulated, parent_indices[linked], (radii[linked] * gain[linked]) ** exponent)

    return radii


def evaluate_taper_denominator(distance_cm: np.ndarray, taper: tuple) -> np.ndarray:
    """1 + a.D + b.D^2 (D en m), 1/T de Kalliokoski et al. 2008, Eq. 2.

    Avec b < 0 le denominateur passe par un maximum a D = -a / 2b et la loi n'a plus de sens au-dela :
    D est plafonne a cette valeur.
    """
    a, b = taper
    distance_m = distance_cm / CM_PER_M
    if b < 0.0:
        distance_m = np.minimum(distance_m, -a / (2.0 * b))
    return 1.0 + a * distance_m + b * distance_m ** 2


def compute_primary_taper_gain(tree, primary_taper: tuple) -> np.ndarray:
    """Gain de rayon par noeud sur ST1 : (1/T) a son niveau sur (1/T) au noeud precedent, 1 ailleurs.

    Seul ST1 passe par la recurrence par noeud. Les organes ST2/4/6/7 portent leur effilement dans
    leur profil B.T(D) (compute_organ_profiles). Neutre (gain 1) tant que primary_taper vaut (0, 0).
    """
    ratio = (evaluate_taper_denominator(tree.axis_distances_cm, primary_taper)
             / evaluate_taper_denominator(tree.previous_axis_distances_cm, primary_taper))
    return np.where(tree.is_structural & (tree.subtypes == PRIMARY_AXIS_SUBTYPE), ratio, 1.0)


def compute_organ_profiles(tree, exponent: float, main_taper: tuple, secondary_taper: tuple) -> np.ndarray:
    """Schema par organe : r(D) = B.T(D) sur chaque organe structural autre que ST1, NaN ailleurs.

    D est la distance en m depuis le premier noeud de l'organe, T la loi d'effilement de son groupe
    (ST2 : axe principal, ST4/6/7 : axes secondaires). B est le plus petit rayon de base qui laisse, a
    chaque noeud, une section au moins egale a celle de la pointe et des laterales rattachees en aval :
        (B.T(D))^e >= r_pointe^e + somme des c_k^e, pour les laterales rattachees en D_k >= D,
    c_k etant le rayon de base de la laterale (son B si elle est structurale, son rayon primaire si c'est
    une fine). Les organes sont traites du plus recent au plus ancien : les identifiants suivent l'ordre
    de creation, donc les laterales d'un organe ont un identifiant plus grand.
    """
    starts, sizes = tree.organ_starts, tree.organ_sizes
    n_organs = len(starts)
    organ_subtypes = tree.subtypes[starts]
    tips = tree.primary_radii[starts]
    structural = tree.is_structural[starts]
    profiled = structural & (organ_subtypes != PRIMARY_AXIS_SUBTYPE)
    is_main = np.isin(organ_subtypes, MAIN_AXIS_SUBTYPES)

    parent_nodes = tree.parent_indices[starts]
    attached = parent_nodes != NO_PARENT
    parent_organs = np.where(attached, tree.organ_indices[parent_nodes], n_organs)
    attach_distances = np.where(attached, tree.axis_distances_cm[parent_nodes], 0.0)
    by_parent = np.argsort(parent_organs, kind="stable")
    bounds = np.searchsorted(parent_organs[by_parent], np.arange(n_organs + 1))

    base = np.where(structural, 0.0, tips)
    radii = np.full(len(tree.primary_radii), np.nan)
    candidates = np.flatnonzero(profiled)
    for organ in candidates[np.argsort(-tree.organ_identifiers[candidates], kind="stable")]:
        nodes = slice(starts[organ], starts[organ] + sizes[organ])
        distances = tree.axis_distances_cm[nodes]
        denominator = evaluate_taper_denominator(distances, main_taper if is_main[organ] else secondary_taper)

        laterals = by_parent[bounds[organ]:bounds[organ + 1]]
        laterals = laterals[np.argsort(attach_distances[laterals], kind="stable")]
        # Somme des c_k^e pour D_k >= D : cumul depuis le bout de l'organe, lu au premier D_k >= D.
        downstream = np.append(np.cumsum((base[laterals] ** exponent)[::-1])[::-1], 0.0)
        carried = downstream[np.searchsorted(attach_distances[laterals], distances, side="left")]

        organ_base = ((tips[organ] ** exponent + carried) ** (1.0 / exponent) * denominator).max()
        base[organ] = organ_base
        radii[nodes] = organ_base / denominator

    return radii


def compute_murray_radius(tree, murray_exponent: float, main_taper: tuple = NEUTRAL_AXIS_TAPER,
                          secondary_taper: tuple = NEUTRAL_AXIS_TAPER,
                          primary_taper: tuple = NEUTRAL_AXIS_TAPER) -> np.ndarray:
    """Schema par organe pour ST2/4/6/7, recurrence par noeud pour ST1 (et les fines)."""
    profiles = compute_organ_profiles(tree, murray_exponent, main_taper, secondary_taper)
    return propagate_from_tips(tree.parent_indices, tree.levels, tree.primary_radii, murray_exponent,
                               NEUTRAL_COEFFICIENT, compute_primary_taper_gain(tree, primary_taper), profiles)
