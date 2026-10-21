# tree — the tree, and the CPlantBox call itself

Two files. One draws what the tree *is*, the other is the only place in the repository that
actually runs CPlantBox.

## Step by step

1. **`attributes.py::draw_tree_attributes`** — draws an age uniformly in [5, 120] years, then
   derives DBH by allometry (with ±15 % spread), height from DBH, and crown depth from height.
   **Only species and age drive CPlantBox**; diameter, height and crown depth exist purely as
   conditioning inputs in the FiLM vector, and should be replaced as soon as real measurements
   arrive.
2. **`growth.py::build_soil_grid` / `build_interpolated_soil_grid`** — push a numpy grid into a
   native CPlantBox lookup. Two flavours, for two different consumers (see below).
3. **`growth.py::assign_soil_hooks`** — attaches `f_se` (and optionally `f_sa`) to every root
   parameter set. The v3 generator always wires both; v2 wired `f_se` only.
4. **`growth.py::assign_hydrotropism`** — `setSoil()` plus `tropismT = 3` on the hydrotropic
   subtypes. Must run **before** `initialize()`.
5. **`growth.py::grow_plant`** — `readParameters` → `setSeed` → `setGeometry` → hooks →
   `initialize(False)` → `simulate(10 days)` in a loop until the tree's age → optional `write()`.
6. **`growth.py::extract_root_system`** — nodes and segment edges to a `(N, 6)` array plus the
   subtype per segment. v2 skips this and reads polylines directly
   (`generator/polylines.py`), because it needs the tree topology for the radii.

## Who does what

| File | Responsibility |
|---|---|
| `attributes.py` | species, age, and the allometries; the species and architecture slots used by both FiLM builders |
| `growth.py` | the soil lookups, the three CPlantBox hooks, the simulation loop, and the segment extraction |

## The traps, all of them in `growth.py`

- **`pad_for_lookup` adds one node per axis.** CPlantBox maps a coordinate onto *n − 1*
  intervals, so a lookup with `n` nodes covers `n − 1` cells; without the extra node the lookup
  cells would not coincide with the voxel grid. Its depth index also runs upward, hence the flip.
  The replicated border makes the field flat outside the domain.
- **`EquidistantGrid3D` for `f_se`, `InterpolatedGrid3D` for water.** The elongation scale is read
  once per apex per step, so nearest-cell is fine and constant-per-cell is honest. A tropism
  samples candidate directions well under a centimetre apart, so it needs a field whose gradient
  is not zero inside a cell — hence trilinear interpolation for the water lookup.
- **Both are native grids, not a Python `SoilLookUp` subclass.** A Python subclass would be called
  back once per apex per time step, dragging the hot loop across the language boundary.
- **`setSoil()` must precede `initialize()`.** The tropism callbacks are built inside
  `initialize()`, out of whatever soil the plant holds at that instant.
- **Feed the hydrotropism the dimensionless water scale, not raw ψ.** CPlantBox blends hydro- and
  gravitropism about 10:1; a ψ running to 1e5 would swamp the gravitropic term instead of
  outweighing it.
- **`f_sa` is left alone on subtype 1.** CPlantBox skips the angle scale when the parent is the
  seed, so wiring it there would be silently dead code.
- **The geometry must stay referenced** for the whole Monte Carlo loop: CPlantBox holds it by
  weak reference, and a freed geometry stops confining roots without any error.

## Key numbers

| | |
|---|---|
| Parameter file | `../parameters/Picea_Abies_combined_v6.xml`, 7 root subtypes |
| Subtypes | 1 juvenile primary axis · 2 structural plate laterals · 3 fine transport roots · 4 structural sinkers · 5 absorbing short roots · 6 exploratory laterals · 7 deep sub-sinkers |
| Structural (target) | 1, 2, 4, 6, 7 — defined in `dataset/occupancy.py`, single source of truth |
| Hydrotropic | 5 and 6, `tropismT = 3`, `tropismS = 0.10` |
| Time step | 10 days |
| Largest `dx` | 3.0 cm |
| Cost | roughly 0.2 s for 60 years and 0.5 s for 120 years, per simulation |

## Choices and limits

- **`tropismT = 3` replaces the subtype's own tropism**, it does not add to it: subtypes 5 and 6
  lose their plagiotropism and become hydro + gravitropic. That is a real change of behaviour on
  subtype 6, which is structural and therefore visible in the target.
- **The soil lookup is constant inside a 15 × 15 × 9 cm cell** for `f_se`. A root crossing a cell
  sees one value for its whole crossing.
- **A blocking soil is not blocking on its border.** `f_se` is read at the apex *before* it
  advances, so a root finishes its last step inside the first cell where `f_se = 0`. Measured on
  dataset v2: 5 % of the target mass sits in cells with `f_se < 1e-3`, 99.9 % of it one cell away
  from growable soil. A hard mask must be eroded by that one cell (`hybrid/masks.py`).
- **Allometries are the specification's, not measurements.** DBH, height and crown depth are
  placeholders.
- **Beyond 60 years the XML is extrapolated.** `simulationTime` is 21 900 days while ages are
  drawn up to 120 years: the growth mathematics stays valid, the parameterisation was never
  calibrated that far.
- **The XML has no botanical source.** It was calibrated on visual plausibility, and its "shallow
  plate, no taproot" stance is in tension with Puhe (2003), *Forest Ecology and Management* 175,
  253–273. Subtype 7 was re-enabled at 0.15 (it had been zeroed to protect pipes, which capped
  rooting at 137 cm of a 306 cm grid); with it, maximum depth reaches 254 cm.

## Seasons (v4)

`seasons.py::grow_plant_through_seasons` grows the same plant as `grow_plant`, but wires the
season's `f_se` and `f_sa` grids on the root parameters every time a 10-day step enters a new
season (spring first, 91.25 days each). CPlantBox reads `f_se` at every `simulate()` and `f_sa`
at the birth of each lateral, through those parameters, so the swap takes effect at the next step.
`growth.py::create_plant` is shared by both growers.

- **The hydrotropism cannot follow the seasons.** It keeps the lookup it got at `initialize()`
  (a weak pointer), so it stays on the mean water state.
- **Never call `plant.copy()` once the grids are wired**: `EquidistantGrid3D::copy` copies raw
  pointers that both copies would free.
- **A lost season is lost, not caught up.** CPlantBox recomputes a root's age from its length
  (`calcAge(length)`), so a root stopped for a season resumes where it stopped.

`check_seasons.py`, scene 1001, 10 seeds:

| | 5 years | 40 years |
|---|---|---|
| Four identical seasons vs `grow_plant` | — | identical segments, 10/10 seeds |
| Winter stopped (`f_se` = 0) | 0.65 of the root length | 0.94 |
| Three seasons stopped | 0.14 | 0.75 |
| All seasons stopped | 0 | 0 |
| Time per plant, `grow_plant` / seasonal | — | 0.07 / 0.09 s |

A dead season costs a young tree a third of its roots, an old one almost nothing: the long roots
end up at their `lmax` either way. The question of recalibrating growth rates for a frozen winter
therefore matters for young trees mostly.
