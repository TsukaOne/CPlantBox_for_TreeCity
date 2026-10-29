"""A value of the library: a range read as the 5th to 95th percentile, and where it comes from.

Mirrors the value format of TreeCity urban_soil, without pydantic, so the generator workers can
import it inside the CPlantBox container. ESTIMATE is added to urban_soil's provenances: a value
with no data behind it yet, whose reference names the data meant to replace it.
"""
from dataclasses import dataclass
from enum import Enum

import numpy as np


class Provenance(str, Enum):
    MEASURED = "measured"
    FIELD_ESTIMATED = "field_estimated"
    DERIVED = "derived"
    PRIOR = "prior"
    ESTIMATE = "estimate"


@dataclass(frozen=True)
class Source:
    provenance: Provenance
    reference: str


@dataclass(frozen=True)
class ValueRange:
    low: float
    high: float
    source: Source

    def draw(self, rng: np.random.Generator) -> float:
        return float(rng.uniform(self.low, self.high))

    @property
    def middle(self) -> float:
        return 0.5 * (self.low + self.high)
