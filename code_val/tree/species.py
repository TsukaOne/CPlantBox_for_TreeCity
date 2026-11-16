"""The species of the project, in one place.

One record per species: its name, its root architecture, the CPlantBox parameter files that belong
to it, the depth decay of its root prior and its secondary growth.
Adding a tree means adding one record to SPECIES, and nowhere else.

The order of SPECIES is the order of the species slots of the FiLM vector: reordering it, or
inserting a species before the last one, changes the meaning of the inputs of a trained network.

A parameter file is identified by the prefix of its file name: the variants that are tested one
by one (my_Quercus_robur_T4.xml) share the species of the file they derive from.
"""
import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

from dataset.occupancy import STRUCTURAL_SUBTYPES
from secondary_growth.parameters import NEUTRAL_AXIS_TAPER, SecondaryGrowthParameters
from tree.attributes import DAYS_PER_YEAR, DBH_AGE_EXPONENT, DBH_COEFFICIENT

PICEA_ABIES = "picea_abies"
QUERCUS_ROBUR = "quercus_robur"
AESCULUS_HIPPOCASTANUM = "aesculus_hippocastanum"

ARCHITECTURE_SLOTS = ("surface", "taproot", "heart")

PARAMETERS_DIRECTORY = Path(__file__).resolve().parent.parent / "parameters"


@dataclass(frozen=True)
class Species:
    name: str
    architecture: str                 # one of ARCHITECTURE_SLOTS
    xml_prefixes: tuple               # lowercase prefixes of the parameter files of this species
    depth_decay_beta: float           # Gale and Grigal, for the depth profile of the prior
    # Secondary growth of the species: collar diameter tied to the project DBH, taper from Kalliokoski et al.
    # (see secondary_growth_modifications.md, section 2). Broadleaves use a Betula proxy: provisional.
    secondary_growth: SecondaryGrowthParameters

# Collar diameter D0 = COLLAR_TO_DBH_RATIO * DBH(age). 1.0 is the lower bound (a root collar is usually
# wider than the DBH); no source. The radius is D0 / 2, hence the factor 0.5; k is computed, not typed.
COLLAR_TO_DBH_RATIO = 1.0
PICEA_SECONDARY_GROWTH = SecondaryGrowthParameters(
    secondary_growth_rate=0.5 * COLLAR_TO_DBH_RATIO * DBH_COEFFICIENT / DAYS_PER_YEAR ** DBH_AGE_EXPONENT,
    allometric_exponent=DBH_AGE_EXPONENT,
    murray_exponent=2.0, maximum_radius_cm=40.0,
    main_axis_taper=(1.739, -0.043),
    primary_axis_taper=NEUTRAL_AXIS_TAPER,
    secondary_axis_taper=(1.409, -0.095),
    structural_subtypes=STRUCTURAL_SUBTYPES)
# Broadleaf taper: Betula pendula, mature MT stand (Kalliokoski et al. 2008, Table 7), proxy
BROADLEAF_PROVISIONAL = replace(PICEA_SECONDARY_GROWTH, maximum_radius_cm=40.0,
                                main_axis_taper=(1.112, -0.022),
                                secondary_axis_taper=(1.801, -0.462))


SPECIES = (
    Species(PICEA_ABIES, "surface", ("my_picea_abies", "picea_abies"), 0.960, PICEA_SECONDARY_GROWTH),
    Species(QUERCUS_ROBUR, "taproot", ("my_quercus_robur",), 0.968, BROADLEAF_PROVISIONAL),
    # depth_decay_beta is provisional: no value of its own yet, the one of the other broadleaf.
    Species(AESCULUS_HIPPOCASTANUM, "heart", ("my_aesculus_hippocastanum",), 0.968, BROADLEAF_PROVISIONAL),
)

SPECIES_SLOTS = tuple(species.name for species in SPECIES)
ARCHITECTURE_OF_SPECIES = {species.name: species.architecture for species in SPECIES}
GALE_GRIGAL_BETA = {species.name: species.depth_decay_beta for species in SPECIES}


def get_species(name: str) -> Species:
    return next(species for species in SPECIES if species.name == name)


def identify_species(xml) -> str:
    file_name = Path(xml).name.lower()
    for species in SPECIES:
        if file_name.startswith(species.xml_prefixes):
            return species.name
    known = ", ".join(prefix for species in SPECIES for prefix in species.xml_prefixes)
    raise ValueError(f"unknown species for the parameter file '{Path(xml).name}': "
                     f"name it with one of the prefixes ({known}) or add it to tree/species.py")


def secondary_growth_for(species: str) -> SecondaryGrowthParameters:
    return get_species(species).secondary_growth


def hash_xml(xml) -> str:
    """Short fingerprint of the parameter file, to know exactly which version made a scene."""
    return hashlib.sha256((PARAMETERS_DIRECTORY / Path(xml).name).read_bytes()).hexdigest()[:16]