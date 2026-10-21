# generator — the v2 scene builder

One scene, from its random seed to the three files on disk. This is where the v2 pipeline is
assembled; the physics lives in [`soil/`](../soil/README.md), the street in
[`network/`](../network/README.md), the growth in [`tree/`](../tree/README.md) and the radii in
[`secondary_growth/`](../secondary_growth/README.md).

Driven by `../build_dataset_v3.py`, one CPlantBox parameter file per tree (`--tree`) and one output
folder per tree. The package produced dataset v2 on 2026-09-22 (commit
`1b52cfb`, old θ → ψ water model, no `f_sa`) and has evolved in place since: **it no longer
reproduces the v2 files**. To derive anything from v2, read its `.npz` and `.vti` back
(`../build_dataset_v2_hybrid.py`), never rebuild its environment with this code.

## Step by step

`build_dataset_v3.py` draws all the configurations up front, then hands one to each worker.
Per scene:

1. **`scene.py::draw_scene` — everything random, decided here and nowhere else.**
   The master seed is split into five independent streams — `TREE`, `PIT`, `SOIL`, `STREET`,
   `NOISE` — through `default_rng([master_seed, identifier, domain])`. Re-tuning one domain
   therefore never reshuffles the others: the same scene number keeps the same tree when you
   change the street code. Draws the tree, the pit, the soil mosaic, the street and its leaks.
   `tree_xml` (keyword-only, required) names the CPlantBox parameter file and
   `tree.species.identify_species` reads the species from its prefix. Soil, pit, street and seeds
   do not depend on it: the same identifier is the same scene for every tree.
2. **`environment.py::build_environment` — the soil the roots will actually feel.**
   The order carries the reasoning and must not be permuted:

   | Order | Why |
   |---|---|
   | pit before fills | a network crosses the planting pit like any other soil |
   | fills before leaks | a fill arrives with its resistance and moisture already consistent; it must not then be rescaled by the moisture → resistance coupling a leak triggers |
   | Rosetta on the composited field | not on the original profile — the fills and the leak have already moved texture and moisture |
   | geometry last | `grow_plant` calls `setSoil()` then `initialize()`, and `initialize()` builds the tropism callbacks from whatever soil the plant holds at that instant |

   The returned `SceneEnvironment` is kept alive for the whole Monte Carlo loop: **CPlantBox
   holds the geometry by `weak_ptr`**, and a freed geometry stops confining roots with no error.
3. **`build.py::grow_once`, once per seed (20 by default).**
   Grow with `f_se`, `f_sa` and the water lookup → `polylines.py` reads the live plant →
   `secondary_growth` recomputes a radius per node → `voxelise.py` stamps the occupancy grids of
   each diameter class and accumulates the volume → `network/intrusion.py` checks nothing ended
   up inside a pipe.
4. **`build.py::build_scene` — the ensemble.** Counts the hits of every occupancy over the runs,
   packs the individual runs bit by bit, keeps the first run's polylines, builds `prior_v2`, and
   collects the diagnostics.
5. **`tensors.py`** builds the 19 input channels and the FiLM vector.
6. **`writer.py`** writes `.npz`, `.vti` (skipped with `write_vti=False`, as the sandbox does),
   `site_request/scene_XXXXX.json` and — last — `.json`.

## Who does what

| File | Responsibility |
|---|---|
| `scene.py` | the experimental design and every seed; `SceneConfiguration` is the complete description of a scene, XML included |
| `environment.py` | soil + street → the fields, the two CPlantBox lookups and the growth geometry |
| `polylines.py` | reads the polylines out of a *live* plant, without a round trip through a `.vtp` |
| `voxelise.py` | polylines → centreline and radius grids per diameter class, root-volume grid |
| `tensors.py` | the 19 input channels and the FiLM vector |
| `site_request.py` | the scene rewritten in the inference contract, `../site_request.schema.json` |
| `build.py` | the loop above, the ensemble, `prior_v2`, the diagnostics |
| `writer.py` | the four files, atomically |

## The targets

| Target | What it is |
|---|---|
| `target_centreline` | v1's definition: a voxel is taken if a root axis passes through it |
| `target` (radius) | a voxel is taken as soon as a root thick enough passes close enough to bite into it |
| `target_major` | the radius target, restricted to samples at least 2 cm in diameter after secondary growth |
| `target_minor` | the radius target, restricted to every other structural sample, with no lower bound |

The classes follow the **real diameter**, sample by sample, not the subtype: 2 cm is what a GPR
can see, and since secondary growth a subtype-2 root of a young tree is thinner than that. A
tapered root therefore changes class along its path. Because *minor* has no lower bound,
`major ∪ minor` is exactly `target`, so `max(major, minor) ≤ any ≤ major + minor` holds on every
voxel of every run, and the historical keys (`target`, `hit_count`, `occupancy_runs`) keep their
v2 meaning for the baseline loader. Hit counts exist for both classes and both occupancy kinds;
individual runs are packed for `radius`, `centreline`, `radius_major` and `radius_minor`.

The radius test is exact — does a sphere of radius *r* centred on the sample intersect the voxel
box — so a root lying on a face spills into the neighbour while the same root through the centre
does not. A morphological dilation per radius class would instead inflate every marked voxel
identically, after throwing away the sub-voxel position. `RADIUS_BIN_EDGES_CM` only groups
samples so one offset table can serve a batch; the per-sample radius is still what is tested.

`root_volume` accumulates π·r²·length over **all** roots, fine ones included: it is a biomass
channel, and fine roots carry biomass.

## The 19 input channels

A superset, so the baseline and the hybrid model train on the **same** scenes — without that,
comparing their Dice says nothing. Each reads its own list by name from the descriptor
(`baseline_channel_names`, `hybrid_channel_names`); the `.npz` also carries `channel_names`.

- The 15 of the baseline: `penetrometer`, `bulk_density`, `available_water`, `sand_fraction`,
  `clay_fraction`, `water_scale`, `growth_scale`, `pipe_fraction`, `pipe_clearance`,
  `backfill_fraction`, `surround_fraction`, `leak_plume`, `pit_mask`, `depth`, `prior`.
- The 4 the hybrid model adds (`../hybrid/channels.py`): `bengough`, and the gradient of
  `water_scale` along depth (positive downward), row and column, per metre and in physical steps.
- The hybrid model's 17 = these 19 minus `depth` (constant) and `growth_scale` (the generator's
  recipe `bengough × water_scale`, which no other data source will reproduce).

`prior_v2` (`../hybrid/prior.py`) is stored beside the inputs, never among them: it is the
phase-B logit offset, `prior × f_se × (1 − pipe_fraction) × (1 + B · leak_plume)`.

Compared with v1: the pavement mask is gone (there is no surface slab any more) and the obstacle
distance is gone (it assumed an infinite axis-aligned pipe). The binary pipe mask became a
**fraction** — a 15 cm pipe has a 177 cm² section against 135 cm² for a voxel column, so no voxel
is ever full and a mask could only draw a staircase.

`water_scale` and `growth_scale` are deliberately redundant with the first five channels: they
are the exact fields CPlantBox read, so the network does not have to rediscover the Rosetta →
van Genuchten → Bengough chain to reach the label.

FiLM is 3 species slots + 3 architecture slots + 7 scalars, ending with the utility count.

## Key numbers

| | |
|---|---|
| Scenes | `SCENE_COUNT = 2000` |
| Runs per scene | `MONTE_CARLO_RUNS = 20` |
| Master seed | 20260922 |
| Sampling along a segment | 1 cm |
| Major class | diameter ≥ `MAJOR_DIAMETER_CM = 2.0` |
| VTP written | the first run only, and only with `--vtp` or `--pilot` |
| Cost of v2 | 98 s per scene on average (64 s soil, 34 s growth), 2 h 12 for the 2000 scenes on 23 workers |
| Cost of v3 | 35 s per scene (median, soil 21 s), about 1 h 15 of computing for the 2000 scenes on 23 workers |
| Size of v3 | 4.2 GB of `.npz`, 15.6 GB of `.vti` (14 uncompressed float32 fields per scene) |
| v3 sanity | 0 intrusion, 0 stillborn tree, 527 uniform soils (26 %), *major* = 29 % of the target mass |

## Choices and limits

- **One folder per tree.** `build_dataset_v3.py` writes `<dataset>/<xml stem>/`, with a `design.json`
  holding the settings, the XML name and its fingerprint; a re-run with other settings or a modified
  XML is refused. The descriptor also stores `versions.xml` and `versions.xml_sha256`. The
  `request_id` of the site request starts with the name of this folder, not with the dataset name.
- **`is_complete()` tests the `.json`, not the `.npz`.** v1 tested the archive, so an archive
  truncated by an interruption looked finished. Both the `.npz` and the `.json` are now written
  to a temporary file and renamed.
- **The descriptor is a mirror of the dataclass.** Everything drawn appears in the `.json`
  because it appears in `SceneConfiguration`, with no separate list to keep in sync.
- **`build_final_radii` is the cheap door.** It computes only what the fusion consumes; the pipe
  model and da Vinci models are extra full traversals and are only computed by the
  `apply_secondary_growth.py` CLI, which writes them as calibration witnesses.
- **Intrusions are reported, not asserted.** `diagnostics["intrusions"]` carries the penetration
  depth per pipe; a graze and a three-centimetre push are different bugs.
- **The scene varies here, not in the sandbox.** `sandbox/sandbox_v3.py` deliberately freezes the
  pit and the street so a difference between two runs can only come from the soil.
- **The site request describes what a user would enter, not the voxels.** Horizons before the
  spatial noise, θ rebuilt from the water fraction with each horizon's own Rosetta curve, points
  permuted from the generator's (x, y, z) to the contract's `[row, column, z]`. The fills and the
  plumes are left for the channel builder to rebuild; the leaks are written explicitly.
