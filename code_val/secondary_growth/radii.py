"""Rayons par noeud, apres croissance secondaire.
"""
from secondary_growth.fusion import enforce_continuity, fuse_radii
from secondary_growth.parameters import SecondaryGrowthParameters
from secondary_growth.radial_models import (
    compute_age_radius,
    compute_murray_radius,
)
from secondary_growth.root_tree import build_root_tree

FINAL_RADIUS_NAME = "radius_secondary"


def build_final_radii(polydata, parameters: SecondaryGrowthParameters) -> tuple:
    tree = build_root_tree(polydata, parameters)
    age_radii = compute_age_radius(tree.primary_radii, tree.ages, tree.is_structural,
                                   parameters.secondary_growth_rate, parameters.allometric_exponent)
    murray_radii = compute_murray_radius(tree, parameters.murray_exponent, parameters.main_axis_taper, 
                                         parameters.secondary_axis_taper, parameters.primary_axis_taper)
    fused = fuse_radii(tree.primary_radii, age_radii, murray_radii, tree.is_structural, tree.levels, parameters.murray_exponent)
    radii = enforce_continuity(fused, tree.parent_indices, tree.levels,
                               tree.primary_radii, parameters.maximum_radius_cm)
    return radii, tree


def build_radius_arrays(polydata, parameters: SecondaryGrowthParameters) -> tuple:
    tree = build_root_tree(polydata, parameters)
    age_radii = compute_age_radius(tree.primary_radii, tree.ages, tree.is_structural,
                                   parameters.secondary_growth_rate, parameters.allometric_exponent)
    murray_radii = compute_murray_radius(tree, parameters.murray_exponent, parameters.main_axis_taper, 
                                         parameters.secondary_axis_taper, parameters.primary_axis_taper)
    fused = fuse_radii(tree.primary_radii, age_radii, murray_radii, tree.is_structural, tree.levels, parameters.murray_exponent)

    arrays = {
        "radius_primary": tree.primary_radii,
        "radius_age": age_radii,
        "radius_murray": murray_radii,
        FINAL_RADIUS_NAME: enforce_continuity(fused, tree.parent_indices, tree.levels, tree.primary_radii, parameters.maximum_radius_cm),
    }
    return arrays, tree
