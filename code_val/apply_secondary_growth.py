"""Reassigne les rayons racinaires d'un vtp CPlantBox par croissance secondaire.

CPlantBox fige le rayon de chaque racine a sa creation. Ce post-processing le
recalcule apres coup selon secondary_growth_modifications.md et reecrit le vtp enrichi :
la geometrie et le CellData d'origine sont conserves, seuls des tableaux de rayons
par noeud sont ajoutes. Les parametres sont ceux de l'espece (tree/species.py) ;
--growth-rate, --allometric-exponent et --murray-exponent les remplacent.
"""
import argparse
from dataclasses import replace
from pathlib import Path

from secondary_growth.fusion import measure_taper_ratio
from secondary_growth.parameters import SecondaryGrowthParameters
from secondary_growth.polydata import read_polydata, write_polydata
from secondary_growth.radii import FINAL_RADIUS_NAME, build_radius_arrays
from tree.species import SPECIES_SLOTS, secondary_growth_for

VTP_PATTERN = "*.vtp"
OUTPUT_SUFFIX = "_thickened.vtp"


def describe(path: Path, arrays: dict, tree) -> str:
    radii = arrays[FINAL_RADIUS_NAME]
    # Un seul noeud doit rester sans parent, le collet : les autres sont des laterales non raccordees.
    unattached = len(tree.levels[0]) - 1
    return (f"{path.name} : {len(radii)} noeuds, "
            f"rayon {radii.min():.3f}-{radii.max():.2f} cm "
            f"(primaire {tree.primary_radii.max():.3f} cm), "
            f"effilement {measure_taper_ratio(radii, tree.levels):.2f}, "
            f"{unattached} laterales non raccordees, "
            f"{tree.ambiguous_links} raccords ambigus")


def build_output_path(source: Path, destination: Path, directory_mode: bool) -> Path:
    if destination is None:
        return source.with_name(source.stem + OUTPUT_SUFFIX)
    return destination / source.name if directory_mode else destination


def apply_to_file(source: Path, output: Path, parameters: SecondaryGrowthParameters) -> str:
    polydata = read_polydata(source)
    arrays, tree = build_radius_arrays(polydata, parameters)
    write_polydata(output, polydata, arrays)
    return describe(output, arrays, tree)


def collect_sources(entry: Path) -> list:
    return sorted(entry.glob(VTP_PATTERN)) if entry.is_dir() else [entry]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="un fichier .vtp ou un dossier en contenant")
    parser.add_argument("--species", required=True, choices=SPECIES_SLOTS,
                        help="espece : ses parametres sont dans tree/species.py")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="fichier ou dossier de sortie, sinon <nom>_thickened.vtp a cote")
    parser.add_argument("--growth-rate", type=float, default=None,
                        help="k [cm.jour^-alpha] : remplace celui de l'espece")
    parser.add_argument("--allometric-exponent", type=float, default=None,
                        help="alpha : remplace celui de l'espece")
    parser.add_argument("--murray-exponent", type=float, default=None,
                        help="Delta, entre 2 et 3 : remplace celui de l'espece")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    overrides = {name: value for name, value in (("secondary_growth_rate", arguments.growth_rate),
                                                 ("allometric_exponent", arguments.allometric_exponent),
                                                 ("murray_exponent", arguments.murray_exponent))
                 if value is not None}
    parameters = replace(secondary_growth_for(arguments.species), **overrides)
    sources = collect_sources(arguments.input)
    if not sources:
        raise SystemExit(f"aucun fichier .vtp dans {arguments.input}")

    directory_mode = arguments.input.is_dir()
    for source in sources:
        output = build_output_path(source, arguments.output, directory_mode)
        print(apply_to_file(source, output, parameters), flush=True)


if __name__ == "__main__":
    main()
