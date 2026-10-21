# network — the buried utilities around the tree (v2)

A street's networks and how they are laid, in any orientation: a run is a polyline, not an axis.
Surface roadway is **not** modelled — what reaches the roots is the excavation, not the slab laid
on top of it. `curb_offset_cm` survives as a plain coordinate: the line the parallel corridors
are offset from, which is what keeps telecom, lighting, electricity, gas, heating and water on
one side and the sewer on the other.

This package replaces the axis-aligned prototype still living in
[`obstacles/`](../obstacles/README.md), which the v1 path and `sandbox_v2.py` still use.

## Three mechanisms, not to be confused

| Mechanism | What it is | What it touches |
|---|---|---|
| **Wall** | absolute ban, `SDF_Difference` | pipe lumens, and nothing else |
| **Penalty** | *fractional* overwrite of the 5 soil channels | trench backfill, sand surround, loose backfill under the pit |
| **Attraction** | θ → ψ → `setSoil()` + `tropismT = 3` | the leak plume, water and sewer only |

## Step by step

1. **`street.py::draw_street_scene` — lay a street.**
   One street bearing for the whole scene (35 % chance of an oblique street) — that is what makes
   it a street rather than a heap of pipes. A density class draws how many networks are present
   (0 to 10), then `select_templates` picks them by weight without replacement. A *connection* is
   only eligible once its parent network is there, and it ends on the parent's polyline, which is
   what produces the tees. 25 % of corridors get an elbow. `place_run` guarantees **no two lumens
   ever touch**: a run that clashes is pushed deeper (up to 40 cm), otherwise it is dropped.
2. **`leaks.py::build_scene_leaks` — pick the leaking joint.**
   Only templates with a `joint_spacing_cm` can leak (water 600 cm, sewer 250 cm, and their
   connections). The joint chosen is the one nearest the trunk — a leak outside the scene teaches
   the network nothing. `build_plume_ramp` then draws an ellipsoid, long along the trench and
   short across it, that follows the local tangent of the pipe.
3. **`shapes.py::build_scene_shapes` — solids, in the order the soil must receive them.**
   lumens (reserve their volume, write nothing) → sand surrounds → loose backfill where a trench
   crosses the pit → recompacted trench backfill. Consumed against a decreasing budget in
   `soil/fill.py`, which carves the rings without any shape having to be described as a ring.
4. **`coverage.py::build_coverage` — what fraction of each voxel a solid occupies.**
   Cheap because the signed distance from the cell centre already classifies a cell as fully in
   or fully out once it exceeds the half-diagonal: only the boundary shell is subsampled, so it
   can be subsampled finely. A prism (trench, pit) separates into a plan fraction and a depth
   fraction — the depth one exact, the plan one computed over 64 × 64 columns instead of 139 264
   voxels. An oblique pipe does not separate and pays for a 3D shell.
5. **`walls.py::build_street_geometry` — the CPlantBox domain.**
   The soil box minus every lumen, inflated by `PIPE_EXCLUSION_MARGIN_CM`. A flat
   `SDF_Difference`: nesting a union inside it is the same expression and one more dispatch.
6. **`intrusion.py::find_intrusions` — check afterwards.**
   Against the *physical* radius, not the inflated one, and reporting the penetration depth
   rather than a boolean.

## Who does what

| File | Responsibility |
|---|---|
| `street.py` | the catalogue of networks, the laying rules, and the draw |
| `primitives.py` | **the single geometric source of truth**: pipe capsules, trench and pit prisms, and the distances that define them |
| `coverage.py` | the fraction of each voxel a solid occupies, plus the ParaView label field |
| `walls.py` | the CPlantBox `SignedDistanceFunction` |
| `leaks.py` | the leaking joint and its anisotropic plume |
| `shapes.py` | the scene translated into solids, in fill priority order |
| `intrusion.py` | the after-the-fact check that no root entered a lumen |

The soil side is elsewhere: `soil/fill.py` applies the materials, `soil/leak.py` injects the
moisture and softens the resistance accordingly.

## How the geometry is built, since it is not obvious

- **A pipe is a flat-ended capsule** between two points. Its signed distance restates
  `SDF_PlantContainer::getDist` in world coordinates, so numpy and CPlantBox can be compared to
  the centimetre and not only by sign.
- **An arbitrary segment needs no C++ change.** `SDF_PlantContainer` is a finite cylinder along
  +z; two nested `SDF_RotateTranslate` tilt it and then aim it. `getDist` applies `rot(-angle)`
  to the point, so the object turns by `+angle` and the local origin lands on `pos`.
- **An elbow closes** because each segment of a run overruns its node by one radius
  (`ELBOW_OVERLAP_RADII`), which covers any turn up to 90°. On the wall the overrun follows the
  *inflated* radius, otherwise the notch reopens at the margin.
- **Only `walls.py` inflates a pipe.** The fractional coverages and the intrusion check both read
  the physical radius.

## Key numbers

| | |
|---|---|
| Templates | 9: lighting, telecom, electricity, gas, water, heating, sewer, water connection, sewer connection — plus an optional pit service (30 %) |
| Networks present | 0 to 10, by density class (bare / residential / dense / city centre) |
| Minimum lumen clearance | 10 cm, enforced by deepening up to 40 cm, else the run is dropped |
| Trench working space | radius + 30 cm on each side |
| Exclusion margin | 4 cm, which must exceed the largest `dx` in the XML (3.0 cm) — asserted at startup |
| Leak statuses | none / minor / major at 0.34 / 0.33 / 0.33, on jointed networks only |
| Plume reach | 150 cm along the trench, 60 cm across, 120 cm down, 50 cm up (× 0.6 for a minor leak) |
| Coverage subsampling | 32 × 32 per column in plan, 5 × 8 × 8 in the 3D shell |

## Choices and limits

- **The plume reach is a budget, not a free parameter.** Bias per growth step times reach is
  roughly constant at 5.9 in this model, so a wider plume is a weaker one. 60 cm across the trench
  puts the pull at about half the gravitropic dive, which is the whole point.
- **The wall is a strong preference, not a guarantee.** CPlantBox confines by rejection and gives
  up after about twenty tries, taking the least bad direction. The real hole is elsewhere:
  `Organ::createSegments` slides the tip forward by one `dx` along its heading without testing the
  geometry, which is why the margin is compared against `dx` and not against the sagitta of a
  growth step.
- **Intrusion is tested at nodes only.** A segment is at most one `dx` = 3 cm, and the thinnest
  lumen is 9 cm across: a 3 cm chord in a 4.5 cm circle bites 2.6 mm, far inside a 4 cm margin.
- **A leak cannot soften its own backfill.** `apply_moisture_to_resistance` raises the scale to
  the power of `natural_share`, which is zero inside a fully engineered fill.
- **Roughly one scene in 25 has no leak at all**: only jointed templates can leak, and each draws
  `none` with p = 0.34.
- **`f_se` stays at the ambient level inside a lumen**, by choice, so the trilinear interpolation
  the hydrotropism reads is not biased near the wall and a sound pipe neither attracts nor repels.
  No root gets in, so growth is unaffected, but it is visible in ParaView — the `tuyaux` field is
  there to spot it. Open decision: leave it ambient, force `f_se = 0`, or make it a mask channel
  only.
- **No root intrusion is produced** (Team 3's `rootIntrusion` and `overlapVolume` stay at 0): the
  SDF is not punctured at the leak point. What is produced is clustering against the pipe.
- Signal measurements for the street as an obstacle were taken on the axis-aligned prototype;
  see [sandbox/README.md](../sandbox/README.md). They have not been re-measured on this package.

## Wall module (v4)

Vertical barriers no root crosses, drawn per scene for the v4 generator. Nothing above changes:
`build_street_geometry` is still the v3 domain; `build_scene_geometry` is the v4 one.

| File | Responsibility |
|---|---|
| `wall_layouts.py` | the three kinds and their dimensions: a building foundation, a narrow strip (facade + kerb), a confined pit (square ring around the pit) |
| `wall_panels.py` | a panel in the street frame, and where it can stand: moved away from the trunk, then made shallower, then dropped |
| `wall_measures.py` | signed 3-D distance to a wall, room left to a corridor, voxel fraction |
| `wall_geometry.py` | the CPlantBox solids (a box per segment, a cylinder per node, inflated 4 cm sideways and downwards) and `build_scene_geometry` |
| `check_wall_geometry.py` | CPlantBox against numpy on points around each wall |

A wall is a `TrenchSlab`, so its coverage is the exact prism coverage of `coverage.py`. Only
corridors are checked for clearance: connections and pit services may cross a wall, as they do
through a real foundation.

| Kind (probability) | Placed | Shifted | Shallower | Dropped | Median depth |
|---|---|---|---|---|---|
| foundation (0.20) | 74 % | 5 % | 18 % | 2 % | 213 cm |
| narrow strip (0.10) | 61 % | 22 % | 14 % | 3 % | 65 cm |
| confined pit (0.15) | 32 % | — | 60 % | 8 % | 61 cm |

Over the first 200 v3 scenes, 5 to 13 ms per scene. `check_wall_geometry.py` on scene 1001:
sign agreement 99.8 to 100 %, largest gap 2.2 cm within 5 cm of a face. The rest is the bottom
edge, square in CPlantBox and rounded in numpy, which makes CPlantBox exclude slightly more.

Every wall dimension and probability is an estimate. A confined pit is often made shallower:
sidewalk corridors pass close to the trunk, and in v3 they even cross the pit.
