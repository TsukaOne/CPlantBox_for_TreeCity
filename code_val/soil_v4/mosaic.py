"""One to four profiles side by side in a scene, blended by lateral patches.

The patch geometry is v3's (soil/mosaic.py): the same seeds, transition lengths and wandering
boundaries, so build_patch_weights reads this mosaic unchanged. Only what a patch holds differs:
a drawn profile of the scene's city instead of a jittered archetype.
"""
from dataclasses import dataclass

import numpy as np

from grid import VoxelGrid
from soil.mosaic import (BOUNDARY_WANDER_CM, BOUNDARY_WANDER_LENGTH_CM, PATCH_COUNT_RANGE,
                         PRIMARY_SEED_RADIUS_CM, draw_seed_cm, draw_transition_length_cm)
from soil_library.cities import City
from soil_library.draw import DrawnProfile, draw_profile
from soil_library.profiles import PROFILES, ProfileRecipe

SEED_LIMIT = 2 ** 31


@dataclass(frozen=True)
class ProfilePatch:
    profile: DrawnProfile
    centre_row_cm: float
    centre_column_cm: float


@dataclass(frozen=True)
class ProfileMosaic:
    patches: tuple[ProfilePatch, ...]
    transition_length_cm: float
    boundary_wander_cm: float
    boundary_wander_length_cm: float
    boundary_seed: int


def draw_primary_seed_cm(rng: np.random.Generator) -> tuple[float, float]:
    angle = float(rng.uniform(0.0, 2.0 * np.pi))
    radius = float(rng.uniform(0.0, PRIMARY_SEED_RADIUS_CM))
    return radius * np.sin(angle), radius * np.cos(angle)


def draw_profile_mosaic(primary: ProfileRecipe, city: City, grid: VoxelGrid,
                        rng: np.random.Generator) -> ProfileMosaic:
    count = int(rng.integers(PATCH_COUNT_RANGE[0], PATCH_COUNT_RANGE[1] + 1))
    others = [recipe for recipe in PROFILES if recipe.identifier != primary.identifier]
    recipes = [primary] + [others[index] for index in rng.choice(len(others), count - 1, replace=False)]

    seeds, patches = [], []
    for recipe in recipes:
        seed = draw_primary_seed_cm(rng) if not seeds else draw_seed_cm(grid, seeds, rng)
        seeds.append(seed)
        patches.append(ProfilePatch(draw_profile(recipe, city, rng), *seed))
    return ProfileMosaic(tuple(patches), draw_transition_length_cm(rng), BOUNDARY_WANDER_CM,
                         BOUNDARY_WANDER_LENGTH_CM, int(rng.integers(1, SEED_LIMIT)))
