# secondary_growth — the radius CPlantBox will not give you

CPlantBox draws a root's radius `a` when the root is created and never changes it again. For a
tree of 5 to 120 years that is wrong: the cambium thickens structural roots continuously. This
package **reassigns the radii after the simulation**, per node. Nothing is patched inside
CPlantBox.

Reference specification: `documentation_TreeCity/secondary_root_growth_math.md`.

Two callers:

| Caller | Entry point | What it does |
|---|---|---|
| `generator/build.py` (v2 dataset) | `radii.build_final_radii` | computes only what the fusion consumes, 20 times per scene, in memory |
| `../apply_secondary_growth.py` (CLI) | `radii.build_radius_arrays` | computes the four models as well, and writes them into a copy of the `.vtp` |

## Step by step

1. **Get the polylines.** From a live plant (`generator/polylines.py`) or from a file
   (`polydata.py`, standard XML — no `vtk` module needed).
2. **`root_tree.py::build_root_tree` — rebuild the topology.**
   `Organism::writeVTP` writes one polyline per organ with strictly sequential point numbering:
   the parent/child link is *not* in the file. Each lateral does store a **bit-for-bit copy** of
   its parent's node, so the tree is glued back by **exact** coordinate equality, filtered on
   `order` and `id`. The result carries, per node: parent index, topological level, primary
   radius, age in days, and whether it is structural.
3. **`radial_models.py` — the four candidate radii.**
   - `compute_age_radius` (§3.1): `r = r0 + k·t^α`, fine roots keep `r0`.
   - `compute_pipe_radius` (§3.2), `compute_da_vinci_radius` (§3.3), `compute_murray_radius`
     (§3.4) are the same recurrence from the tips — `coefficient × (Σ r_child^exponent)^(1/exponent)`
     — with different coefficients and exponents, so one upward pass covers all three.
4. **`fusion.py::fuse_radii` — Murray's shape, the age law's magnitude.**
   The Murray profile is scaled so its collar matches the age law's collar; fine roots keep their
   primary radius.
5. **`fusion.py::enforce_continuity` — no root thicker than its bearer**, and none thinner than
   its primary radius, walking from the collar down so a parent is already constrained when its
   children are handled.
6. **Write.** The CLI appends arrays to `<PointData>` and leaves points, polylines and
   `<CellData>` byte-identical; the generator just keeps the array.

## Who does what

| File | Responsibility |
|---|---|
| `parameters.py` | every number of the model, as the *Picea abies* prior of §5 |
| `polydata.py` | reads and rewrites a `.vtp` as plain XML, without the `vtk` module |
| `root_tree.py` | parent/child reconstruction, levels, and the age of every node |
| `radial_models.py` | the four radius models |
| `fusion.py` | the fusion, the continuity constraints, and the taper diagnostic |
| `radii.py` | the two entry points — cheap for the dataset, complete for the CLI |

## Running the CLI

numpy is the only dependency, so this works on the host as well as in the container:

```bash
python3 code_val/apply_secondary_growth.py code_val/pilot_v1/vtp/example_0001_run_01.vtp
python3 code_val/apply_secondary_growth.py code_val/pilot_v1/vtp/ -o code_val/pilot_v1/vtp_thickened/
python3 code_val/apply_secondary_growth.py input.vtp --growth-rate 0.035 --murray-exponent 2.5
```

A file or a folder as input. Without `-o`, the output is `<name>_thickened.vtp` next to the
input. All five model parameters are overridable on the command line.

The output file is the input file **plus** six `<PointData>` arrays:

| Array | Contents |
|---|---|
| `radius_secondary` | the final radius — the one to use |
| `radius_primary` | the original CellData `radius`, spread per node, for comparison |
| `radius_age` | §3.1, `r0 + k·t^α` |
| `radius_pipe` | §3.2, Shinozaki's pipe model |
| `radius_da_vinci` | §3.3, area conservation × SGC |
| `radius_murray` | §3.4, hydraulic optimum with exponent Δ |

The radius becomes **per node** rather than per organ: in ParaView, `Tube` then *Scale by Scalar*
on `radius_secondary` gives a tapered root directly. One diagnostic line is printed per file,
with the taper ratio §4 expects under 0.5 and the count of ambiguous topological links.

## Key numbers (the *Picea abies* prior)

| Symbol | Constant | Value |
|---|---|---|
| k | `secondary_growth_rate` | 0.022 cm·day^−α |
| α | `allometric_exponent` | 0.5 |
| κ | `pipe_efficiency` | 0.8 |
| SGC | `area_conservation` | 0.80 |
| Δ | `murray_exponent` | 2.1 |
| — | `maximum_radius_cm` | 15.0 |

## Choices and limits

- **Why Murray anchored on the age law, and not `max(r_age, r_pipe)` as §4 says.** Measured on a
  120-year *Picea*, median radius by order 0→3:

  | model | order 0 | 1 | 2 | 3 | taper |
  |---|---|---|---|---|---|
  | `r_age` | 4.785 | 4.423 | 4.255 | 4.231 | 0.82 — flat |
  | `r_murray` | 0.542 | 0.192 | 0.098 | 0.060 | 0.08, but a collar 6× too thin |

  `r_age` only depends on time, so at 120 years it thickens a third-order lateral as much as the
  collar. `r_murray` respects the hierarchy but starts from CPlantBox's primary radius, one to two
  orders of magnitude too thin. Keeping Murray's profile and anchoring it on the age law's collar
  is the one combination that gets both the shape and the magnitude.
- **The pipe model and da Vinci are not used in the fusion.** Their coefficient is below 1 and is
  applied at *every* node, so along a chain the radius decays instead of accumulating and the
  `r ≥ r0` floor snaps it straight back. Measured: their per-order radii are identical to the
  primary radius. They are still computed and written by the CLI as calibration witnesses. Two
  possible corrections, to be settled at calibration: apply κ only at nodes with several children,
  or set κ = 1.
- **Topology is rebuilt from coordinates, and the equality must stay exact.** Measured over the
  five files of `pilot_v1/vtp/`: **1049 organs out of 1050** resolved unambiguously. Without the
  `order`/`id` filter: 69 ambiguities and at least one wrong assignment in `example_0001` alone.
  The residual case is settled by creation order and reported on stdout. A tolerance instead of
  exact equality would create false links — 279 coordinates are already shared by more than two
  nodes.
- **Continuity wins over the primary floor.** The two §4 constraints contradict each other when
  CPlantBox draws a lateral thicker than the segment carrying it. Measured: 17 nodes per file, all
  fine roots, largest gap 0.002 cm.
- **Parameters per species.** The dataset reads them from `Species.secondary_growth`
  (`tree/species.py`); today every species carries this *Picea abies* prior, so the oak and the horse
  chestnut radii, and the *major* / *minor* targets, are not calibrated.
- **The calibration is not validated.** The defaults are the §5 prior, not a measurement.
  Re-fit them on TreeCity's GPR / excavation data.
- **Gompertz saturation is not implemented.** The power law is enough over the dataset's 5–120
  year range; saturation only matters past 80 years.
- **v1 does not use any of this.** `dataset/occupancy.py` still rasterises the centreline alone;
  only the v2 generator stamps the corrected radius.
