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
from dataclasses import dataclass, field
from pathlib import Path

from secondary_growth.parameters import SecondaryGrowthParameters

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
    # Provisional for every species: the Picea abies prior of secondary_root_growth_math.md section 5.
    # The radii of an oak or a horse chestnut, and so the major/minor targets, are not calibrated.
    secondary_growth: SecondaryGrowthParameters = field(default_factory=SecondaryGrowthParameters)


SPECIES = (
    Species(PICEA_ABIES, "surface", ("my_picea_abies", "picea_abies"), 0.960),
    Species(QUERCUS_ROBUR, "taproot", ("my_quercus_robur",), 0.968),
    # depth_decay_beta is provisional: no value of its own yet, the one of the other broadleaf.
    Species(AESCULUS_HIPPOCASTANUM, "heart", ("my_aesculus_hippocastanum",), 0.968),
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