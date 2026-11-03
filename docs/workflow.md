# Workflow

The design is two inputs and ten steps. Each step is one function in `grid_roof`, reads
the brief and what the steps before it made, and returns its result.

## Inputs

| | |
|---|---|
| `Brief` | every number, in mm, with defaults (`grid_roof/brief.py`); saved as `brief.json` |
| `Drawing` | light openings and planters as closed outlines, drains as points (`drawing.json`); make yours with `blob` and `outline` ([your design](your-design.md#the-drawing)) |

## Steps

| | Function | Makes |
|---|---|---|
| 3 | `beams` | the 6 m grid of beams, and the core each must keep |
| 4 | `water` | rain routed over the deck to the drains; channels cut where enough area drains |
| 5 | `slab` | the deck, with its channels, as a solid slab |
| 6 | `soffit` | a foam below the deck: solid near the deck, open at the soffit, closed near beams |
| 7 | `voids`, `carve` | light openings, planter pockets, drain outlets |
| 8 | `keep`, `design` | what no later step may remove, and the design itself |
| 10 | `kit` | nodes, beams and panels, with joints placed where both sides are solid |
| 11 | `weathering` | the process each piece goes through: pitting and wear |

Steps 1, 2, 9 and 12 to 14 of the notebook are the inputs, checks and building.
`design_roof(brief, drawing)` runs steps 3 to 11 in one call.

## Rules, and where each is kept

| Rule | Kept by | Checked by |
|---|---|---|
| beams keep 500 mm of depth | `keep`, a constraint on every process | `beam_depth` |
| light openings go through | `voids` | `clear_apertures` |
| planters keep a wall and a floor | `keep` | |
| water drains, with no puddles | `water`: priority flood, beds graded downstream | `Incision.summary()` |
| the 120 mm deck stays whole | `keep`, and pitting stays out of the rock under it | |

Weathering runs per piece, with a halo of its neighbours, so pieces built separately
still meet; `Seams` measures how closely.

## Specific to this roof

`Drainage` and `Incision` (water over a plan), `VolHeightField` (a plan grid of heights
as a solid), `Spinodoid` (a foam in world coordinates, the same in every piece), and
`grid_kit` and `beam_bands` (the slab cut into nodes, beams and panels). The rest comes
from compas_vol.
