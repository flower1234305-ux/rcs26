# RCS26

Building-scale porous structures, designed as signed distance fields. Each student
develops their own workflow here, for a roof, a wall or a landscape, on top of the
general library [compas_vol](https://github.com/rccn-dev/compas_vol).

| Where | What | Who changes it |
|---|---|---|
| `projects/<name>/` | one student's workflow: brief, steps, notebook, tests | its owner, reviewed by anyone |
| [compas_vol](https://github.com/rccn-dev/compas_vol) | fields and processes more than one project needs | anyone, by reviewed pull request |
| everything else here | the shared setup | the maintainer |

`projects/roof` is the worked example: an 18 × 12 m roof designed as one field and built
as 53 pieces.

## Start

```bash
git clone https://github.com/rccn-dev/rcs26
cd rcs26
uv sync --all-packages
uv run pre-commit install
uv run python -m pytest
uv run jupyter lab projects/roof/walkthrough.ipynb
```

First time on this computer? Follow [install](docs/install.md). Then read
[CONTRIBUTING](CONTRIBUTING.md), which is how we work together.

## How a workflow is written

A workflow is written the way a Grasshopper definition is drawn, so it can become
components later with little change:

| Canvas | Here |
|---|---|
| sliders | a `Brief`, saved as JSON |
| referenced curves and points | a drawing, saved as JSON with COMPAS geometry |
| a component | one function in your package, tested |
| wires | a step's result passed to the next |
| viewport | preview plots |

Notebooks call steps and show results. Logic lives in the package, and Rhino never
appears there, so a workflow stays CAD-agnostic.
