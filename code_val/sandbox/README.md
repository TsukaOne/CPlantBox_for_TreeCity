# sandbox — experiments that measure one mechanism at a time

## What is here

| File | Role |
|---|---|
| `sandbox_v3.py` | v3 sandbox: one scene of the dataset generator at a time (network/ streets, secondary growth, diameter classes) |
| `root_metrics.py` | root measures shared by the sandboxes: shape, length per band, occupancy shape |
| `sandbox_v2.py` | test sandbox v2 (axis-aligned street prototype of `obstacles/`) |
| `sandbox_v1.py` | frozen reference to v1, imported by `sandbox_v2.py --v1` |
| `sandbox_hydro_test.py` | Test hydrotropism steers roots towards water |

## `sandbox_v2.py` — Run code

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" -w /workspaces/CPlantBox_for_TreeCity cplantbox-image
```
```bash
python3 code_val/sandbox/sandbox_v2.py --tree my_Picea_abies.xml
```
| Flag | Effect |
|---|---|
| `--tree XML ...` | **required**: CPlantBox parameter files (`parameters/` folder), one sub-folder of output per file |
| *(none)* | current soil pipeline, `f_se` only |
| `--f-sa` | also wire `f_sa`, the lateral insertion angle scale |
| `--hydro` | also wire hydrotropism on the interpolated water field |
| `--v1` | build the soil with the frozen v1 pipeline instead, same scenes |
| `--no-street` | scene without networks and leaks, to isolate the effect of the tropisms |
| `--output` | where to write; default `sandbox_v2[_fsa][_hydro]/` next to the script |

### Step by step, per archetype

1. Draw a soil profile from `default_rng([SEED, archetype_id])`.
2. Draw the street from `default_rng(SEED)` — **seeded without the archetype on purpose**, so
   every soil meets exactly the same pipes, trenches, pit and leaks. A difference between two
   scenes can then only come from the soil. Scene variation belongs to the dataset generator, not
   here.
3. Build the soil (v2 or v1 path), the fills, the leaks, then ψ and `f_se`.
4. Grow 50 seeds at 120 years, voxelise each, average.
5. Print three lines: the mean of each soil factor; segments, depth, support, mass, mean radius
   and mean depth of the occupancy; then the leaking networks and any intrusion.
6. Write `<archetype>.npy` (the probability grid), `<archetype>.vti` (all the fields) and
   `<archetype>.vtp` (the first root system).

Note that this script uses the **axis-aligned** street prototype in
[`obstacles/`](../obstacles/README.md), not `network/`.

## `sandbox_v3.py` — one scene of the v3 generator

Same scene model as the dataset, built by hand so that one thing varies at a time: one soil
archetype (a single patch), one street, the age and the seeds of your choice.

```bash
python3 code_val/sandbox/sandbox_v3.py --tree my_Quercus_robur_T4.xml --runs 3 --no-street
```

| Flag | Effect |
|---|---|
| `--tree XML ...` | **required**: CPlantBox parameter files |
| `--archetype N ...` | soil archetype identifiers, 1 = `loose_uniform` ... 10 = `sand_over_clay` (default 1) |
| `--no-street` | no network and no leak |
| `--street-class` | density class of the street, ignored with `--no-street` (default `dense`) |
| `--no-f-sa`, `--no-hydro` | do not wire `f_sa` / the hydrotropism (the dataset wires both) |
| `--npz` | also write the files of the dataset into `npz/` (`.npz`, `.json`, `site_request`, no `.vti`) |
| `--runs`, `--age`, `--seed` | trees per scene (50), age in years (120), base seed (7) |
| `--output` | output folder, default `sandbox_v3[_nofsa][_nohydro][_nostreet]/` next to the script |

Per XML file it writes `<output>/<xml stem>/`: the first three `.vtp`, one `.vti` (the fields and the
occupancy), `_roots.csv` (one row per structural root of at least 100 cm) and `_profile.csv`
(structural length per subtype, depth band and radius band). The pit and the street are seeded
without the archetype and without the tree, so every soil and every XML meets the same pit and
the same pipes. A street of the requested class is searched from the seed upwards, over at most
200 seeds.

## `sandbox_v1.py` — the frozen reference

The v1 soil pipeline, kept only so it can be compared with the current one. Three differences,
in the order the soil is built:

1. noise drawn independently per channel, so a voxel could be dense, wet and weak at once;
2. Rosetta called once per horizon instead of once per voxel, so textural noise never reached the
   retention parameters — only the moisture did;
3. the mechanical factor floored at 0.05 instead of being allowed to reach zero.

It now carries its own helpers so it no longer follows changes in `soil/field.py`. **Do not
"fix" it**: its value is that it does not move.

## `sandbox_hydro_test.py` — does the tropism work?

Puts two saturated pockets in the domain (one shallow at 45 cm, one at 135 cm, on opposite
bearings), grows 24 seeds with and without the water lookup, and compares the occupancy inside
each pocket against a control shell around it at the same depth and the same distance from the
trunk.

The statistic is a **pooled rate ratio with a bootstrap over seeds**. Averaging one ratio per
seed would be biased both ways: a seed that misses the pocket contributes a hard zero, and a seed
that grazes it contributes an unbounded number.

Archetypes 5 (`sandy_dry`, where water is limiting) and 2 (`medium_uniform`, where it is not) are
run deliberately: if the effect only shows on the first, the mechanism is working as intended.

**This script is currently broken**: it imports `draw_obstacle_layouts` from `obstacles.layouts`,
which exports `draw_obstacle_layout` (singular). One-character fix when it is next needed.

## Measured here

With `sandbox_v2.py`, 120 years, 10 seeds, the simplified street against the same scene with the
networks removed:

| archetype | mass | mean radius | support |
|---|---|---|---|
| loose_uniform | −36.2 % | −24.4 % | −40.1 % |
| medium_uniform | −75.1 % | −52.0 % | −78.6 % |

The full street cut, with surface roadway, gave −44.6 % and −73.0 % on the mass: removing surface
roadway cost the signal almost nothing, because the trenches now reach the surface. v1's obstacle
families gave +4.6 %, the wrong sign.

Zero intrusions were found over 10 seeds × 2 archetypes × 4 modes (default, `--f-sa`, `--hydro`,
`--v1`) in the six lumens.

## Limits

- **50 runs at 120 years is slow** — the whole point is that it is one scene at a time, run by
  hand, not a dataset.
- **Segment counts are blind to `f_sa`** by construction: a scaled insertion angle moves roots
  around without changing how much length is grown. Look at the mean radius and mean depth of the
  occupancy instead.
- **The output directories are not cleaned.** Two runs with the same flags overwrite each other;
  different flags land in different folders.

## v4 sandbox — the soil library on a frozen v3 scene

The tree (58 years), pit (82 × 89 cm), five networks, leak and 20 root seeds of v3 scene 1001 stay
fixed; only the soil, the walls and the water state change. The profile stands alone (no mosaic),
the pit is loose and drawn once, the year is normal. Same secondary growth and radius voxelisation
as the v3 generator (`generator.build.grow_ensemble`), plus a wall intrusion check.

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity/code_val/sandbox cplantbox-image \
    bash -c "python3 sandbox_v4_profiles.py; python3 sandbox_v4_seasons.py; python3 sandbox_v4_walls.py"
```

| File | Experiment | Time (23 workers) |
|---|---|---|
| `sandbox_v4_scene.py` | the frozen scene, the soil it receives, what is measured | — |
| `sandbox_v4_profiles.py` | E1: 12 profiles × 3 cities × stop at 2.5 / 3.0 MPa; `output/sandbox_v4/profiles.csv` | 97 s |
| `sandbox_v4_seasons.py` | E2: mean state against a four-season cycle, P01/P03/P05/P08/P12 × Brussels/Helsinki | 40 s |
| `sandbox_v4_walls.py` | E3: foundation, narrow strip, confined pit on P01/P05/P08 in Brussels | 17 s |

Each configuration writes a `.vti` (occupancy, f_se, resistance, rootable, walls, pipes) and the
`.vtp` of run 1 under `output/sandbox_v4/`.

### What was measured

E1 ran before the native subsoils of P03, P04, P06, P09–P12 were set to IN (only P01 was);
those profiles are a little more favourable now than in these numbers.

- **No tree is stillborn, no root enters a pipe or a wall** in any of the 72 + 50 + 12 ensembles.
- **Profiles order as expected.** Root mass (mean occupancy) at 2.5 MPa: engineered substrates
  P11/P12 0.0034–0.0040, deep natural soil P01 0.0034–0.0038, compacted P05 0.0025, thin soil
  P02 0.0022–0.0026, sealed P08 0.0020–0.0023. The v3 soil of the same scene gave 0.0013.
- **Mechanical impedance limits almost everywhere**; water never in the mean state; air in P03
  (61–82 % of the limited voxels, roots stop at the water table); the barrier in P02 (82 %).
- **The stop threshold is a first-order parameter**: 3.0 instead of 2.5 MPa raises the mass by
  20 to 55 % and the occupancy-weighted radius by 20 to 35 cm, in every profile.
- **Seasons do not change the result.** Overlap of the cycle with the mean state 0.77–0.86, above
  the noise floor of the mean state with other seeds (0.73–0.83, the cycle shares its seeds);
  mass within ±11 %, mean depth within ±1.5 cm. A stopped winter costs 15 to 31 % of the mass
  and 9 to 32 cm of radius at 58 years; growing 4/3 faster the rest of the year recovers most of
  it (mass 0.84–0.97).
- **Walls.** A confined pit keeps 9 to 12 % of the mass outside its ring instead of 36 to 49 %, and
  the roots dive under its 59 cm walls (maximum depth +12 to +20 cm). A narrow-strip facade cuts
  the 4 to 8 % of the mass that grew behind it. The foundation, 240 to 450 cm away, is out of
  reach of this 58-year-old tree.
- **Barriers leak by one growth step.** 0.1 to 3 % of the centreline samples end in a fully
  non-rootable cell (rock, slab, asphalt): a tip slides one `dx` (up to 3 cm) into the cell before
  the nearest-cell lookup stops it.
