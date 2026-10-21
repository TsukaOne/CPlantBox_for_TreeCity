"""A v4 scene written in the inference contract site_request/v3.

It is what a user would have typed for this scene: the city, the layers as drawn (before the
spatial noise), the walls, and the networks the channel builder derives backfills and leaks from.
Neither water nor penetration resistance is an input any more: both follow from the city and the
physics. The seasonal water the generator drew is written for the record, under `water`.

Coordinates follow grid.py, row = y and column = x, hence the permutation of (x, y) points.
"""
from generator.site_request import REQUEST_TEMPLATE, describe_leak, describe_utility
from generator_v4.design import FILL
from soil_library.draw import SOIL, DrawnLayer, DrawnProfile

SCHEMA_VERSION = "site_request/v3"
PROVENANCE = "generator"
DESCRIBED_BLOCKS = ("tree", "city", "pit", "soil", "walls", "water", "street", "leaks")
LAYER_VALUES = ("sand_fraction", "clay_fraction", "organic_carbon_percent", "coarse_fraction",
                "compaction_class", "fine_earth_density_g_cm3")


def describe_layer(layer: DrawnLayer) -> dict:
    base = {"top_cm": layer.top_cm, "bottom_cm": layer.bottom_cm}
    if layer.kind != SOIL:
        return {"kind": "barrier", "barrier": layer.name, **base}
    return {"kind": "soil", "material": layer.component, **base,
            **{name: getattr(layer, name) for name in LAYER_VALUES}}


def describe_profile(profile: DrawnProfile, kind: str) -> dict:
    return {"profile_type": None if kind == FILL else profile.recipe,
            "water_table_depth_cm": profile.water_table_depth_cm,
            "layers": [describe_layer(layer) for layer in profile.layers]}


def describe_soil(configuration) -> dict:
    mosaic, kind = configuration.soil.mosaic, configuration.slot.kind
    primary, *others = mosaic.patches
    return {"default_profile": describe_profile(primary.profile, kind),
            "default_center_row_cm": primary.centre_row_cm,
            "default_center_column_cm": primary.centre_column_cm,
            "patches": [{"center_row_cm": patch.centre_row_cm,
                         "center_column_cm": patch.centre_column_cm,
                         "profile": describe_profile(patch.profile, kind)} for patch in others],
            "blending": {"transition_length_cm": mosaic.transition_length_cm,
                         "boundary_wander_cm": mosaic.boundary_wander_cm,
                         "boundary_wander_length_cm": mosaic.boundary_wander_length_cm,
                         "boundary_seed": mosaic.boundary_seed}}


def describe_walls(walls) -> list:
    return [{"kind": walls.kind, "path_cm": [[y, x] for x, y in panel.path_cm],
             "thickness_cm": 2.0 * panel.half_width_cm, "depth_cm": -panel.bottom_cm}
            for panel in walls.panels]


def build_site_request_v3(configuration, dataset_name: str) -> dict:
    tree, soil, water = configuration.tree, configuration.soil, configuration.soil.water
    modules = [name for name, active in (("drought", water.drought), ("runoff", water.runoff))
               if active]
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": REQUEST_TEMPLATE.format(dataset=dataset_name,
                                              identifier=configuration.identifier),
        "tree": {"species": tree.species, "age_years": tree.age_years, "dbh_cm": tree.dbh_cm,
                 "height_m": tree.height_m, "crown_depth_m": tree.crown_depth_m},
        "city": soil.city,
        "pit": {"radius_cm": configuration.pit_radius_cm, "depth_cm": configuration.pit_depth_cm,
                "variant": soil.pit.variant, "substrate": describe_layer(soil.pit.substrate)},
        "soil": describe_soil(configuration),
        "walls": describe_walls(configuration.walls),
        "water": {"modules": modules,
                  "sealed_surface": soil.mosaic.patches[0].profile.sealed_surface,
                  "seasonal_water_fraction": list(water.seasonal_water_fraction)},
        "street": {"bearing_deg": configuration.street.bearing_deg,
                   "curb_offset_cm": configuration.street.curb_offset_cm,
                   "utilities": [describe_utility(run) for run in configuration.street.utilities]},
        "leaks": [describe_leak(leak) for leak in configuration.leaks],
        "provenance": {block: PROVENANCE for block in DESCRIBED_BLOCKS},
    }
