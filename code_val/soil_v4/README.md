# soil_v4 — the soil physics of the v4 generator

From drawn profiles (`soil_library/`) to what CPlantBox reads: the elongation scale `f_se` and the
lateral angle scale `f_sa`. The penetration resistance is **derived**, never typed in, and the
water comes from the city, never from the texture.

## Who does what

| File | Responsibility |
|---|---|
| `column.py` | `StaticSoil` and `build_column`: a profile laid on the 9 cm depth cells; barriers become `rootable_fraction` |
| `mosaic.py` | one to four profiles side by side, on v3's patch geometry (`build_patch_weights` reads it unchanged) |
| `field.py` | the 3-D static soil: patch columns blended by weight, then compaction (3 %) and texture (8 %) noise |
| `pit.py` | the planting pit, loose or compacted, cut through surface barriers, stopped by deep ones |
| `fills.py` | network backfills as v4 materials, blended by volume fraction in v3's priority order |
| `retention.py` | one Rosetta 3 call per scene, density capped at 2.0 g/cm³ for Rosetta only |
| `water.py` | `WaterRegime` (four seasons from the city, year, drought, sealing, runoff, water table) and leaks |
| `resistance.py` | Whalley et al. (2007): resistance from suction × saturation and density |
| `aeration.py` | air-filled porosity 1 − ρ/2.65 − θ (none when saturated), ramp from 5 % to 12 % air |
| `factors.py` | mechanical ramp with an open stop threshold, `f_se` = product of the factors × rootable, `f_sa` |
| `state.py` | `compute_soil_state`: everything that follows from one water state |
| `scene.py` | `SoilScene` (what is drawn) → `SceneSoil` (static fields, walls, one Rosetta call) → one state per water state |
| `check_references.py` | the physics against published values |

## Run

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image bash -c "
    python3 code_val/soil_v4/check_references.py
    python3 code_val/visualisation/soil_states.py
    python3 code_val/visualisation/soil_scene.py 1001 --profile P08 --city Helsinki --walls foundation
    python3 code_val/visualisation/soil_section.py output/soil_v4/scene_01001_P08_helsinki_foundation.vti"
```

- `soil_states.py`: `output/soil_v4/soil_states_<city>.png`, resistance, air and `f_se` down the
  profiles of `soil_columns.png`, for each season, the mean state and a 3.0 MPa stop.
- `soil_scene.py <id>`: the v4 soil of v3 scene `<id>` (same tree, pit size, networks, leaks) as a
  `.vti` for ParaView, plus a summary of what limits growth. `--profile`, `--city`, `--pit` and
  `--walls` fix what is otherwise drawn from the scene identifier.
- `soil_section.py <vti>`: a PNG section through the trunk, across the street, of that `.vti`.

## Order of a scene

1. Static soil: profile columns, blended by patch weights, noised.
2. Planting pit, then network backfills (a trench crosses the pit like any soil), then walls
   (`network/wall_layouts.py`): the share of a voxel a wall fills is no longer rootable.
3. Rosetta once on the result.
4. Per water state: city season × year × sealing (outside the pit), runoff into the pit, leaks,
   water table; then θ, ψ, resistance, air and the factors.

## Key numbers

| Check | Computed | Published |
|---|---|---|
| WRB IN/FR and FR/VR boundaries, 20 % clay loam | 1.62 / 1.82 g/cm³ | NRCS silt loam: 1.65 affects, 1.80 restricts |
| Loam at −10 kPa, LO / IN / FR | 0.67 / 1.02 / 1.57 MPa | Bengough 2011: ~90 % of field readings < 2 MPa |
| Loam at the wilting point, LO / IN / FR | 2.6 / 4.2 / 5.0 MPa | — (outside Whalley's −20…−300 kPa) |
| Structural soil, available water | 0.104 | CU-Soil 0.07–0.11 |
| Structural soil, whole-soil density | 2.07 g/cm³ | CU-Soil 1.87–2.04 |
| Saturated loam | air 0, `f_se` 0 | — |
| Mechanical ramp at 2.5 MPa vs v3 Bengough | identical | — |
| 3-D soil of one scene, mean and summer states | 6–8 s | v3: 21–28 s |

## Known limits

- **Whalley's coefficients are second-hand** and still to be checked against the paper. Dry
  states (|ψ| above 300 kPa) are extrapolated.
- **Air from θs was wrong** and was dropped: Rosetta's θs sits close to a loam's field capacity
  and left a loose loam with about 3 % air, which choked every fine soil in wet seasons.
- Structural soil comes out 0.03 g/cm³ too dense: the model fills every stone void with fine
  earth, while CU-Soil keeps open macro-voids.
- Stones act only through the fine-earth density and the whole-soil water.
- The pit and the backfills are engineered: they carry no deviation from the resistance
  pedotransfer, and a trench excavated through rock is rootable backfill.
- The pit bottom follows the profile that dominates each column; the v3 trench-under-pit shape
  still uses the nominal pit depth.
- Water carries no spatial noise of its own: within a state it varies through sealing, the pit,
  leaks and the water table, and θ through each cell's retention curve.
- The water table does not move with the seasons and has no capillary fringe.
- A frozen winter is not applied here: whether it stops growth is the seasons pilot's question.
