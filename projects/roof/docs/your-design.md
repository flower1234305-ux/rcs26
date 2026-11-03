# Changing the roof

The roof is a worked example: a brief, a drawing, a few steps, and a check for every rule.
Your own project keeps that shape, and these are the same edits you would make there.

## Change it, in this order

| | Where | What |
|---|---|---|
| 1 | `grid_roof/brief.py` | your numbers and their defaults |
| 2 | `drawing.json` | your openings, planters and drains: [the drawing](#the-drawing), below |
| 3 | `grid_roof/design.py` | change a step, or add one: a step takes the brief and earlier results, and returns its own |
| 4 | `grid_roof/checks.py` | a check for every rule you add |
| 5 | `tests/` | a test that the rule holds |

Change one thing, rerun the notebook from that step, look, run the tests, then commit.

## The drawing

`drawing.json` holds the openings and planters as closed outlines and the drains as points,
all in mm on the 18 × 12 m plan, with the origin at a corner. Make yours in Step 2 of the
notebook, in place of `roof.Drawing.load("drawing.json")`:

```python
from compas.geometry import Point

drawing = roof.Drawing(
    openings=[roof.blob((9000, 9000), 900, seed=1)],                                     # organic, about 1.8 m across
    planters=[roof.outline([(2000, 2000), (4000, 2000), (4000, 3500), (2000, 3500)])],   # corners, in order
    drains=[Point(x, y, 0) for x in (4500, 10500, 16500) for y in (1500, 10500)],          # one in every bay
)
drawing.save("drawing.json")
```

`roof.blob(centre, radius, seed)` is the organic shape the sample uses; `roof.outline`
takes corners. Keep openings and planters off the beams, which run along every 6 m grid
line; Step 9 shows what happens to light that crosses one. Water needs a drain within reach:
with only two drains on the whole roof, the water check reports puddles. Try it.

If you have Rhino, you can also draw the curves there ([grasshopper](grasshopper.md)).

## Example: a new rule

*Planters keep 1 m from the roof's edge.* Three edits and a test.

In `grid_roof/brief.py`, a number for the rule, under the planter fields:

```python
    planter_margin: float = 1000.0      # planters keep this far from the roof's edge
```

In `grid_roof/checks.py`, a check that measures it, and its name in `__all__`:

```python
__all__ = ["clear_apertures", "beam_depth", "planter_margins"]


def planter_margins(brief, drawing):
    """For each planter: how close its outline comes to the roof's edge, in mm."""
    margins = []
    for outline in drawing.planters:
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        margins.append(min(min(xs), min(ys), brief.length - max(xs), brief.width - max(ys)))
    return margins
```

In `grid_roof/__init__.py`, add `planter_margins` to the `from .checks import` line and
to `__all__`. Then a test, at the end of `tests/test_design.py`:

```python
def test_planters_keep_their_margin(brief, drawing):
    assert min(roof.planter_margins(brief, drawing)) >= brief.planter_margin
```

```bash
uv run python -m pytest projects/roof -k margin
```

It passes: the sample planters are 1940 to 3528 mm from the edge. Set `planter_margin`
to 2000 and it fails: one planter is 1940 mm away. In the notebook, print the check
in Step 9: `roof.planter_margins(brief, drawing)`.
