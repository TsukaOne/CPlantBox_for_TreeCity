"""Draw one concrete profile from a recipe and a city.

A material that appears twice in a profile keeps one texture: the layers of a natural soil share
their parent material, only their organic carbon, stones and compaction differ.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from soil_library.barriers import Barrier
from soil_library.cities import City
from soil_library.compaction import draw_density
from soil_library.materials import Material
from soil_library.profiles import CITY_BARRIER, NATURAL, LayerRecipe, ProfileRecipe

SOIL = "soil"
SURFACE_BARRIER = "surface_barrier"
DEEP_BARRIER = "deep_barrier"


@dataclass(frozen=True)
class DrawnLayer:
    component: str
    name: str
    kind: str
    top_cm: float
    bottom_cm: Optional[float]
    sand_fraction: Optional[float] = None
    clay_fraction: Optional[float] = None
    organic_carbon_percent: Optional[float] = None
    coarse_fraction: Optional[float] = None
    compaction_class: Optional[str] = None
    fine_earth_density_g_cm3: Optional[float] = None


@dataclass(frozen=True)
class DrawnProfile:
    recipe: str
    city: str
    layers: tuple[DrawnLayer, ...]
    sealed_surface: bool
    water_table_depth_cm: Optional[float]


def draw_texture(material: Material, rng: np.random.Generator) -> tuple[float, float]:
    clay = material.clay_fraction.draw(rng)
    sand = rng.uniform(material.sand_fraction.low, min(material.sand_fraction.high, 1.0 - clay))
    return float(sand), clay


def draw_layer(material: Material, recipe: LayerRecipe, top_cm: float, bottom_cm: Optional[float],
               texture: tuple[float, float], rng: np.random.Generator) -> DrawnLayer:
    sand, clay = texture
    organic_carbon = material.organic_carbon_percent.draw(rng)
    compaction_class = recipe.compaction_classes[rng.integers(len(recipe.compaction_classes))]
    return DrawnLayer(material.identifier, material.name, SOIL, top_cm, bottom_cm, sand, clay,
                      organic_carbon, material.coarse_fraction.draw(rng), compaction_class,
                      draw_density(compaction_class, clay, organic_carbon, rng))


def draw_barrier_layer(barrier: Barrier, top_cm: float, bottom_cm: Optional[float]) -> DrawnLayer:
    kind = SURFACE_BARRIER if barrier.is_surface else DEEP_BARRIER
    return DrawnLayer(barrier.identifier, barrier.name, kind, top_cm, bottom_cm)


def resolve_component(component, natural: Material, city: City):
    if component == NATURAL:
        return natural
    if component == CITY_BARRIER:
        return city.deep_barrier
    return component


def draw_profile(recipe: ProfileRecipe, city: City, rng: np.random.Generator) -> DrawnProfile:
    natural = city.natural_materials[rng.choice(len(city.natural_materials), p=city.natural_weights)]
    textures, layers, top_cm = {}, [], 0.0
    for layer in recipe.layers:
        component = resolve_component(layer.components[rng.integers(len(layer.components))],
                                      natural, city)
        bottom_cm = top_cm + layer.thickness_cm.draw(rng) if layer.thickness_cm else None
        if isinstance(component, Barrier):
            layers.append(draw_barrier_layer(component, top_cm, bottom_cm))
        else:
            texture = textures.get(component.identifier) or draw_texture(component, rng)
            textures[component.identifier] = texture
            layers.append(draw_layer(component, layer, top_cm, bottom_cm, texture, rng))
        top_cm = bottom_cm
    water_table = recipe.water_table_depth_cm.draw(rng) if recipe.water_table_depth_cm else None
    return DrawnProfile(recipe.identifier, city.name, tuple(layers), recipe.sealed_surface,
                        water_table)
