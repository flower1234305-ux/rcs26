# The roof

## What this is

An application of `compas_vol`, not a library: one 18 × 12 m roof designed as a single distance field and built as 53 pieces. It is the worked example for the other projects. All dimensions are in mm.

Something belongs in `compas_vol` only if it is general and more than one project would otherwise write it. What is specific to the roof stays here.

## Commands

From the repository root; the root `AGENTS.md` has the general ones.

```bash
uv run jupyter lab projects/roof/walkthrough.ipynb
uv run python -m pytest projects/roof
uv run python -m pytest projects/roof/tests/test_design.py -k water
uv run python -m pytest projects/roof/grid_roof/kit.py       # one module's doctests
uv run python projects/roof/build.py --out out               # every piece at 40 mm, about 2 minutes
uv run python projects/roof/build.py --voxel 12 --pieces panel_0_1_00 --out out   # one piece, by name or role
```

## Architecture

**Two inputs and a chain of steps.** `Brief` (`brief.py`) holds every number, with defaults, and `Drawing` (`drawing.py`, `drawing.json`) holds the opening and planter outlines and the drain points. `design.py` has one function per step, each taking the brief and earlier results and returning its own result. `design_roof(brief, drawing)` runs them in order and returns a `Roof` holding each step's output:

`beams` → `water` → `slab` → `soffit` → `voids` → `keep` → `design` → `kit` → `weathering`

Step numbers in the `design.py` docstrings match the headings in `walkthrough.ipynb`, and each docstring lists the brief fields that step reads. The docstrings also name the Grasshopper canvas equivalent, because steps are built from `compas_vol.nodes` wherever a component exists, so a step drawn on a canvas gives the same field.

**Design rules are kept in one place and checked in another.** The table in `docs/workflow.md` maps each rule to both.
- `keep` builds the solid no later step may remove. `weathering` applies it through `field.constrain`, and that is the only reason beams, the deck and planter walls survive erosion.
- `Design` has two fields: `roof`, and `drawn`, which is the same model without foam. Panel cuts and joints are placed against `drawn` because foam noise swamps the features.
- `checks.py` measures rules. Pass `beam_depth` the *processed* field from `Assembly.build`, not the finished one, because a dowel socket reads as lost depth.

**Building is per piece.** `design_roof` only constructs the field and the `Assembly`. No voxels are sampled for the whole roof, except in the coarse unweathered `roof_preview.stl`. `Assembly.build` then samples each piece's box plus a `halo`, runs `weathering`, and re-applies the joints, so memory is bounded by the piece. Neighbouring pieces meet because `Spinodoid` and the other fields are defined in world coordinates. `Seams` measures how closely they meet. Keep any new field world-coherent, and never make it depend on a piece's bounds.

**Three front ends share this code.** Keep logic in `grid_roof`, not in the front ends.
- `walkthrough.ipynb`: the design step by step.
- `build.py`: the command-line build. It silently reads `brief.json` and `drawing.json` from the repository root when present, so a leftover `brief.json` changes its output. Tests use the defaults.
- `grasshopper/components/Roof_*/` (parked): each `code.py` converts Rhino objects and calls one function in `grid_roof/nodes.py`, which is the tested layer. No test parses or checks the component folders. Follow the checklist in `docs/development.md` when adding one: it needs a fresh `instanceGuid`, and `import System` and `import Rhino` must stay at the top of `code.py`.

**Two modules are named `nodes`.** `grid_roof.nodes` holds the roof's own components (`Roof_*`). In `design.py`, `build.py` and the notebook, `nodes` means `compas_vol.nodes`. The notebook calls the library's as `nodes.x` and this package's as `roof.x`.

## Tests

- Tests build the design at `voxel=60` in module-scoped fixtures, shared across each test module.
- `tests/test_nodes.py` asserts the exact kit (53 pieces: 12 nodes, 17 beams, 24 panels) and `0 puddles`, so changing the grid or the sample drawing means updating those numbers.
- `tests/test_notebook.py` does not run the notebook. It parses it and fails if `nodes.x` isn't in `compas_vol.nodes.__all__`, or if `roof.x` isn't in `grid_roof.__all__`. CI runs it, and locally `uv run python scripts/run_notebooks.py roof` does.

## Adding a rule

`docs/your-design.md` has a worked example. A new rule touches:
1. A field in `Brief`. `Brief.from_dict` rejects unknown names.
2. A check in `checks.py`, listed in that module's `__all__`.
3. The import and `__all__` in `grid_roof/__init__.py`, or the notebook test fails on `roof.<name>`.
4. A test in `tests/test_design.py`.
