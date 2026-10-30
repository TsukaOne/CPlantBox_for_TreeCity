"""The retention curve of every cell, from one Rosetta call on the fine earth.

Rosetta 3 was trained on bulk densities up to 2.0 g/cm3 and silently falls back to a
texture-only model above it, so the density it sees is capped there. The cap only touches the
retention curve: the penetration resistance reads the true density.
"""
import numpy as np
import plantbox.functional.van_genuchten as vg

from soil.rosetta_batch import estimate_van_genuchten_parameters_field
from soil_v4.column import StaticSoil

ROSETTA_MAXIMUM_DENSITY_G_CM3 = 2.0


def estimate_retention(soil: StaticSoil) -> vg.Parameters:
    density = np.minimum(soil.fine_earth_density_g_cm3, ROSETTA_MAXIMUM_DENSITY_G_CM3)
    return estimate_van_genuchten_parameters_field(soil.sand_fraction, soil.clay_fraction, density)
