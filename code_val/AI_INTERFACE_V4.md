# AI interface, dataset v4

One page for the three consumers of dataset v4: **training**, **inference**, **web app**.
Sources of truth: `generator_v4/tensors.py` (channels, FiLM), `site_request_v3.schema.json`
(contract). If this page and the code disagree, the code wins. Channel schema: `v5`.

## 0. The pipeline

1. **Training**: the U-Net is trained on dataset v4 (26-channel tensor + 16-value FiLM, section 1).
2. **Inference**: adapted to build the same tensor and FiLM from a `site_request/v3` (section 2).
3. **Web app**: the user builds a `site_request/v3` in six steps, then runs the inference on this new site (section 3):
   a. tree attributes and species; b. soil, from the archetypes, editable; c. planting pit, own design or the archetype's;
   d. networks: keep, add or move; e. review; f. run inference, the model predicts the root distribution.

## 1. Training: what the tensors contain

Input tensor `(C, depth, row, column)`, float. Read channels **by name**, never by index: the
names are written in the dataset metadata (`film_names`, channel names, `generator_v4/writer.py`).

| # | Channels | Origin |
|---|---|---|
| 1-15 | `penetrometer`, `bulk_density`, `available_water`, `sand_fraction`, `clay_fraction`, `water_scale`, `growth_scale`, `pipe_fraction`, `pipe_clearance`, `backfill_fraction`, `surround_fraction`, `leak_plume`, `pit_mask`, `depth`, `prior` | v3 baseline |
| 16-19 | `bengough`, `water_gradient_down`, `water_gradient_row`, `water_gradient_column` | v3 hybrid |
| 20-26 | `organic_carbon` (% / 5), `coarse_fraction`, `rootable`, `wall_fraction`, `air_filled_porosity`, `aeration_scale`, `saturated_fraction` | **new in v4** |

- Baseline model: channels 1-15 + 20-26 = **22**. Hybrid model: all minus `depth` and `growth_scale` = **24**.
- Meaning changed on two v3 channels: `penetrometer` is derived (not typed in), `bulk_density` is the fine-earth density.
- All channels are the **mean-state** water (`MEAN_STATE`); no hydrotropism in v4.

FiLM vector, **16** scalars, in this order:

| Group | Components |
|---|---|
| species one-hot (3) | `picea_abies`, `quercus_robur`, `aesculus_hippocastanum` |
| architecture one-hot (3) | `surface`, `taproot`, `heart` |
| tree (4) | `age_years`, `dbh_cm`, `height_m`, `crown_depth_m` |
| pit (2) | `pit_radius_cm`, `pit_depth_cm` |
| network (1) | `utility_count` (/ 10, saturated) |
| city water, **new** (3) | `annual_water_fraction` (mean of the 4 seasons), `seasonal_water_amplitude` (max - min), `frozen_winter` |

Rules:
- **No city or soil-profile one-hot in FiLM**, on purpose: a one-hot lets the network learn a lookup table and breaks the held-out city / profile tests. Only the city's water enters.
- Sizes (22/24 channels, 16 FiLM) must come from the metadata, not from constants: adding a species changes the one-hot length.
- Channels 1-19 and FiLM 1-13 keep the v3 order, so a name-based loader works on v3 and v4.

## 2. Inference: aligning on `site_request/v3`

The network never reads the JSON. The channel builder must turn a `site_request/v3` into the
same 26 channels and 16 FiLM values as `generator_v4/build.py` does for a training scene.
Training scenes are also written as `site_request/v3` under `site_request/`: **use them as the
reference test**: rebuild tensors from the JSON and compare with the stored ones.

| Network input | Comes from `site_request/v3` |
|---|---|
| species / architecture one-hot | `tree.species`; `tree.architecture` if given, else the species default |
| `age_years`, `dbh_cm`, `height_m` | `tree.*`, normalised with the ranges of `dataset/tensors.py` |
| `crown_depth_m` | `tree.crown_depth_m`, else `0.6 * height_m` |
| `pit_radius_cm`, `pit_depth_cm` | `pit.radius_cm`, `pit.depth_cm` |
| `utility_count` | `len(street.utilities) / 10`, saturated at 10 |
| city water (3 FiLM values) | `city` climate; `water.seasonal_water_fraction` only if given |
| soil channels | `soil.default_profile` (+ `patches`, `blending`), layers, `pit.substrate`, `walls` |
| `penetrometer`, `available_water`, `air_filled_porosity`... | **derived** from layer texture, density, city climate. Never read from the request |
| network / leak channels | `street.utilities`, `street.bearing_deg`, `curb_offset_cm`; `leaks` (null = automatic placement at leaking joints) |

Ported in TreeCity, `ai/root_voxel/preprocessing/` (branch `root_voxel_v4`), with no dependency on
this repository; `python -m root_voxel.checks.compare_dataset` rebuilds training scenes from
their `site_request/` and must match the stored inputs to the float16 rounding. Choices made there:
- A layer without a measured density takes the middle of its WRB class (`T - 0.009 * clay %`, lowered above 1 % organic carbon): the mean of the generator's draw. The backfills are the mean of their draw too; no soil noise is added.
- A profile is sealed when its top layer is asphalt, paving or a supported slab, as every sealed profile type; `water.sealed_surface` is traced.
- `leaks: null` (automatic placement) is refused: the app sends the list, `[]` for none.
- Mosaic: softmax blend of profiles by distance to their seeds; default profile seed at `default_center_*` (collar if absent); `boundary_seed` derived from `request_id` if null.
- Warn, do not refuse, outside `x-training-range`.
- `site_request_v3.schema.json` still has `[0, 0]` ranges on the new layer and wall fields: unusable for normalisation or extrapolation warnings until `measure_training_ranges.py --schema code_val/site_request_v3.schema.json --dataset <v4>` is run.

## 3. Web app: the six steps and what each writes

The app builds one `site_request/v3`. Required at the end: `schema_version = "site_request/v3"`,
`tree`, `city`, `pit`, `soil.default_profile`, `street`.

| Step | User does | Writes |
|---|---|---|
| a. Tree | sets attributes, picks the species (3 only: one dataset folder per tree XML, any other is out-of-distribution) | `tree` (`species`, `age_years`, `dbh_cm`, `height_m`, optional `crown_depth_m`, `architecture`), `city` |
| b. Soil | picks a soil archetype (P01-P12, made of materials M01-M12), then optionally edits it | `soil.default_profile.layers` top-first, up to 3 `patches`, `water_table_depth_cm`; `walls` |
| c. Pit | designs the planting pit, or keeps the archetype's | `pit` (`radius_cm`, `depth_cm`, `substrate`, `variant`) |
| d. Networks | keeps the networks in place, or adds / moves some | `street.utilities` (`nodes_cm`, `radius_cm`, `trench_half_width_cm`, `leakage_status`...), `street.curb_offset_cm`, `street.bearing_deg` |
| e. Review | checks everything, sees what was measured and what was assumed | reads `provenance` and the warnings below |
| f. Run | sends the request; the model predicts the root distribution | nothing new; the result is reprojected with `frame` |

Notes per step:
- **b.** A layer is `soil` (sand and clay fractions + `compaction_class` or a measured density; organic carbon and stones optional) or `barrier` (`asphalt`, `paving`, `supported slab`, `buried slab`, `limestone`, `granite`). Editing a library layer keeps `material` / `profile_type` as labels only: the network never reads them, it reads the numbers. Walls: `foundation`, `narrow_strip`, `confined_pit` (closed path), each with `thickness_cm` and `depth_cm`.
- **c.** A pit is dug through asphalt, paving and a supported slab, never through the other barriers, and stops on the first deep barrier of the soil.
- **d.** Leave `leaks` out: plumes are placed automatically at the joints of `minor` / `major` conduits. Nodes may leave the box, they are clipped. Max 3 nodes per conduit; beyond 10 conduits the FiLM count saturates.
- **Do not send** water, penetrometer or density-from-resistance values: they are derived. `water.seasonal_water_fraction` is left out; the city gives the climate, and `water.modules` (`drought`, `runoff`) and `sealed_surface` are the only water inputs.
- **Orientation**: the app sets `frame.azimuth_deg` (box +column axis, degrees clockwise from north) from the nearest street axis, so `street.bearing_deg` is only the residual, **within +-40 deg**. `frame` (CRS, collar easting / northing) is always sent by the app.
- **Review warnings**: show a warning (not an error) when a value leaves its `x-training-range`.
- `observations` are for checking only, never a channel.
