"""The twelve profile types: a stack of layer recipes, top first. The last layer runs to the bottom
of the soil box. NATURAL stands for the city's natural material and CITY_BARRIER for what lies
under a thin soil in that city.
"""
from dataclasses import dataclass
from typing import Optional

from soil_library.barriers import ASPHALT, PAVING, SUPPORTED_SLAB
from soil_library.materials import (BIORETENTION_MEDIA, GRAVEL, IMPORTED_TOPSOIL, NATURAL_CLAY,
                                    NATURAL_LOAM, NATURAL_SAND, PIT_SUBSTRATE, RUBBLE_FILL,
                                    STONY_TILL, STRUCTURAL_SOIL, TRENCH_SAND, TREE_SAND)
from soil_library.sources import DESIGN_DOCUMENT, TO_GROUNDWATER_MAPS, TO_SCENARIO_SURVEYS
from soil_library.values import ValueRange

NATURAL = "natural"
CITY_BARRIER = "city_barrier"

LOOSE = ("VL", "LO")
SOFT = ("LO", "IN")
MEDIUM = ("IN", "FR")
FIRM = ("FR", "VR")
FINE = (NATURAL_LOAM, NATURAL_CLAY)
COARSE = (NATURAL_SAND, STONY_TILL, TRENCH_SAND)


@dataclass(frozen=True)
class LayerRecipe:
    components: tuple
    thickness_cm: Optional[ValueRange]
    compaction_classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileRecipe:
    identifier: str
    name: str
    scenarios: tuple[str, ...]
    limiting_factor: str
    layers: tuple[LayerRecipe, ...]
    sealed_surface: bool = False
    water_table_depth_cm: Optional[ValueRange] = None


def build_layer(components: tuple, low_cm: float, high_cm: float,
                compaction_classes: tuple[str, ...] = ()) -> LayerRecipe:
    return LayerRecipe(components, ValueRange(low_cm, high_cm, TO_SCENARIO_SURVEYS),
                       compaction_classes)


def build_bottom_layer(compaction_classes: tuple[str, ...]) -> LayerRecipe:
    return LayerRecipe((NATURAL,), None, compaction_classes)


PROFILES = (
    ProfileRecipe("P01", "deep natural soil", ("A1", "A2", "A3", "A4"), "none (control)", (
        build_layer((NATURAL,), 20, 50, SOFT),
        build_bottom_layer(MEDIUM))),
    ProfileRecipe("P02", "thin soil over a hard layer", ("A5", "E4"), "depth", (
        LayerRecipe((NATURAL, IMPORTED_TOPSOIL), ValueRange(20, 60, DESIGN_DOCUMENT), SOFT),
        LayerRecipe((CITY_BARRIER,), None))),
    ProfileRecipe("P03", "waterlogged soil", ("A6", "D5"), "air", (
        build_layer((NATURAL,), 20, 40, SOFT),
        build_bottom_layer(("IN", "FR", "VR"))),
        water_table_depth_cm=ValueRange(40, 150, TO_GROUNDWATER_MAPS)),
    ProfileRecipe("P04", "imported topsoil over native soil", ("B1", "B4"), "interface", (
        build_layer((IMPORTED_TOPSOIL,), 30, 80, LOOSE),
        build_bottom_layer(MEDIUM))),
    ProfileRecipe("P05", "compacted soil", ("B5", "B6"), "resistance", (
        build_layer((NATURAL,), 0, 30, SOFT),
        build_layer((NATURAL,), 15, 60, FIRM),
        build_bottom_layer(("IN",)))),
    ProfileRecipe("P06", "rubble fill", ("B2", "B3", "B7"), "water and stones", (
        build_layer((IMPORTED_TOPSOIL, RUBBLE_FILL), 10, 30, SOFT),
        build_layer((RUBBLE_FILL,), 50, 200, MEDIUM),
        build_bottom_layer(MEDIUM))),
    ProfileRecipe("P07", "multilayer with sharp interfaces", ("B8", "F3"), "interface", (
        build_layer(FINE, 20, 80, SOFT),
        build_layer(COARSE, 20, 80, FIRM),
        build_layer(FINE, 20, 80, SOFT),
        build_bottom_layer(MEDIUM))),
    ProfileRecipe("P08", "sealed soil", ("E1", "E5"), "resistance and water", (
        build_layer((ASPHALT, PAVING), 5, 15),
        build_layer((GRAVEL,), 20, 40, ("VR",)),
        build_layer((RUBBLE_FILL, TRENCH_SAND), 40, 100, ("FR",)),
        build_bottom_layer(MEDIUM)), sealed_surface=True),
    ProfileRecipe("P09", "structural soil under pavement", ("C5", "C6"), "volume", (
        build_layer((PAVING,), 8, 15),
        build_layer((STRUCTURAL_SOIL,), 60, 100, LOOSE),
        build_bottom_layer(MEDIUM)), sealed_surface=True),
    ProfileRecipe("P10", "loose soil under suspended pavement", ("C7",), "none", (
        build_layer((SUPPORTED_SLAB,), 10, 20),
        build_layer((IMPORTED_TOPSOIL, PIT_SUBSTRATE), 60, 100, LOOSE),
        build_bottom_layer(("IN",))), sealed_surface=True),
    ProfileRecipe("P11", "tree sand or engineered substrate", ("C8",), "none", (
        build_layer((TREE_SAND, PIT_SUBSTRATE), 60, 120, SOFT),
        build_bottom_layer(MEDIUM))),
    ProfileRecipe("P12", "bioretention and drainage trench", ("D1", "D3", "D4"), "water", (
        build_layer((BIORETENTION_MEDIA,), 40, 90, LOOSE),
        build_layer((GRAVEL,), 20, 40, ("LO",)),
        build_bottom_layer(MEDIUM))),
)
