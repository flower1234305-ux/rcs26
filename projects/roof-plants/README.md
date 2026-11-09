# roof-plants

Owner: @flower1234305-ux

The grid roof with plants. Each planter is cut to suit what grows in it: the plant's numbers
(`offset`, `rim`, `depth`) reshape the planter's outline, depth and drain, and the rest of the roof
follows. The question is whether planting conditions and roof conditions can drive one distance
field together. The plant numbers are assumptions, not sourced values; this shows the workflow.

## Run it

From the repository root:

```bash
uv sync --all-packages
uv run jupyter lab projects/roof-plants/plants_walkthrough.ipynb
uv run python -m pytest projects/roof-plants
uv run python scripts/run_notebooks.py roof-plants
uv run python -m roof_plants.plant_build --out out        # all 53 pieces at 40 mm, a few minutes
```

`plant_build` reads `drawing.json`, `plants.json` and `planter_plants.json` from this folder, and
`brief.json` from the current folder when present, as `projects/roof/build.py` does.

## Steps

1. **Roof conditions.** `Brief` and `drawing.json`, as in `projects/roof`.
2. **Plant conditions.** `plants.json` (edited as `plants.csv`, converted by `plant_table`), and
   `planter_plants.json`, which says what grows in each planter.
3. **Openings.** `plants.opening_spec` turns each plant into a planter opening.
4. **Steps 3-8.** `design_roof(brief, drawing, steps=plant_drains.plant_steps_drained(brief, specs))`
   replaces Step 4 (`water`) and Step 7 (`voids`) and keeps every other step.
5. **Checks.** `plant_checks` and `plant_drains`: soil depth, wall, beams, light openings, drains,
   standing water, the drain bore in each planter.
6. **Pipes and loads.** `plant_pipes` routes each planter drain under the slab (data only);
   `plant_loads` compares load scenarios side by side, and judges nothing structural.
7. **Section and STL.** `plant_figures`, and `plant_build` for the pieces. Geometry goes in `out/`.

`docs/roof-plants.md` explains each step, the checks and the open decisions (in Chinese).

## Where the roof comes from

Projects don't import each other, so the roof is copied, not imported. These modules are copies of
`projects/roof/grid_roof` at commit `f4c0b44`: `brief`, `checks`, `design`, `drainage`, `drawing`,
`heightfield`, `kit`, `preview` and `spinodoid`, with `drawing.json`. They are unchanged except
for `grid_roof` reading `roof_plants` in docstrings, and the `steps=` argument of `design_roof`.
A fix to the roof in `projects/roof` does not reach this copy by itself.

## Not here

This project holds the planter work from the old `grid-roof-plants` repository, branch
`roof-plants-contribution` (`e910bec`). Work on that repository's other branches is not here,
and neither are its printer samples (`printing`) or Grasshopper components.
