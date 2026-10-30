"""The three target cities: what their natural soil is made of, what lies under a thin soil, and
their seasonal water as a fraction of the available water capacity (spring, summer, autumn,
winter).
"""
from dataclasses import dataclass

from soil_library.barriers import BURIED_SLAB, GRANITE, LIMESTONE, Barrier
from soil_library.materials import (NATURAL_CLAY, NATURAL_LOAM, NATURAL_SAND, STONY_TILL,
                                    Material)
from soil_library.sources import TO_ERA5_LAND, TO_SOILGRIDS
from soil_library.values import Source


@dataclass(frozen=True)
class City:
    name: str
    natural_materials: tuple[Material, ...]
    natural_weights: tuple[float, ...]
    natural_weights_source: Source
    deep_barrier: Barrier
    seasonal_water_fraction: tuple[float, float, float, float]
    seasonal_water_source: Source
    frozen_winter: bool


BRUSSELS = City("Brussels", (NATURAL_LOAM, NATURAL_SAND), (0.7, 0.3), TO_SOILGRIDS, BURIED_SLAB,
                (0.85, 0.45, 0.65, 0.95), TO_ERA5_LAND, False)
HELSINKI = City("Helsinki", (NATURAL_CLAY, STONY_TILL), (0.6, 0.4), TO_SOILGRIDS, GRANITE,
                (0.90, 0.45, 0.75, 0.90), TO_ERA5_LAND, True)
TALLINN = City("Tallinn", (NATURAL_SAND, STONY_TILL), (0.5, 0.5), TO_SOILGRIDS, LIMESTONE,
               (0.85, 0.40, 0.70, 0.90), TO_ERA5_LAND, True)

CITIES = (BRUSSELS, HELSINKI, TALLINN)
