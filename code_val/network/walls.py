"""Les barrieres absolues : la boite de sol moins chaque tuyau ou une racine n'a pas le droit d'entrer.

CPlantBox confine par rejet et abandonne apres une vingtaine d'essais en prenant la direction la
moins mauvaise, donc le mur n'est pas tout a fait absolu a lui seul. La marge ci-dessous couvre le
vrai trou, qui est ailleurs : Organ::createSegments fait glisser la pointe d'un dx le long de son
cap sans tester la geometrie. Elle doit donc depasser le plus grand dx du fichier de parametres,
pas la fleche d'un pas de croissance.

Seul ce module gonfle un tuyau. Les masques fractionnaires et le controle d'intrusion lisent le
rayon physique.

Un segment quelconque s'obtient sans toucher au C++ : SDF_PlantContainer est un cylindre fini le
long de +z, que deux SDF_RotateTranslate imbriques inclinent puis orientent. getDist applique
rot(-angle) au point, donc l'objet tourne de +angle, et l'origine locale atterrit sur `pos`.
"""
import math

import numpy as np
import plantbox as pb

from grid import VoxelGrid
from network.primitives import PipeSegment, build_run_segments

PIPE_EXCLUSION_MARGIN_CM = 4.0
ROUND_CROSS_SECTION = 0.0
TILT_AXIS = 1
AZIMUTH_AXIS = 2

import os
# Soil box margin (cm): the box extends this far beyond the grid, sideways and downwards, so that roots are not
# squeezed against the grid edge. TREECITY_BOX_MARGIN_CM overrides it (0 to compare with the old datasets).
DEFAULT_BOX_MARGIN_CM = 60.0
BOX_MARGIN_CM = float(os.environ.get("TREECITY_BOX_MARGIN_CM", DEFAULT_BOX_MARGIN_CM))


def build_segment_solid(segment: PipeSegment) -> pb.SignedDistanceFunction:
    start = np.asarray(segment.start_cm, float)
    end = np.asarray(segment.end_cm, float)
    direction = end - start
    length_cm = float(np.linalg.norm(direction))
    unit = direction / length_cm

    tilt_degrees = math.degrees(math.acos(float(np.clip(unit[2], -1.0, 1.0))))
    azimuth_degrees = math.degrees(math.atan2(float(unit[1]), float(unit[0])))

    body = pb.SDF_PlantContainer(segment.radius_cm, segment.radius_cm, length_cm, ROUND_CROSS_SECTION)
    tilt = pb.SDF_RotateTranslate(body, tilt_degrees, TILT_AXIS, pb.Vector3d(0.0, 0.0, 0.0))
    return pb.SDF_RotateTranslate(tilt, azimuth_degrees, AZIMUTH_AXIS, pb.Vector3d(*end))


def inflate(shape, margin_cm: float):
    if isinstance(shape, PipeSegment):
        return PipeSegment(shape.name, shape.start_cm, shape.end_cm, shape.radius_cm + margin_cm)
    return type(shape)(shape.name, shape.nodes_cm, shape.radius_cm + margin_cm)


def build_wall_segments(lumens: tuple, margin_cm: float = PIPE_EXCLUSION_MARGIN_CM) -> tuple:
    """Le debordement des coudes suit le rayon gonfle, sinon l'encoche se rouvre a la marge."""
    segments = []
    for lumen in lumens:
        thick = inflate(lumen, margin_cm)
        segments.extend([thick] if isinstance(thick, PipeSegment) else build_run_segments(thick))
    return tuple(segments)


def build_street_geometry(lumens: tuple, grid: VoxelGrid) -> pb.SignedDistanceFunction:
    """Une difference plate : imbriquer une union est la meme expression et un dispatch de plus."""
    soil_box = pb.SDF_PlantBox(2.0 * (grid.half_width_cm + BOX_MARGIN_CM),
                               2.0 * (grid.half_length_cm + BOX_MARGIN_CM),
                               grid.depth_cm + BOX_MARGIN_CM)
    solids = [build_segment_solid(segment) for segment in build_wall_segments(lumens)]
    return pb.SDF_Difference([soil_box] + solids)
