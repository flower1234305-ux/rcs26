# grid-roof

An 18 × 12 m roof, 600 mm thick, on a 6 m beam grid, designed as one distance field
and built as 53 pieces: rain channels on the deck, a porous soffit, light openings
and planters. An application of [compas_vol](https://github.com/rccn-dev/compas_vol),
and the template for the designs in the
[workshop](https://github.com/rccn-dev/designing-by-process).

## Install

Clone it next to compas_vol, which it builds against:

```bash
git clone https://github.com/rccn-dev/compas_vol
git clone https://github.com/rccn-dev/grid-roof
cd grid-roof
uv sync --extra notebook
```

Step by step, with checks: [install](docs/install.md).

## Quick start

```bash
uv run jupyter lab walkthrough.ipynb       # the design, step by step
uv run python build.py --out out           # every piece as an STL, with a manifest of checks
```

## Documentation

Read them in this order the first time.

| Topic | Page |
|---|---|
| installing, and checking the install | [install](docs/install.md) |
| working in the notebook | [notebook](docs/notebook.md) |
| the steps, and the rule each one keeps | [workflow](docs/workflow.md) |
| your own design: brief, drawing, a new rule | [your design](docs/your-design.md) |
| building every piece, at any resolution | [build](docs/build.md) |

Also: [grasshopper](docs/grasshopper.md), the same steps as Rhino 8 components (optional),
and [development](docs/development.md), for tests and the components.

## Related

- [compas_vol](https://github.com/rccn-dev/compas_vol): the distance-field library this is built on.
- [designing-by-process](https://github.com/rccn-dev/designing-by-process): the workshop that uses this repository.
