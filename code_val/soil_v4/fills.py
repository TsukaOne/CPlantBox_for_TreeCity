"""The backfills of the buried networks, as v4 materials.

The network shapes and their fill priority are v3's (network/shapes.py). Each v3 fill horizon is
replaced by a drawn v4 layer: trench sand around the pipe, recompacted trench sand in the
trench, and the pit substrate refilled loose where a trench crosses the pit. The blend by volume
fraction against a decreasing budget is the one of soil/fill.py, on the v4 channels.
"""
from dataclasses import dataclass, fields

import numpy as np

from network.street import LOOSE_BACKFILL, PIPE_SURROUND, RECOMPACTED_BACKFILL
from soil_library.draw import DrawnLayer, draw_layer, draw_texture
from soil_library.materials import TRENCH_SAND, Material
from soil_library.profiles import LayerRecipe
from soil_v4.column import StaticSoil, convert_layer_to_soil

SURROUND_CLASSES = ("IN",)
RECOMPACTED_CLASSES = ("FR", "VR")
LOOSE_CLASSES = ("LO",)


@dataclass(frozen=True)
class Backfills:
    pipe_surround: DrawnLayer
    recompacted_backfill: DrawnLayer
    loose_backfill: DrawnLayer


def draw_fill_layer(material: Material, compaction_classes: tuple, rng: np.random.Generator) -> DrawnLayer:
    recipe = LayerRecipe((material,), None, compaction_classes)
    return draw_layer(material, recipe, 0.0, None, draw_texture(material, rng), rng)


def draw_backfills(pit_material: Material, rng: np.random.Generator) -> Backfills:
    return Backfills(draw_fill_layer(TRENCH_SAND, SURROUND_CLASSES, rng),
                     draw_fill_layer(TRENCH_SAND, RECOMPACTED_CLASSES, rng),
                     draw_fill_layer(pit_material, LOOSE_CLASSES, rng))


def apply_fills(field: StaticSoil, shape_fills: tuple, coverages: tuple, backfills: Backfills) -> StaticSoil:
    soils = {PIPE_SURROUND: convert_layer_to_soil(backfills.pipe_surround),
             RECOMPACTED_BACKFILL: convert_layer_to_soil(backfills.recompacted_backfill),
             LOOSE_BACKFILL: convert_layer_to_soil(backfills.loose_backfill)}
    remaining = np.ones(field.rootable_fraction.shape)
    for (_, horizon), coverage in zip(shape_fills, coverages):
        share = np.minimum(coverage, remaining)
        remaining = remaining - share
        if horizon is None:
            continue
        fill = soils[horizon]
        field = StaticSoil(**{channel.name: getattr(field, channel.name) * (1.0 - share)
                              + getattr(fill, channel.name) * share for channel in fields(StaticSoil)})
    return field
