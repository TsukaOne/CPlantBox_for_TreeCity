"""Analyse des .vtp et du .vti d'un test sandbox_v3, sans pyvista (lecteurs inclus).

Affiche d'abord le resume ecrit par le sandbox (<prefixe>_summary.txt : xml, age, masses, tortuosites,
longueurs par couche, hors grille sur tous les arbres), puis pour les arbres gardes en .vtp, par sous-type :
  - le nombre de racines et leur rayon / profondeur de naissance (premier point de la polyligne),
  - la longueur structurale dans la couche du fond (297-306 cm) et la couche suivante (288-297 cm),
  - les rayons, l'effilement, le collet compare a 0,5 . c . DBH(age), la somme D2 des ST2 / D2 du collet,
et depuis le .vti : masse, support, saturation, part major / total, rapport de masse fond / suivante
(occupation et major) et part du profond (120 cm et plus) a plus de 250 cm du tronc. Le .vti est lu avec
z = 0 au fond ; ici l'indice est retourne pour que 0 soit la surface.

Usage (dans le dossier du test, ou avec le chemin) :
    python3 analyse_vtp_vti.py loose_uniform_20261020_07-40 [--age 120]
Le prefixe est le nom commun des fichiers <prefixe>.vti et <prefixe>_seed00.vtp, _seed01.vtp, ...
L'age est lu dans <prefixe>_summary.txt ; --age ne sert que s'il n'y en a pas.
"""
import argparse
import csv
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tree.attributes import DBH_AGE_EXPONENT, DBH_COEFFICIENT  # noqa: E402
from tree.species import COLLAR_TO_DBH_RATIO, PARAMETERS_DIRECTORY  # noqa: E402

ROOT_ORGAN_TYPE = 2
STRUCTURAL = (1, 2, 4, 6, 7)
BOTTOM_CM, NEXT_CM = 297.0, 288.0
DEEP_START_CM, FAR_CM = 120.0, 250.0
RADIUS_ARRAY = "radius_secondary"
TAPER_DISTANCES_CM = (100.0, 200.0, 400.0)
MURRAY_EXPONENT = 2.0           # celui des 3 especes (species.py), pour l'echelle s de fuse_radii
GRID_SHAPE = (34, 64, 64)       # profondeur, lignes, colonnes
CELL_XY_CM, CELL_Z_CM = 15.0, 9.0
SAMPLE_STEP_CM = 1.0            # pas d'echantillonnage de dataset/occupancy.py
HALF_WIDTH_CM = 0.5 * GRID_SHAPE[2] * CELL_XY_CM
HALF_LENGTH_CM = 0.5 * GRID_SHAPE[1] * CELL_XY_CM
DEPTH_CM = GRID_SHAPE[0] * CELL_Z_CM
FLOOR_TOLERANCE_CM = 1.0        # celle de grid.py : jusqu'a 1 cm sous le fond, le point reste dans la derniere couche
DEFAULT_AGE_YEARS = 120.0       # celui de sandbox_v3.py
SATURATION_LEVELS = (0.9, 0.99)
LMAX_TOLERANCE_DEV = 3.0        # une racine plus longue que lmax + 3 dev est hors limite


def read_vtp(path):
    """Points, connectivite, offsets et tableaux de cellules (subType, organType, ...) d'un .vtp ASCII."""
    root = ET.parse(path).getroot()
    points = np.array(root.find(".//Points/DataArray").text.split(), dtype=float).reshape(-1, 3)
    lines = root.find(".//Lines")
    connectivity = np.array(lines.find("DataArray[@Name='connectivity']").text.split(), dtype=np.int64)
    offsets = np.array(lines.find("DataArray[@Name='offsets']").text.split(), dtype=np.int64)
    cells = {a.get("Name"): np.array(a.text.split(), dtype=float) for a in root.find(".//CellData")}
    return points, connectivity, offsets, cells


def read_vti(path):
    """Champs d'un .vti binaire (float32, donnees ajoutees apres le '_'), en (z, y, x), z = 0 au fond."""
    raw = Path(path).read_bytes()
    start = raw.index(b"<AppendedData")
    data = raw[raw.index(b"_", start) + 1:]
    header = raw[:start].decode()
    fields = {}
    for match in re.finditer(r'Name="(\w+)"[^>]*offset="(\d+)"', header):
        name, offset = match.group(1), int(match.group(2))
        size = struct.unpack("<I", data[offset:offset + 4])[0]
        fields[name] = np.frombuffer(data[offset + 4:offset + 4 + size], dtype="<f4").reshape(GRID_SHAPE)
    return fields


def polylines(path):
    points, connectivity, offsets, cells = read_vtp(path)
    starts = offsets - np.diff(offsets, prepend=0)
    subtypes = cells["subType"].astype(int)
    organs = cells["organType"].astype(int)
    for index, (first, last) in enumerate(zip(starts, offsets)):
        if organs[index] == ROOT_ORGAN_TYPE:
            yield subtypes[index], points[connectivity[first:last]]


def polyline_radii(path, name=RADIUS_ARRAY):
    """(sous-type, points, rayons des noeuds) de chaque racine, depuis le tableau de points `name` (.vtp ASCII)."""
    node = ET.parse(path).getroot().find(f".//PointData/DataArray[@Name='{name}']")
    if node is None:
        return
    values = np.array(node.text.split(), dtype=float)
    points, connectivity, offsets, cells = read_vtp(path)
    starts = offsets - np.diff(offsets, prepend=0)
    subtypes = cells["subType"].astype(int)
    organs = cells["organType"].astype(int)
    for index, (first, last) in enumerate(zip(starts, offsets)):
        if organs[index] == ROOT_ORGAN_TYPE:
            yield subtypes[index], points[connectivity[first:last]], values[connectivity[first:last]]


def sample_polyline(line, step=SAMPLE_STEP_CM):
    """Points espaces d'environ `step` cm le long d'une polyligne, comme occupancy.sample_points_along."""
    starts, ends = line[:-1], line[1:]
    lengths = np.linalg.norm(ends - starts, axis=1)
    per_segment = np.maximum(2, np.ceil(lengths / step).astype(int) + 1)
    index = np.repeat(np.arange(len(starts)), per_segment)
    first = np.repeat(np.cumsum(per_segment) - per_segment, per_segment)
    fraction = (np.arange(per_segment.sum()) - first) / np.repeat(per_segment - 1, per_segment)
    return starts[index] + fraction[:, None] * (ends - starts)[index]


def split_outside_samples(points):
    """Echantillons hors grille (meme regle que VoxelGrid.locate_points), un seul motif par point :
    fond d'abord, puis cotes, puis surface. Renvoie (nb fond, nb cotes, nb surface, profondeurs du fond)."""
    depth = -points[:, 2]
    bottom = depth >= DEPTH_CM + FLOOR_TOLERANCE_CM
    lateral = ~bottom & ((points[:, 0] < -HALF_WIDTH_CM) | (points[:, 0] >= HALF_WIDTH_CM)
                         | (points[:, 1] < -HALF_LENGTH_CM) | (points[:, 1] >= HALF_LENGTH_CM))
    top = ~bottom & ~lateral & (depth < 0.0)
    return int(bottom.sum()), int(lateral.sum()), int(top.sum()), depth[bottom]


def measure_area_scale(path):
    """Echelle s de fuse_radii au collet (1er noeud de ST1) : (r_age^e - r_prim^e) / (r_murray^e - r_prim^e).

    Proche de 1 : le profil de Murray et la loi d'age donnent deja la meme section au collet.
    """
    first = {}
    for name in ("radius_primary", "radius_age", "radius_murray"):
        values = [line_values[0] for subtype, _, line_values in polyline_radii(path, name) if subtype == 1]
        if not values:
            return None
        first[name] = max(values)
    primary = first["radius_primary"] ** MURRAY_EXPONENT
    anchor = first["radius_murray"] ** MURRAY_EXPONENT - primary
    return (first["radius_age"] ** MURRAY_EXPONENT - primary) / anchor if anchor > 0 else None


def analyse_vtp(prefix, age_years):
    counts, births, bottom, below = {}, {}, {}, {}
    outside, overshoot = np.zeros(3, dtype=int), []
    seeds = sorted(Path(".").glob(f"{prefix}_seed*.vtp")) or sorted(Path(prefix).parent.glob(f"{Path(prefix).name}_seed*.vtp"))
    for path in seeds:
        for subtype, line in polylines(path):
            subtype = int(subtype)
            counts[subtype] = counts.get(subtype, 0) + 1
            births.setdefault(subtype, []).append((np.hypot(line[0, 0], line[0, 1]), -line[0, 2]))
            if subtype in STRUCTURAL and len(line) > 1:
                n_bottom, n_lateral, n_top, bottom_depths = split_outside_samples(sample_polyline(line))
                outside += (n_bottom, n_lateral, n_top)
                overshoot.extend(bottom_depths - DEPTH_CM)
                middle = 0.5 * (line[1:] + line[:-1])
                length = np.linalg.norm(np.diff(line, axis=0), axis=1)
                depth = -middle[:, 2]
                bottom[subtype] = bottom.get(subtype, 0.0) + length[depth >= BOTTOM_CM].sum()
                below[subtype] = below.get(subtype, 0.0) + length[(depth >= NEXT_CM) & (depth < BOTTOM_CM)].sum()
    print(f"{len(seeds)} arbres lus ({', '.join(p.name for p in seeds)})")
    detail = ""
    if overshoot:
        detail = (f" | depassement du fond : med {np.median(overshoot):.2f} p90 {np.percentile(overshoot, 90):.2f} "
                  f"max {np.max(overshoot):.2f} cm")
    print(f"Echantillons hors grille par arbre (structurales, pas {SAMPLE_STEP_CM:.0f} cm) : fond {outside[0] / len(seeds):.1f} "
          f"| cotes {outside[1] / len(seeds):.1f} | surface {outside[2] / len(seeds):.1f}{detail}")
    print("Racines par sous-type et par arbre :", {t: round(c / len(seeds), 1) for t, c in sorted(counts.items())})
    for subtype in (2, 4, 6, 7):
        if subtype in births:
            a = np.array(births[subtype])
            print(f"ST{subtype} n={len(a):3d} | rayon de naissance : med {np.median(a[:, 0]):5.0f} p90 "
                  f"{np.percentile(a[:, 0], 90):5.0f} max {a[:, 0].max():5.0f} cm | profondeur : med "
                  f"{np.median(a[:, 1]):5.0f} p90 {np.percentile(a[:, 1], 90):5.0f} cm")
    radii, profiles, proximal, scales, collars, thickest = {}, {}, [], [], [], []
    for path in seeds:
        scale = measure_area_scale(path)
        if scale is not None:
            scales.append(scale)
        collar, bases, thickest_st2 = 0.0, [], 0.0
        for subtype, line, values in polyline_radii(path):
            subtype = int(subtype)
            radii.setdefault(subtype, []).append(values)
            if subtype == 1:
                collar = max(collar, values[0])
            elif subtype == 2:
                bases.append(values[0])
                thickest_st2 = max(thickest_st2, values.max())
            if subtype in (1, 2, 4, 6, 7) and len(line) > 1 and values[0] > 0:
                distance = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))])
                for target in TAPER_DISTANCES_CM:
                    if distance[-1] >= target:
                        profiles.setdefault((subtype, target), []).append(np.interp(target, distance, values) / values[0])
        if collar > 0:
            collars.append(collar)
            thickest.append(thickest_st2 / collar)
        if collar > 0 and bases:
            proximal.append(np.sum(np.square(bases)) / collar ** 2)
    if not radii:
        print(f"Pas de tableau {RADIUS_ARRAY} dans les .vtp (ou .vtp brut / non ASCII)")
    for subtype, parts in sorted(radii.items()):
        values = np.concatenate(parts)
        print(f"ST{subtype} {RADIUS_ARRAY} : med {np.median(values):6.2f} p90 {np.percentile(values, 90):6.2f} "
              f"max {values.max():6.2f} cm ({len(values)} noeuds)")
    for subtype in (1, 2, 4, 6, 7):
        parts = [f"{target / 100:.0f} m {np.median(profiles[(subtype, target)]):.2f} (n={len(profiles[(subtype, target)])})"
                 for target in TAPER_DISTANCES_CM if (subtype, target) in profiles]
        if parts:
            print(f"ST{subtype} effilement r(D)/r(0), mediane : " + " | ".join(parts))
    if collars:
        expected = 0.5 * COLLAR_TO_DBH_RATIO * DBH_COEFFICIENT * age_years ** DBH_AGE_EXPONENT
        print(f"Collet (1er noeud de ST1) a {age_years:g} ans : med {np.median(collars):.2f} min {np.min(collars):.2f} "
              f"max {np.max(collars):.2f} cm | attendu 0.5 . c . DBH = {expected:.2f} cm + r0 du XML "
              f"(c = {COLLAR_TO_DBH_RATIO:g}) | ecart med - attendu {np.median(collars) - expected:.2f} cm")
        print(f"ST2 le plus epais / collet : max {np.max(thickest):.2f} sur {len(thickest)} arbres (doit rester < 1)")
    if proximal:
        print(f"Somme D2 des ST2 / D2 du collet : {np.mean(proximal):.2f} (Kalliokoski : 0.86 a 1.87)")
    if scales:
        print(f"Echelle s de fusion au collet (age / Murray) : med {np.median(scales):.2f} "
              f"min {np.min(scales):.2f} max {np.max(scales):.2f}")
    total_bottom, total_next = sum(bottom.values()), sum(below.values())
    if total_next > 0:
        print(f"Couche du fond (297-306 cm) {total_bottom:.0f} cm, suivante (288-297 cm) {total_next:.0f} cm, "
              f"rapport {total_bottom / total_next:.2f}")
        print("  part du fond par sous-type (%) :", {t: round(100 * v / total_bottom) for t, v in sorted(bottom.items())})


def format_ratio(value):
    return "sans objet" if not np.isfinite(value) else f"{value:.2f}"


def format_percent(value):
    return "sans objet" if not np.isfinite(value) else f"{100 * value:.1f} %"


def analyse_vti(path):
    fields = read_vti(path)
    axis = (np.arange(GRID_SHAPE[1]) - (GRID_SHAPE[1] - 1) / 2) * CELL_XY_CM
    radius = np.hypot(*np.meshgrid(axis, axis))
    for name in ("occupancy", "occupancy_major"):
        if name not in fields:
            continue
        volume = fields[name]
        saturation = " | ".join(f">{level:g} : {np.mean(volume > level):.5f} ({int((volume > level).sum())} voxels)"
                                for level in SATURATION_LEVELS)
        surface_first = volume[::-1]
        layers = surface_first.sum(axis=(1, 2))
        depth = (np.arange(GRID_SHAPE[0]) + 0.5) * CELL_Z_CM
        deep = surface_first[depth >= DEEP_START_CM]
        far = (deep * (radius >= FAR_CM)[None]).sum() / deep.sum() if deep.sum() > 0 else float("nan")
        bottom_ratio = layers[-1] / layers[-2] if layers[-2] > 0 else float("nan")
        print(f"{name}: masse moyenne {volume.mean():.5f} | support {np.mean(volume > 0):.4f} | max {volume.max():.3f}"
              f" | {saturation}")
        print(f"  fond / suivante {format_ratio(bottom_ratio)} | part du profond a plus de {FAR_CM:.0f} cm du tronc "
              f"{format_percent(far)}")
    if "occupancy" in fields and "occupancy_major" in fields and fields["occupancy"].mean() > 0:
        print(f"Part major / total (masse moyenne) : {format_percent(fields['occupancy_major'].mean() / fields['occupancy'].mean())}")


def read_lmax_limits(xml_path):
    """lmax + 3 ecarts-types de chaque sous-type, lus dans le XML (parametre `lmax` et son `dev`)."""
    limits = {}
    for root in ET.parse(xml_path).getroot().iter("root"):
        for parameter in root.findall("parameter"):
            if parameter.get("name") == "lmax":
                limits[int(root.get("subType"))] = (float(parameter.get("value"))
                                                    + LMAX_TOLERANCE_DEV * float(parameter.get("dev") or 0.0))
    return limits


def analyse_lmax(prefix, summary):
    """Racines de 100 cm et plus plus longues que lmax + 3 dev : le _roots.csv du sandbox (tous les arbres)
    et le XML nomme dans le resume, tel qu'il est au moment de l'analyse."""
    roots_csv = Path(f"{prefix}_roots.csv")
    match = re.search(r"xml (\S+) \(sha", summary or "")
    if not match or not roots_csv.exists():
        print("Racines hors lmax : non evalue (pas de _summary.txt ou de _roots.csv)")
        return
    xml_path = PARAMETERS_DIRECTORY / match.group(1)
    limits = read_lmax_limits(xml_path)
    over, total = defaultdict(list), 0
    with open(roots_csv, newline="") as file:
        for row in csv.DictReader(file):
            total += 1
            subtype, length = int(row["sous_type"]), float(row["longueur_cm"])
            if subtype in limits and length > limits[subtype]:
                over[subtype].append((int(row["arbre"]), length, float(row["profondeur_cm"])))
    trees = sorted({tree for rows in over.values() for tree, _, _ in rows})
    print(f"Racines hors lmax + {LMAX_TOLERANCE_DEV:g} dev ({xml_path.name}, {total} racines de 100 cm et plus) : "
          f"{sum(len(rows) for rows in over.values())}, arbres concernes : {trees}")
    print(f"  limites : { {t: round(v) for t, v in sorted(limits.items())} }")
    for subtype, rows in sorted(over.items()):
        lengths = sorted(length for _, length, _ in rows)
        deep = sum(depth >= 300 for _, _, depth in rows)
        print(f"  ST{subtype} : {len(rows)} racines, longueur mediane {lengths[len(lengths) // 2]:.0f} cm, "
              f"max {lengths[-1]:.0f} cm, {deep} a 300 cm de profondeur ou plus")


def read_summary(prefix):
    """Le resume ecrit par sandbox_v3 (texte, age en annees), ou (None, None) s'il n'existe pas."""
    path = Path(f"{prefix}_summary.txt")
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8").rstrip()
    match = re.search(r"age ([\d.]+) ans", text)
    return text, float(match.group(1)) if match else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prefix", help="nom commun des fichiers du test, sans extension")
    parser.add_argument("--age", type=float, default=None, help="age [ans], si le resume n'existe pas")
    arguments = parser.parse_args()
    summary, summary_age = read_summary(arguments.prefix)
    age_years = summary_age or arguments.age or DEFAULT_AGE_YEARS
    if summary:
        print("=== Resume du sandbox (tous les arbres) ===")
        print(summary)
    else:
        print(f"(pas de {arguments.prefix}_summary.txt : sandbox lance avant cette version, age suppose {age_years:g} ans)")
    print("=== Arbres gardes en .vtp et .vti ===")
    analyse_vtp(arguments.prefix, age_years)
    analyse_vti(f"{arguments.prefix}.vti")
    analyse_lmax(arguments.prefix, summary)


if __name__ == "__main__":
    main()