"""Fusion des modeles et contraintes de continuite.

Murray donne la forme, la loi d'age donne la magnitude : ce sont deux informations
orthogonales, l'une dit comment le bois se repartit dans la hierarchie, l'autre combien
il en a ete depose. Aucune des deux ne suffit seule.

Mesure sur un Picea de 120 ans, rayon median par ordre 0 a 3 :
  r_age    4,785  4,423  4,255  4,231  -> plat, effilement 0,82 contre les 0,5 attendus
  r_murray 0,542  0,192  0,098  0,060  -> effilement 0,08, mais collet 6x trop fin
r_age ne depend que du temps, donc a 120 ans il epaissit une laterale de 3e ordre autant
que le collet. r_murray respecte la hierarchie mais part du rayon primaire de CPlantBox,
trop fin d'un a deux ordres de grandeur. On garde donc le profil de Murray et on l'ancre
sur le collet de la loi d'age.
"""
import numpy as np


def fuse_radii(primary_radii: np.ndarray, age_radii: np.ndarray, murray_radii: np.ndarray,
               is_structural: np.ndarray, levels: list, exponent: float = 2.0) -> np.ndarray:
    collar = levels[0]
    primary_power = primary_radii ** exponent
    anchor = (murray_radii[collar] ** exponent - primary_power[collar]).max()
    target = (age_radii[collar] ** exponent - primary_power[collar]).max()
    ratio = target / anchor if anchor > 0.0 else 1.0
    excess = np.maximum(murray_radii ** exponent - primary_power, 0.0)
    fused = (primary_power + ratio * excess) ** (1.0 / exponent)
    return np.where(is_structural, fused, primary_radii)


def enforce_continuity(radii: np.ndarray, parent_indices: np.ndarray, levels: list,
                       primary_radii: np.ndarray, maximum_radius_cm: float) -> np.ndarray:
    """Aucune racine plus fine que son rayon primaire, ni plus epaisse que son porteur.

    Les deux contraintes se contredisent quand CPlantBox tire une laterale plus epaisse
    que le segment qui la porte. La continuite l'emporte alors sur le plancher primaire.
    """
    constrained = np.clip(radii, primary_radii, maximum_radius_cm)

    # Descente du collet vers les pointes : le parent est deja contraint quand on traite ses fils.
    for level in levels[1:]:
        constrained[level] = np.minimum(constrained[level], constrained[parent_indices[level]])

    return constrained


def measure_taper_ratio(radii: np.ndarray, levels: list) -> float:
    """Validation interne section 4 : r(pointe) / r(base) attendu sous 0.5 sur un arbre age."""
    return float(radii[levels[-1]].mean() / radii[levels[0]].mean())
