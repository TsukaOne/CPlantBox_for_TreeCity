# generator_v4 — dataset v4: the v3 scenes with the urban soil library

Scene k of v4 is v3 scene k (same tree, pit size, street, leaks and root seeds, taken from
`generator.scene.draw_scene`) with a v4 soil (`soil_library/`, `soil_v4/`), walls
(`network/wall_*.py`), and roots stopped at 3.0 MPa instead of 2.5. The growth, secondary growth,
voxelisation and file layout are the v3 ones.

## Run

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image \
    bash -c "python3 code_val/build_dataset_v4.py --pilot"
```

`--pilot` writes identifiers 1–128 (eight blocks, the first scenes of the dataset) to `pilot_v4/`;
without it, `--scenes 2000` to `dataset_v4/`. Resumable, refuses a design change in a directory.

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

## Key numbers (first block, 16 scenes, 23 workers)

| | |
|---|---|
| Time per scene | 12–33 s (v3: 31–66 s on the same machine) |
| Whole block | 41 s |
| Intrusions into pipes or walls | none |
| `site_request` v3 valid against the schema | 16/16 |
| Paired with v3 (tree, pit, street, leaks, seeds) | exact |
| Regenerated block identical to the first | 16/16 |
| Rootable voxels whose mean-state suction lies outside Whalley's −20…−300 kPa | 35 % (scene 1) |

## Known limits

- Whalley's coefficients are second-hand; a third of the mean-state voxels extrapolate it.
- The v3 pit sizes (0.5–7 m³) are kept for the pairing, below the 5–60 m³ of the regulations.
- `site_request_v3.schema.json` still carries unset training ranges (`[0, 0]`) on the new fields:
  run `measure_training_ranges.py --schema code_val/site_request_v3.schema.json --dataset <v4>` on
  the host once a v4 dataset exists.
- A wall that finds no room is dropped (`skipped` in the descriptor), so a scene can draw a wall
  kind and have no panel.
