"""Grow one root system through the seasons: the elongation and angle grids change every season.

CPlantBox reads f_se at every simulate() and f_sa at the birth of each lateral, both through the
root parameters the plant holds (Root.cpp:147, Root.cpp:51), so wiring other grids on those
parameters between two steps is enough. The hydrotropism keeps the lookup it was built with at
initialize() (a weak_ptr, Plant.cpp:386): it stays on the mean water state. Never call
plant.copy() once the grids are wired: EquidistantGrid3D copies raw pointers (soil.h:409).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import plantbox as pb

from tree.attributes import DAYS_PER_YEAR
from tree.growth import TIME_STEP_DAYS, assign_soil_hooks, create_plant

SEASON_COUNT = 4
SEASON_LENGTH_DAYS = DAYS_PER_YEAR / SEASON_COUNT


@dataclass(frozen=True)
class SeasonalGrids:
    elongation: tuple
    angle: tuple


def find_season(step: int) -> int:
    return int((step * TIME_STEP_DAYS % DAYS_PER_YEAR) // SEASON_LENGTH_DAYS)


def grow_plant_through_seasons(geometry, grids: SeasonalGrids, seed: int, age_years: float,
                               tree: Path, water_lookup: pb.SoilLookUp,
                               vtp_path: Optional[Path]) -> pb.Plant:
    plant = create_plant(geometry, grids.elongation[0], seed, tree, grids.angle[0], water_lookup)
    season = 0
    for step in range(round(age_years * DAYS_PER_YEAR / TIME_STEP_DAYS)):
        if find_season(step) != season:
            season = find_season(step)
            assign_soil_hooks(plant, grids.elongation[season], grids.angle[season])
        plant.simulate(TIME_STEP_DAYS, False)

    if vtp_path is not None:
        vtp_path.parent.mkdir(parents=True, exist_ok=True)
        plant.write(str(vtp_path))
    return plant
