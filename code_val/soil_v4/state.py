"""The soil in one water state: moisture, suction, resistance, air and the growth factors.

The retention curve is computed once per scene; each water state only reruns what follows from
the water. A saturated cell is filled to theta_s, so it has no suction and no air, and it is not
short of water.
"""
from dataclasses import dataclass

import numpy as np
import plantbox.functional.van_genuchten as vg

from soil.growth_response import apply_water_stress
from soil.hydraulics import convert_available_water_to_moisture, convert_moisture_to_pressure_head
from soil_v4.aeration import apply_aeration, measure_air_filled_porosity
from soil_v4.column import StaticSoil
from soil_v4.factors import apply_mechanical_impedance, compute_angle_scale, compute_growth_scale
from soil_v4.resistance import MAXIMUM_RESISTANCE_MPA, estimate_penetration_resistance


@dataclass
class SoilState:
    available_water_fraction: np.ndarray
    saturated_fraction: np.ndarray
    moisture_m3_m3: np.ndarray
    whole_soil_moisture_m3_m3: np.ndarray
    pressure_head_cm: np.ndarray
    penetrometer_mpa: np.ndarray
    air_filled_porosity: np.ndarray
    bengough: np.ndarray
    water_scale: np.ndarray
    aeration_scale: np.ndarray
    growth_scale: np.ndarray
    angle_scale: np.ndarray


def compute_soil_state(soil: StaticSoil, retention: vg.Parameters, available_water: np.ndarray,
                       saturated_fraction: np.ndarray, stopped_growth_mpa: float) -> SoilState:
    unsaturated = convert_available_water_to_moisture(available_water, retention)
    moisture = unsaturated + saturated_fraction * (retention.theta_S - unsaturated)
    pressure_head = convert_moisture_to_pressure_head(moisture, retention)
    resistance = estimate_penetration_resistance(pressure_head, moisture / retention.theta_S,
                                                 soil.fine_earth_density_g_cm3,
                                                 soil.resistance_deviation_log10)
    penetrometer = np.where(soil.rootable_fraction > 0.0, resistance, MAXIMUM_RESISTANCE_MPA)
    air = measure_air_filled_porosity(soil.fine_earth_density_g_cm3, moisture, saturated_fraction)

    bengough = apply_mechanical_impedance(penetrometer, stopped_growth_mpa)
    water_scale = apply_water_stress(np.maximum(available_water, saturated_fraction))
    aeration_scale = apply_aeration(air)
    return SoilState(
        available_water_fraction=available_water,
        saturated_fraction=saturated_fraction,
        moisture_m3_m3=moisture,
        whole_soil_moisture_m3_m3=moisture * (1.0 - soil.coarse_fraction),
        pressure_head_cm=pressure_head,
        penetrometer_mpa=penetrometer,
        air_filled_porosity=air,
        bengough=bengough,
        water_scale=water_scale,
        aeration_scale=aeration_scale,
        growth_scale=compute_growth_scale(bengough, water_scale, aeration_scale,
                                          soil.rootable_fraction),
        angle_scale=compute_angle_scale(bengough),
    )
