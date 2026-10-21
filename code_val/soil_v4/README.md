# soil_v4 — the soil physics of the v4 generator

From a drawn profile (`soil_library/`) to what CPlantBox reads: the elongation scale `f_se` and the
lateral angle scale `f_sa`. The penetration resistance is **derived**, never typed in, and the
water comes from the city, never from the texture.

Step 3 covers one column (1-D). The 3-D field, the planting pit, the backfills and the leaks come
next.

## Who does what

| File | Responsibility |
|---|---|
| `column.py` | `StaticSoil` and `build_column`: a profile laid on the 9 cm depth cells; barriers become `rootable_fraction` |
| `retention.py` | one Rosetta 3 call per scene, density capped at 2.0 g/cm³ for Rosetta only |
| `water.py` | `WaterRegime`: four seasons from the city, dry/normal/wet year, drought, sealing, runoff, water table |
| `resistance.py` | Whalley et al. (2007): resistance from suction × saturation and density |
| `aeration.py` | air-filled porosity 1 − ρ/2.65 − θ (none when saturated), ramp from 5 % to 12 % air |
| `factors.py` | mechanical ramp with an open stop threshold, `f_se` = product of the factors × rootable, `f_sa` |
| `state.py` | `compute_soil_state`: everything that follows from one water state |
| `check_references.py` | the physics against published values |

## Run

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image \
    bash -c "python3 code_val/soil_v4/check_references.py && python3 code_val/visualisation/soil_states.py"
```

`soil_states.py` writes `output/soil_v4/soil_states_<city>.png`: resistance, air and `f_se` down the
profiles of `soil_columns.png`, for each season, the mean state, and a 3.0 MPa stop threshold.

## Order of a water state

1. θ from the available water fraction on the cell's own retention curve; θs where saturated.
2. ψ read back off the same curve; S = θ / θs.
3. Resistance: log10 Q[kPa] = 1.26 + 0.35 log10(|ψ|[kPa] S) + 0.93 ρ, plus a per-layer
   deviation (log10 sd 0.1), capped at 5 MPa; 5 MPa in a full barrier cell.
4. Air from the particle-density porosity.
5. `f_se` = Bengough(0.5 → stop) × water stress (v3, threshold 0.40) × aeration × rootable.

## Key numbers (`check_references.py`)

| Check | Computed | Published |
|---|---|---|
| WRB IN/FR and FR/VR boundaries, 20 % clay loam | 1.62 / 1.82 g/cm³ | NRCS silt loam: 1.65 affects, 1.80 restricts |
| Loam at −10 kPa, LO / IN / FR | 0.67 / 1.02 / 1.57 MPa | Bengough 2011: ~90 % of field readings < 2 MPa |
| Loam at the wilting point, LO / IN / FR | 2.6 / 4.2 / 5.0 MPa | — (outside Whalley's −20…−300 kPa) |
| Structural soil, available water | 0.104 | CU-Soil 0.07–0.11 |
| Structural soil, whole-soil density | 2.07 g/cm³ | CU-Soil 1.87–2.04 |
| Saturated loam | air 0, `f_se` 0 | — |
| Mechanical ramp at 2.5 MPa vs v3 Bengough | identical | — |

## Known limits

- **Whalley's coefficients are second-hand** and still to be checked against the paper. Dry
  states (|ψ| above 300 kPa) are extrapolated.
- **Air from θs was wrong** and was dropped: Rosetta's θs sits close to a loam's field capacity
  and left a loose loam with about 3 % air, which choked every fine soil in wet seasons.
- Structural soil comes out 0.03 g/cm³ too dense: the model fills every stone void with fine
  earth, while CU-Soil keeps open macro-voids.
- Stones act only through the fine-earth density and the whole-soil water; a stone has no direct
  effect on growth.
- The water table does not move with the seasons and has no capillary fringe.
- A frozen winter is not applied here: whether it stops growth is the seasons pilot's question.
