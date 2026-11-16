# secondary_growth — the radius CPlantBox will not give you

CPlantBox draws a root's radius `a` when the root is created and never changes it again. For a
tree of 5 to 120 years that is wrong: the cambium thickens structural roots continuously. This
package **reassigns the radii after the simulation**, per node. Nothing is patched inside
CPlantBox.

Reference: `secondary_growth_modifications.md` (this folder). For every choice it says what was
done, why, and on which source or test it rests.

Two callers:

| Caller | Entry point | What it does |
|---|---|---|
| `generator/build.py` (v2 dataset) | `radii.build_final_radii` | computes only the final radius, once per simulated tree, in memory |
| `../apply_secondary_growth.py` (CLI) | `radii.build_radius_arrays` | also returns the intermediate radii and writes them into a copy of the `.vtp` |

## Step by step

1. **Get the polylines.** From a live plant (`generator/polylines.py`) or from a file
   (`polydata.py`, standard XML — no `vtk` module needed).
2. **`root_tree.py::build_root_tree` — rebuild the topology.**
   `Organism::writeVTP` writes one polyline per organ with strictly sequential point numbering:
   the parent/child link is *not* in the file. Each lateral does store a **bit-for-bit copy** of
   its parent's node, so the tree is glued back by **exact** coordinate equality, filtered on
   `order` and `id`. The result carries, per node: parent index, topological level, primary
   radius, age in days, sub-type, distance along its axis, and whether it is structural; and, per
   organ, its index, identifier, first node and size (the per-organ profile needs them).
3. **`radial_models.py` — the radii.**
   - `compute_age_radius`: `r = r0 + k·t^α`, fine roots keep `r0`. It sets the size of the collar:
     the collar diameter follows the project's DBH allometry (`tree/species.py`).
   - `compute_murray_radius`: conserved cross-section, exponent Δ = 2.
     - ST2/4/6/7: a profile per organ, `r(D) = B·T(D)` (`compute_organ_profiles`), where
       `T = 1 / (1 + a·D + b·D²)` is the taper law of the axis group (Kalliokoski et al. 2008) and
       `B` is the smallest base radius that keeps, at every node, a section at least equal to the
       tip plus the attached laterals.
     - ST1 and fine roots: the node-wise upward recurrence
       `(Σ r_child^Δ)^(1/Δ)` (`propagate_from_tips`), with an optional ST1 taper (neutral today).
4. **`fusion.py::fuse_radii` — Murray's shape, the age law's magnitude.**
   `fused² = p² + s·(r_murray² − p²)`, with `p` the primary radius and `s` chosen so that the
   collar matches the age law's collar. Tips and fine roots keep their primary radius.
5. **`fusion.py::enforce_continuity` — no root thicker than its bearer**, none thinner than its
   primary radius, then the cap `maximum_radius_cm`, walking from the collar down so a parent is
   already constrained when its children are handled.
6. **Write.** The CLI appends arrays to `<PointData>` and leaves points, polylines and
   `<CellData>` byte-identical; the generator just keeps the array.

## Who does what

| File | Responsibility |
|---|---|
| `parameters.py` | the fields of the model, with no default value |
| `../tree/species.py` | the value of every field, per species |
| `polydata.py` | reads and rewrites a `.vtp` as plain XML, without the `vtk` module |
| `root_tree.py` | parent/child reconstruction, levels, node ages, axis distances, organ tables |
| `radial_models.py` | the age law, the taper law and the conserved-section radii |
| `fusion.py` | the fusion, the continuity constraints, and the taper diagnostic |
| `radii.py` | the two entry points — cheap for the dataset, complete for the CLI |

## Running the CLI

numpy is the only dependency, so this works on the host as well as in the container. `--species`
is required: it picks the parameters of `tree/species.py` (`picea_abies`, `quercus_robur`,
`aesculus_hippocastanum`).

```bash
python3 code_val/apply_secondary_growth.py code_val/pilot_v1/vtp/example_0001_run_01.vtp --species picea_abies
python3 code_val/apply_secondary_growth.py code_val/pilot_v1/vtp/ --species quercus_robur -o code_val/pilot_v1/vtp_thickened/
python3 code_val/apply_secondary_growth.py input.vtp --species picea_abies --growth-rate 0.005 --murray-exponent 2.5
```

A file or a folder as input. Without `-o`, the output is `<name>_thickened.vtp` next to the
input. `--growth-rate`, `--allometric-exponent` and `--murray-exponent` replace the species value.

The output file is the input file **plus** four `<PointData>` arrays:

| Array | Contents |
|---|---|
| `radius_secondary` | the final radius — the one to use |
| `radius_primary` | the original CellData `radius`, spread per node, for comparison |
| `radius_age` | `r0 + k·t^α` |
| `radius_murray` | conserved-section radius with exponent Δ, before the fusion |

The radius becomes **per node** rather than per organ: in ParaView, `Tube` then *Scale by Scalar*
on `radius_secondary` gives a tapered root directly. One diagnostic line is printed per file,
with the taper ratio and the count of ambiguous topological links.

## Key numbers (`tree/species.py`, same for the three species)

| Symbol | Constant | Value |
|---|---|---|
| k | `secondary_growth_rate` | 0.5 · c · `DBH_COEFFICIENT` / 365^α = 0.00398 cm·day^−α (c = 1.0) |
| α | `allometric_exponent` | `DBH_AGE_EXPONENT` = 0.85 |
| Δ | `murray_exponent` | 2.0 |
| — | `maximum_radius_cm` | 40.0 |
| (a, b) | `main_axis_taper` (ST2) | Picea (1.739, −0.043) ; broadleaves (1.112, −0.022) |
| (a, b) | `secondary_axis_taper` (ST4/6/7) | Picea (1.409, −0.095) ; broadleaves (1.801, −0.462) |
| (a, b) | `primary_axis_taper` (ST1) | (0, 0), neutral |

`k` and `α` are computed from `tree/attributes.py`, so that a change of the project's DBH allometry
carries over to the roots. The broadleaf taper is the *Betula pendula* mature stand, a proxy.

## Choices and limits

- **Why Murray anchored on the age law, and not one of the two alone.** Measured on a 120-year
  *Picea* (with the former prior k = 0.022, α = 0.5), median radius by order 0→3:

  | model | order 0 | 1 | 2 | 3 | taper |
  |---|---|---|---|---|---|
  | `r_age` | 4.785 | 4.423 | 4.255 | 4.231 | 0.82 — flat |
  | `r_murray` | 0.542 | 0.192 | 0.098 | 0.060 | 0.08, but a collar 6× too thin |

  `r_age` only depends on time, so at 120 years it thickens a third-order lateral as much as the
  collar. `r_murray` respects the hierarchy but starts from CPlantBox's primary radius, one to two
  orders of magnitude too thin. Keeping Murray's profile and anchoring it on the age law's collar
  is the one combination that gets both the shape and the magnitude.
- **The pipe model and da Vinci's rule were removed.** They were computed and written as
  calibration witnesses, but never entered a final radius, and their per-order radii were
  identical to the primary radius.
- **Topology is rebuilt from coordinates, and the equality must stay exact.** Measured over the
  five files of `pilot_v1/vtp/`: **1049 organs out of 1050** resolved unambiguously. Without the
  `order`/`id` filter: 69 ambiguities and at least one wrong assignment in `example_0001` alone.
  The residual case is settled by creation order and reported on stdout. A tolerance instead of
  exact equality would create false links — 279 coordinates are already shared by more than two
  nodes.
- **Continuity wins over the primary floor.** The two constraints contradict each other when
  CPlantBox draws a lateral thicker than the segment carrying it. Measured: 17 nodes per file, all
  fine roots, largest gap 0.002 cm.
- **Parameters per species.** The dataset reads them from `Species.secondary_growth`
  (`tree/species.py`). The three species share k, α, Δ and the cap; only the taper of *Picea*
  comes from its own stand, those of the oak and the horse chestnut are the *Betula* proxy.
- **The collar is imposed, not fitted.** Its diameter is c × DBH(age) with c = 1.0, a lower bound
  without a source; at 120 years the simulated architecture can no longer feed it (the scale `s`
  of the fusion reaches 12 to 85). The limits, the validation at 5, 20, 50 and 120 years and the
  sensitivity to c are in `secondary_growth_modifications.md` (§2, §13, §14).
- **One taper law for every age** (the mature stand's), although it is steeper for young trees.
- **Gompertz saturation is not implemented.** The power law is enough over the dataset's 5–120
  year range.
- **v1 does not use any of this.** `dataset/occupancy.py` still rasterises the centreline alone;
  only the v2 generator stamps the corrected radius.
