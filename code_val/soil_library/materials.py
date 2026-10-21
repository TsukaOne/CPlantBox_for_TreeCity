"""The twelve materials a profile layer is made of, as fine-earth properties.

Texture follows the USDA convention (sand above 50 um), as Rosetta expects. Coarse fragments are
a whole-soil volume fraction. The compaction class is not a property of the material: the
profile chooses it.
"""
from dataclasses import dataclass

from soil_library.sources import (FAWB_2015, FLL_SHEETS, GRABOSKY_2009, GRABOSKY_2009_DERIVED,
                                  NEHLS_2013, SOILGRIDS_BRUSSELS, SOILGRIDS_HELSINKI,
                                  TO_GEOLOGICAL_SURVEYS, TO_PLANTING_SPECIFICATIONS,
                                  TO_PRODUCT_SHEETS, TO_SOILGRIDS, TO_URBAN_SURVEYS,
                                  TREE_SAND_SHEETS)
from soil_library.values import ValueRange

ORGANIC_MATTER_PER_CARBON = 1.724


@dataclass(frozen=True)
class Material:
    identifier: str
    name: str
    sand_fraction: ValueRange
    clay_fraction: ValueRange
    organic_carbon_percent: ValueRange
    coarse_fraction: ValueRange


NATURAL_LOAM = Material(
    "M01", "natural loam", ValueRange(0.09, 0.26, SOILGRIDS_BRUSSELS),
    ValueRange(0.18, 0.31, SOILGRIDS_BRUSSELS), ValueRange(1.3, 4.2, SOILGRIDS_BRUSSELS),
    ValueRange(0.0, 0.05, TO_SOILGRIDS))
NATURAL_SAND = Material(
    "M02", "natural sand", ValueRange(0.75, 0.95, TO_SOILGRIDS), ValueRange(0.02, 0.08, TO_SOILGRIDS),
    ValueRange(0.3, 1.5, TO_SOILGRIDS), ValueRange(0.0, 0.10, TO_SOILGRIDS))
NATURAL_CLAY = Material(
    "M03", "natural clay", ValueRange(0.05, 0.25, TO_SOILGRIDS),
    ValueRange(0.27, 0.36, SOILGRIDS_HELSINKI), ValueRange(0.5, 3.0, TO_SOILGRIDS),
    ValueRange(0.0, 0.05, TO_SOILGRIDS))
STONY_TILL = Material(
    "M04", "stony till", ValueRange(0.45, 0.70, TO_SOILGRIDS), ValueRange(0.05, 0.15, TO_SOILGRIDS),
    ValueRange(0.3, 1.5, TO_SOILGRIDS), ValueRange(0.15, 0.40, TO_GEOLOGICAL_SURVEYS))
IMPORTED_TOPSOIL = Material(
    "M05", "imported topsoil", ValueRange(0.30, 0.60, TO_PLANTING_SPECIFICATIONS),
    ValueRange(0.10, 0.25, TO_PLANTING_SPECIFICATIONS),
    ValueRange(1.5, 5.0, TO_PLANTING_SPECIFICATIONS), ValueRange(0.0, 0.10, TO_PLANTING_SPECIFICATIONS))
RUBBLE_FILL = Material(
    "M06", "rubble fill", ValueRange(0.40, 0.70, TO_URBAN_SURVEYS),
    ValueRange(0.05, 0.20, TO_URBAN_SURVEYS), ValueRange(0.5, 3.0, TO_URBAN_SURVEYS),
    ValueRange(0.20, 0.60, NEHLS_2013))
STRUCTURAL_SOIL = Material(
    "M07", "structural soil", ValueRange(0.20, 0.45, GRABOSKY_2009),
    ValueRange(0.27, 0.40, GRABOSKY_2009), ValueRange(0.5, 2.0, TO_PRODUCT_SHEETS),
    ValueRange(0.55, 0.65, GRABOSKY_2009_DERIVED))
TREE_SAND = Material(
    "M08", "tree sand", ValueRange(0.85, 0.93, TO_PRODUCT_SHEETS),
    ValueRange(0.01, 0.04, TREE_SAND_SHEETS),
    ValueRange(3.5 / ORGANIC_MATTER_PER_CARBON, 5.5 / ORGANIC_MATTER_PER_CARBON, TREE_SAND_SHEETS),
    ValueRange(0.0, 0.05, TO_PRODUCT_SHEETS))
PIT_SUBSTRATE = Material(
    "M09", "FLL pit substrate", ValueRange(0.55, 0.80, TO_PRODUCT_SHEETS),
    ValueRange(0.05, 0.15, TO_PRODUCT_SHEETS),
    ValueRange(1.0 / ORGANIC_MATTER_PER_CARBON, 4.0 / ORGANIC_MATTER_PER_CARBON, FLL_SHEETS),
    ValueRange(0.0, 0.30, TO_PRODUCT_SHEETS))
GRAVEL = Material(
    "M10", "gravel", ValueRange(0.70, 0.90, TO_PRODUCT_SHEETS), ValueRange(0.02, 0.08, TO_PRODUCT_SHEETS),
    ValueRange(0.0, 0.3, TO_PRODUCT_SHEETS), ValueRange(0.65, 0.80, TO_PRODUCT_SHEETS))
TRENCH_SAND = Material(
    "M11", "trench sand", ValueRange(0.85, 0.97, TO_PRODUCT_SHEETS),
    ValueRange(0.01, 0.05, TO_PRODUCT_SHEETS), ValueRange(0.0, 0.3, TO_PRODUCT_SHEETS),
    ValueRange(0.0, 0.10, TO_PRODUCT_SHEETS))
BIORETENTION_MEDIA = Material(
    "M12", "bioretention media", ValueRange(0.97, 1.0, FAWB_2015), ValueRange(0.0, 0.02, FAWB_2015),
    ValueRange(0.3, 1.5, TO_PRODUCT_SHEETS), ValueRange(0.0, 0.05, TO_PRODUCT_SHEETS))

MATERIALS = (NATURAL_LOAM, NATURAL_SAND, NATURAL_CLAY, STONY_TILL, IMPORTED_TOPSOIL, RUBBLE_FILL,
             STRUCTURAL_SOIL, TREE_SAND, PIT_SUBSTRATE, GRAVEL, TRENCH_SAND, BIORETENTION_MEDIA)
