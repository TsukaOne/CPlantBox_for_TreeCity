"""Compare the soil physics with published values.

    python3 code_val/soil_v4/check_references.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soil.growth_response import STOPPED_GROWTH_RESISTANCE_MPA, apply_bengough
from soil.hydraulics import convert_available_water_to_moisture
from soil_library.compaction import measure_class_bounds, measure_class_edges
from soil_v4.column import StaticSoil
from soil_v4.factors import apply_mechanical_impedance
from soil_v4.resistance import convert_head_to_suction_kpa
from soil_v4.retention import estimate_retention
from soil_v4.state import compute_soil_state

LOAM_TEXTURE = (0.20, 0.20)
STRUCTURAL_SOIL_TEXTURE = (0.33, 0.33)
STRUCTURAL_SOIL_COARSE_FRACTION = 0.60
REFERENCE_ORGANIC_CARBON_PERCENT = 1.0
LOAM_CLASSES = ("LO", "IN", "FR")
WATER_FRACTIONS = (1.0, 0.6, 0.3, 0.0)
NRCS_SILT_LOAM_LIMITS_G_CM3 = (1.65, 1.80)
CU_SOIL_DENSITY_G_CM3 = (1.87, 2.04)
CU_SOIL_AVAILABLE_WATER = (0.07, 0.11)
RESISTANCE_SAMPLES = 501


def build_soil(texture: tuple, coarse_fraction: float, densities) -> StaticSoil:
    density = np.asarray(densities, float)
    sand, clay = texture
    return StaticSoil(np.full_like(density, sand), np.full_like(density, clay),
                      np.full_like(density, REFERENCE_ORGANIC_CARBON_PERCENT),
                      np.full_like(density, coarse_fraction), density, np.zeros_like(density),
                      np.ones_like(density))


def measure_class_middle(compaction_class: str, clay_fraction: float) -> float:
    return float(np.mean(measure_class_bounds(compaction_class, clay_fraction,
                                              REFERENCE_ORGANIC_CARBON_PERCENT)))


def report_class_boundaries() -> None:
    edges = measure_class_edges(LOAM_TEXTURE[1], REFERENCE_ORGANIC_CARBON_PERCENT)
    print(f"WRB IN|FR and FR|VR for a 20 % clay loam: {edges[3]:.2f} and {edges[4]:.2f} g/cm3"
          f"  (NRCS silt loam: affects growth {NRCS_SILT_LOAM_LIMITS_G_CM3[0]},"
          f" restricts {NRCS_SILT_LOAM_LIMITS_G_CM3[1]})")


def report_structural_soil() -> None:
    density = measure_class_middle("LO", STRUCTURAL_SOIL_TEXTURE[1])
    soil = build_soil(STRUCTURAL_SOIL_TEXTURE, STRUCTURAL_SOIL_COARSE_FRACTION, [density])
    retention = estimate_retention(soil)
    capacity = convert_available_water_to_moisture(np.ones(1), retention)
    wilting = convert_available_water_to_moisture(np.zeros(1), retention)
    available = float((capacity - wilting)[0] * (1.0 - STRUCTURAL_SOIL_COARSE_FRACTION))
    print(f"structural soil (LO fine earth {density:.2f}, stones {STRUCTURAL_SOIL_COARSE_FRACTION}):"
          f" whole-soil density {soil.whole_soil_density_g_cm3[0]:.2f} (CU-Soil {CU_SOIL_DENSITY_G_CM3}),"
          f" available water {available:.3f} (CU-Soil {CU_SOIL_AVAILABLE_WATER})")


def report_loam_resistance() -> None:
    print("loam penetration resistance, MPa (Bengough 2011: ~90 % of field readings < 2 MPa at -10 kPa)")
    for compaction_class in LOAM_CLASSES:
        density = measure_class_middle(compaction_class, LOAM_TEXTURE[1])
        soil = build_soil(LOAM_TEXTURE, 0.0, [density])
        retention = estimate_retention(soil)
        cells = []
        for fraction in WATER_FRACTIONS:
            state = compute_soil_state(soil, retention, np.full(1, fraction), np.zeros(1),
                                       STOPPED_GROWTH_RESISTANCE_MPA)
            suction = convert_head_to_suction_kpa(state.pressure_head_cm)[0]
            cells.append(f"water {fraction:.1f}: {suction:6.0f} kPa -> {state.penetrometer_mpa[0]:4.2f}")
        print(f"  {compaction_class} {density:.2f} g/cm3   " + "   ".join(cells))


def report_saturation() -> None:
    soil = build_soil(LOAM_TEXTURE, 0.0, [measure_class_middle("IN", LOAM_TEXTURE[1])])
    state = compute_soil_state(soil, estimate_retention(soil), np.full(1, 0.5), np.ones(1),
                               STOPPED_GROWTH_RESISTANCE_MPA)
    print(f"saturated loam: air {state.air_filled_porosity[0]:.3f}, aeration"
          f" {state.aeration_scale[0]:.2f}, resistance {state.penetrometer_mpa[0]:.2f} MPa,"
          f" f_se {state.growth_scale[0]:.2f}")


def report_v3_consistency() -> None:
    resistance = np.linspace(0.0, 5.0, RESISTANCE_SAMPLES)
    gap = np.abs(apply_mechanical_impedance(resistance, STOPPED_GROWTH_RESISTANCE_MPA)
                 - apply_bengough(resistance)).max()
    print(f"mechanical impedance at {STOPPED_GROWTH_RESISTANCE_MPA} MPa vs v3 Bengough: max gap {gap:.1e}")


if __name__ == "__main__":
    report_class_boundaries()
    report_structural_soil()
    report_loam_resistance()
    report_saturation()
    report_v3_consistency()
