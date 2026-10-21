# soil_library — the urban soil catalogue (v4)

What an urban soil can be made of, for the v4 generator. The design is in
`documentation_TreeCity/bibliotheque_sols_urbains.md`. This package only holds the catalogue and
the draw of one concrete profile; the physics (Rosetta, water, penetration resistance, growth
factors) comes in `soil_v4/`.

The network learns from physical quantities, never from these names: identifiers are kept only to
trace each scene and to build the test sets.

## Who does what

| File | Responsibility |
|---|---|
| `values.py` | `ValueRange` (5th–95th percentile) with its `Source`; the urban_soil value format without pydantic, plus an `ESTIMATE` provenance |
| `sources.py` | every reference cited, and for each estimate the data meant to replace it |
| `compaction.py` | WRB packing density classes VL…VR and the fine-earth bulk density each one allows |
| `materials.py` | the twelve materials M01–M12, as fine-earth texture, organic carbon and coarse fragments |
| `barriers.py` | layers no root crosses; a pit is dug through a surface barrier, never a deep one |
| `profiles.py` | the twelve profile types P01–P12, as stacks of layer recipes |
| `cities.py` | Tallinn, Brussels, Helsinki: natural materials, the barrier under a thin soil, seasonal water |
| `draw.py` | `draw_profile(recipe, city, rng)` → `DrawnProfile`, a list of concrete layers |

## Run

```bash
docker run --rm -v "C:\Users\ValentinMarchand\Dev\CPlantBox_for_TreeCity:/workspaces/CPlantBox_for_TreeCity" \
    -w /workspaces/CPlantBox_for_TreeCity cplantbox-image \
    bash -c "python3 code_val/visualisation/soil_columns.py"
```

Writes `output/soil_v4/soil_columns.png`: one drawn profile per type and city.

## How a profile is drawn

1. The city picks its natural material (Brussels: loam 70 %, sand 30 %; Helsinki: clay 60 %,
   till 40 %; Tallinn: sand 50 %, till 50 %).
2. Each layer recipe picks one of its components, then a thickness in its range. The last layer
   runs to the bottom of the box (`bottom_cm = None`).
3. A material drawn twice in one profile keeps one texture (same parent material); organic carbon,
   coarse fragments and compaction class are drawn per layer.
4. The compaction class gives the density: WRB 2022 boundaries T − 0.009 × clay %, with
   T = 1.4 / 1.6 / 1.8 / 2.0, lowered by 0.03 per 0.5 % of organic carbon above 1 %. VL and VR
   are 0.2 g/cm³ wide.

## Where the values come from

Of the 76 ranges in the library, **13 come from a reference** (SoilGrids, Nehls 2013,
Grabosky 2009, FAWB 2015, FLL and tree sand product sheets, the design document), **1 is derived**
(the stone fraction of structural soil, from Grabosky's mass ratio and density) and **62 are
estimates**. Every estimate names its replacement in `sources.py`:

| Data to collect | Estimates it replaces |
|---|---|
| SoilGrids 2.0 at natural points near the cities | 14: textures, organic carbon and stones of M02–M04, stones of M01, natural material shares of the three cities |
| GTK and Estonian geological maps | 1: stones of the till (M04) |
| Planting specifications (Brussels CCT 2015) | 4: all of the imported topsoil (M05) |
| Measured urban fills (Brussels soil health survey, NRCS New York) | 3: fine earth of the rubble fill (M06) |
| Product sheets and standards | 16: what the sheets did not give for M07–M12 |
| Field descriptions of the urban scenarios | 20: layer thicknesses of the profiles |
| Groundwater depth maps | 1: water table of P03 |
| 1-D water balance on ERA5-Land | 3: seasonal water of the three cities |

The WRB class boundaries themselves are a reference, not an estimate.

## Key numbers (500 draws per profile and city, 18 000 profiles)

| Class | Density range g/cm³ | Median |
|---|---|---|
| VL | 0.75 – 1.40 | 1.06 |
| LO | 0.96 – 1.59 | 1.31 |
| IN | 1.13 – 1.78 | 1.52 |
| FR | 1.37 – 1.99 | 1.77 |
| VR | 1.57 – 2.18 | 2.03 |

No stacking gap, no texture above 100 %, every density inside its class. **62 % of VR layers
exceed 2.0 g/cm³**, where Rosetta stops being valid.

## Known limits

- **The native soil under a profile is undisturbed (IN)** — SoilGrids gives 1.56–1.58 g/cm³ at
  depth in Brussels — except in P05, P07 and P08, where compaction is the subject. Decided at
  the sandbox checkpoint: a FR subsoil (1.5–3.7 MPa) stopped the roots of most profiles.
- P03 has a groundwater table only; the perched water table over a compacted layer is not a
  separate variant.
- P07 alternates fine / coarse / fine over the natural soil in a fixed order.
- Compaction classes are drawn uniformly among those a recipe allows; profile and city weights
  are uniform too (open decision).
