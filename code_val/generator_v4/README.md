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

`--tree` is required, one or more files of `parameters/`, one folder per tree. `--pilot` writes
identifiers 1–128 (eight blocks, the first scenes of the dataset) to `pilot_v4/<xml>/`; without it,
`--scenes 2000` to `dataset_v4/<xml>/`. Resumable, refuses a design change or a modified XML in a
directory.

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
- **A wall is a strong preference, not a guarantee** (accepted). CPlantBox confines by rejection
  and gives up after about twenty tries; in the pilot, 4 confined pits out of 22 had a root
  node 0.3 to 10.5 cm inside their wall, which surrounds the densest roots. Every intrusion is
  recorded in the scene's diagnostics.
- The full dataset v4 is not generated yet: it waits for Whalley's coefficients to be checked.
