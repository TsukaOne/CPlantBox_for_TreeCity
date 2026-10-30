# generator_v4 — dataset v4: the v3 scenes with the urban soil library

Scene k of v4 is v3 scene k of the same tree XML (same tree, pit size, street, leaks and root
seeds, taken from `generator.scene.draw_scene`) with a v4 soil (`soil_library/`, `soil_v4/`), walls
(`network/wall_*.py`), and roots stopped at 3.0 MPa instead of 2.5. The growth, secondary growth,
voxelisation and file layout are the v3 ones.

## Run

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image \
    bash -c "python3 code_val/build_dataset_v4.py --tree my_Picea_abies.xml --pilot"
```

The full dataset, detached, with a log (`pipefail` keeps the exit status of Python, not of `tee`):

```bash
docker run -d --name dataset_v4 -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image \
    bash -c "set -o pipefail; mkdir -p code_val/dataset_v4 && python3 code_val/build_dataset_v4.py --tree my_Picea_abies.xml my_Quercus_robur.xml my_Aesculus_hippocastanum.xml 2>&1 | tee -a code_val/dataset_v4/build.log"
```

A scene that raises is logged as `FAILED, left unwritten` with its traceback and the run goes on;
the command then exits with an error, and a rerun retries only the missing scenes.

`--tree` is required, one or more files of `parameters/`, one folder per tree. `--pilot` writes
identifiers 1–128 (eight blocks, the first scenes of the dataset) to `pilot_v4/<xml>/`; without it,
`--scenes 2000` to `dataset_v4/<xml>/`. Resumable, refuses a design change, a modified XML or
other growth options in a directory. `--identifiers 28 37 90` builds only those scenes of the
design (here three confined pits of the pilot); a later full run completes it. The ParaView `.vti` (85 % of a scene on disk, about 11 MB) is
written by the pilot or with `--vti` only; the training channels are all in the `.npz`.

## Who does what

| File | Responsibility |
|---|---|
| `design.py` | blocks of 16: P01–P12 once each in a shuffled order, then 4 fill scenes (25 %); city turns with the block; pit variant alternates |
| `fill_space.py` | fill scenes on a scrambled Sobol sequence: 2–4 soil layers, texture, organic carbon, stones, density anywhere from VL to VR, water factor, water table |
| `scene.py` | `SceneConfigurationV4`: the paired v3 scene plus soil (streams 6, 7) and walls (stream 9) |
| `environment.py` | the soil in every water state, the walls, the CPlantBox domain and the mean-state lookups |
| `build.py` | one scene: environment, 20 runs with the v3 ensemble, tensors, fields, diagnostics |
| `tensors.py` | channel schema v5: the 19 v3 channels, then 7 new ones; FiLM v3 + 3 water values |
| `site_request.py` | each scene redescribed in the contract `site_request_v3.schema.json` |
| `writer.py` | the v3 file layout, with the v4 names, versions and contract |

## Choices (sandbox checkpoint, `sandbox/README.md`)

- **Mean water state**, no frozen winter: a season cycle stayed within the Monte Carlo noise.
- **Stop at 3.0 MPa**: the tree threshold. It raised the root mass by 20 to 55 % in the sandbox,
  so a paired v3/v4 difference mixes the soil and the threshold.
- **Natural subsoils are undisturbed (IN)** except in P05, P07 and P08.
- **Every tree is planted with a root ball** (`soil_v4/pit.py::ROOT_BALL`, since 22 October 2026):
  scene 136 had a compacted FR pit at 3.1 MPa, its collar could not grow, and the empty root
  system stopped the whole run. In such a pit the roots now fill the ball and leave it along the
  trench backfills that cross the pit.
- **No hydrotropism** (`build.py::GROWTH_OPTIONS`, since 22 October 2026). The mean state leaves
  no water gradient (water scale 1 in every rootable voxel of the first 16 pilot scenes), so it
  only replaced the XML tropisms of subtypes 5 and 6 by a dive. `f_sa` stays wired. Pilots built
  before that date grew with it and are refused by `design.json`.
- Profile, city, wall and module weights are uniform priors; everything drawn is in the
  descriptor, so the dataset can be reweighted without being regenerated.

## Channels (schema v5)

| Index | Channel | v4 meaning |
|---|---|---|
| 0–18 | the v3 channels | `penetrometer` = derived resistance of the mean state; `bulk_density` = fine-earth density; the water ones = mean state |
| 19 | `organic_carbon` | percent / 5 |
| 20 | `coarse_fraction` | whole-soil volume share |
| 21 | `rootable` | 1 − share of the voxel under a barrier or a wall |
| 22 | `wall_fraction` | share of the voxel inside a wall |
| 23 | `air_filled_porosity` | mean state |
| 24 | `aeration_scale` | mean state |
| 25 | `saturated_fraction` | share under a water table |

## Key numbers (first block, 16 scenes, 23 workers, `Picea_Abies_combined_v6.xml`)

| | |
|---|---|
| Time per scene | 12–33 s (v3: 31–66 s on the same machine) |
| Whole block | 41 s |
| Intrusions into pipes or walls | none |
| `site_request` v3 valid against the schema | 16/16 |
| Paired with v3 (tree, pit, street, leaks, seeds) | exact |
| Regenerated block identical to the first | 16/16 |
| Rootable voxels whose mean-state suction lies outside Whalley's −20…−300 kPa | 35 % (scene 1) |

## Pilot against v3 (`compare_pilot_v4.py`, scenes 1–128, `Picea_Abies_combined_v6.xml`)

| | |
|---|---|
| Time | 8 min 38 on 23 workers; 77 s per scene median, 199 s max; about 2 h for 2000 scenes |
| Paired with v3 | 128/128; no stillborn tree |
| Root mass v4 / v3 | median ×1.49 [1.19–2.28], higher in 112/128 pairs (sign test p < 0.001) |
| Occupancy-weighted depth / radius | +5 cm / +25 cm |
| Overlap of the v3 and v4 targets | 0.69 |
| Most favourable profiles | P04 ×2.36, P01 ×2.19, P09 ×2.13, P12 ×1.81 |
| Least favourable | P07 ×1.20, P02 ×1.26, P03 ×1.29 (not significant), P05 ×1.43, P08 ×1.49 |
| Confined pit | roots dive (+15 cm) rather than spread (+12 cm of radius, +34 without walls) |

Part of the rise is the stop threshold (3.0 instead of 2.5 MPa: +20 to +55 % in the sandbox);
the rest is v4 soils being on average less compacted than the v3 archetypes. The pit variant
(×1.52 compacted, ×1.46 loose) and the drought module (×1.47 against ×1.49) barely matter: an
IN–FR pit stays penetrable at 3.0 MPa, and in the mean state a drought only shortens the summer.

## Known limits

- Whalley's coefficients are second-hand; a third of the mean-state voxels extrapolate it.
- The v3 pit sizes (0.5–7 m³) are kept for the pairing, below the 5–60 m³ of the regulations.
- `site_request_v3.schema.json` still carries unset training ranges (`[0, 0]`) on the new fields:
  run `measure_training_ranges.py --schema code_val/site_request_v3.schema.json --dataset <v4>` on
  the host once a v4 dataset exists.
- A wall that finds no room is dropped (`skipped` in the descriptor), so a scene can draw a wall
  kind and have no panel.
- **Confined pit walls leaked.** CPlantBox confines by rejection and gives up after about twenty
  tries; behind that, `f_se` was only scaled by the share of the voxel outside the wall, and a
  15–25 cm pit wall seldom fills a 15 cm voxel (median `f_se` 0.10 inside). In the three-tree
  pilot, roots entered the wall in 12/22 (Picea), 5/21 (Quercus) and 8/22 (Aesculus) confined
  pits, up to about 12 cm. Since 22 October 2026 a voxel at least half in a wall is closed
  (`soil_v4/scene.py::CLOSED_WALL_FRACTION`); the wall grows by at most half a voxel on the soil
  side, a root can still enter the open part of a voxel the wall cuts, and an oblique thin wall
  may leave corners open. On the three pilot scenes that leaked most (28, 37, 90, all three trees,
  also without hydrotropism), the deepest intrusion fell from 5–12 cm to 0–7.2 cm, 4 of the 9
  runs with none; the remaining ones stay within the half voxel the fix leaves open. Every
  intrusion is recorded in the scene's diagnostics.
- **The box is too shallow for Quercus and Aesculus** (306 cm): 83/126 oak and 45/127 horse
  chestnut scenes reach 290 cm or more, and their deep roots fall outside the grid.
- **The XML dynamics** (Marius' files): the oak taproot reaches 288 cm by 5–15 years and the oak
  root mass barely follows age (∝ age^0.16); Aesculus and Picea saturate after 40 years; Aesculus
  fine roots never die. Kept as they are for now.
- **Drought acts only through soil hardness.** In the mean state the water-stress factor is below
  1 in about 3 % of the scenes; water acts through the resistance (from the wettest to the driest
  mean state, about ×1.5 in a loam) and the aeration (roots stop under a water table). Carbon,
  fine-root mortality and proliferation in moist soil are not modelled, so the three FiLM water
  values carry little signal and `frozen_winter` none. The dataset tells where roots can go given
  the soil's structure and wetness, not what a drought does to a tree.
- The full dataset v4 is not generated yet: it waits for Whalley's coefficients to be checked.

These are detailed, with their numbers and options, in
`documentation_TreeCity/faiblesses_dataset_v4.md` (6.4, 6.6, 6.8, 6.9, 6.10).
