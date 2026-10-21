"""Layers no root crosses. A planting pit is dug through a surface barrier, never through a deep one."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Barrier:
    identifier: str
    name: str
    is_surface: bool


ASPHALT = Barrier("B01", "asphalt", True)
PAVING = Barrier("B02", "paving", True)
SUPPORTED_SLAB = Barrier("B03", "supported slab", True)
BURIED_SLAB = Barrier("B04", "buried slab", False)
LIMESTONE = Barrier("B05", "limestone", False)
GRANITE = Barrier("B06", "granite", False)

BARRIERS = (ASPHALT, PAVING, SUPPORTED_SLAB, BURIED_SLAB, LIMESTONE, GRANITE)
