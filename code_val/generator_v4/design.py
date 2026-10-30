"""Which kind of scene each identifier is: the plan of the v4 dataset, in blocks of 16.

In every block, the twelve profile types appear once, in an order shuffled per block, and four
fill scenes follow (25 %). The city turns with the block, so every profile meets every city once
in three blocks; the pit variant alternates. Profile and city weights are uniform until the first
users of the application say otherwise: everything is recorded, so the dataset can be reweighted
without being regenerated.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from soil_library.cities import CITIES
from soil_library.profiles import PROFILES
from soil_v4.pit import PIT_VARIANTS

FILL_SLOTS = 4
BLOCK_SIZE = len(PROFILES) + FILL_SLOTS
DESIGN_DOMAIN = 12
REALISTIC, FILL = "realistic", "fill"


@dataclass(frozen=True)
class SceneSlot:
    kind: str
    profile: Optional[str]
    city: str
    pit_variant: str
    fill_index: Optional[int]


def assign_slot(identifier: int, master_seed: int) -> SceneSlot:
    block, slot = divmod(identifier - 1, BLOCK_SIZE)
    pit_variant = list(PIT_VARIANTS)[(block + slot) % len(PIT_VARIANTS)]
    if slot < len(PROFILES):
        profile_index = int(np.random.default_rng([master_seed, block, DESIGN_DOMAIN])
                            .permutation(len(PROFILES))[slot])
        city = CITIES[(block + profile_index) % len(CITIES)]
        return SceneSlot(REALISTIC, PROFILES[profile_index].identifier, city.name, pit_variant, None)
    fill_slot = slot - len(PROFILES)
    city = CITIES[(block + fill_slot) % len(CITIES)]
    return SceneSlot(FILL, None, city.name, pit_variant, block * FILL_SLOTS + fill_slot)
