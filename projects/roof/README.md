# The grid roof

An 18 × 12 m roof, 600 mm thick, on a 6 m beam grid, designed as one distance field
and built as 53 pieces: rain channels on the deck, a porous soffit, light openings
and planters. An application of [compas_vol](https://github.com/rccn-dev/compas_vol),
and the worked example for the other projects here.

## Quick start

From the repository root, after [install](../../docs/install.md):

```bash
uv run jupyter lab projects/roof/walkthrough.ipynb   # the design, step by step
uv run python projects/roof/build.py --out out       # every piece as an STL, with a manifest of checks
```

## Documentation

Read them in this order the first time.

| Topic | Page |
|---|---|
| working in the notebook | [notebook](docs/notebook.md) |
| the steps, and the rule each one keeps | [workflow](docs/workflow.md) |
| changing it: brief, drawing, a new rule | [changing the roof](docs/your-design.md) |
| building every piece, at any resolution | [build](docs/build.md) |

Also: [grasshopper](docs/grasshopper.md), the same steps as Rhino 8 components (parked for now),
and [development](docs/development.md), for the components.

## Related

- [compas_vol](https://github.com/rccn-dev/compas_vol): the distance-field library this is built on.
