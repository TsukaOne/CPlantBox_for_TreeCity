"""Everything a v4 scene needs to grow and to be measured: the soil in every water state, the
walls, the networks, the CPlantBox domain and the lookups of the mean state.

The lookups and the geometry must stay referenced for the whole Monte Carlo loop: CPlantBox
holds the geometry and the hydrotropism soil by weak reference.
"""
from dataclasses import dataclass

from generator.network_layers import NetworkLayers, build_network_layers
from grid import VoxelGrid
from network.intrusion import find_intrusions
from network.street import StreetScene
from network.wall_geometry import build_scene_geometry
from network.wall_layouts import WallModule
from network.wall_measures import find_wall_intrusions
from soil_v4.scene import SceneSoil, SoilScene, build_scene_soil, compute_scene_state
from soil_v4.water import MEAN_STATE, list_state_fractions
from tree.growth import build_interpolated_soil_grid, build_soil_grid


@dataclass
class EnvironmentV4:
    soil: SceneSoil
    network: NetworkLayers
    walls: WallModule
    states: dict
    lumens: tuple
    geometry: object
    elongation_grid: object
    angle_grid: object
    water_lookup: object


def build_environment_v4(street: StreetScene, leaks: tuple, soil_scene: SoilScene, walls: WallModule,
                         stopped_growth_mpa: float, grid: VoxelGrid) -> EnvironmentV4:
    network = build_network_layers(street, leaks, grid)
    soil = build_scene_soil(soil_scene, network, walls.panels, grid)
    states = {name: compute_scene_state(soil, soil_scene, network, fraction, stopped_growth_mpa)
              for name, fraction in list_state_fractions(soil_scene.water).items()}
    mean = states[MEAN_STATE]
    return EnvironmentV4(
        soil=soil, network=network, walls=walls, states=states, lumens=network.shapes.lumens,
        geometry=build_scene_geometry(network.shapes.lumens, walls.panels, grid),
        elongation_grid=build_soil_grid(mean.growth_scale, grid),
        angle_grid=build_soil_grid(mean.angle_scale, grid),
        water_lookup=build_interpolated_soil_grid(mean.water_scale, grid))


def find_pipe_and_wall_intrusions(environment: EnvironmentV4, segments) -> dict:
    return {**find_intrusions(segments, environment.lumens),
            **find_wall_intrusions(segments, environment.walls.panels)}
