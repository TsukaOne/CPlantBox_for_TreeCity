"""Parametres de la croissance secondaire, un champ par constante du modele.

Aucune valeur par defaut : les valeurs de chaque espece sont dans tree/species.py, justifiees dans
secondary_growth_modifications.md.
"""
from dataclasses import dataclass

NEUTRAL_AXIS_TAPER = (0.0, 0.0)


@dataclass(frozen=True)
class SecondaryGrowthParameters:
    secondary_growth_rate: float    # k, cm.day^-alpha
    allometric_exponent: float      # alpha
    murray_exponent: float          # Delta
    maximum_radius_cm: float
    # Tapering of a root axis, T = 1 / (1 + a.D + b.D^2), D in m from the base of the axis, as (a, b)
    # (Kalliokoski et al. 2008, Silva Fennica 42(2), Eq. 2 and Table 7). (0, 0) = no tapering.
    main_axis_taper: tuple
    # ST1 : tronçon de collet (Picea, Aesculus) ou pivot (Quercus) ; neutre tant qu'aucune source
    primary_axis_taper: tuple
    secondary_axis_taper: tuple     # same law for ST4, ST6, ST7
    structural_subtypes: frozenset