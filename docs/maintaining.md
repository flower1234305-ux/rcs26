# Maintaining

For whoever runs the course.

## GitHub settings

**This repository and `compas_vol`,** under *Settings*:

- *General › Pull Requests:* allow only **squash merging**, and turn on **Automatically delete head branches**.
- *Collaborators and teams:* give each student **Write**. In `rccn-dev`, a team makes this one step.
- *Branches › Add rule* for `main`: require a pull request with **1 approval**, and require status checks to pass. Here, also tick **Require review from Code Owners**.

Required status check: `ci-ok` here. In `compas_vol`, the checks named in `build.yml` and `Check Actions`. Each appears in the list once it has run on a pull request.

In `compas_vol`, also create the label `no changelog`.

## Starting a cohort

Create every project at once, because each one changes `uv.lock`:

```bash
uv run python scripts/new_project.py wall-ana roof-ben --owner ana-gh ben-gh
uv run python -m pytest
```

Commit that to a branch and merge it before the first session.

## Moving to a new compas_vol

Release `compas_vol` (its `CONTRIBUTING.md` has the steps), then change `tag` in the root `pyproject.toml`:

```bash
uv lock --upgrade-package compas-vol
uv sync --all-packages
uv run python -m pytest
```

Open that as a pull request. CI proves every project still works. A weekly tag keeps the wait short.

## A weekly rhythm

One student a week is on duty: they triage new issues, make sure review requests get answered, and flag anything two projects are duplicating. Rotate it, so everyone reads code outside their own project.

## Parked: Grasshopper components

Notebooks come first. `projects/roof/grasshopper/` and `projects/roof/scripts/ghuser` are kept but not built or tested in CI. When this returns, each project's `grid_roof/nodes.py`-style functions become the component layer, and CI needs a check that component sources parse, `instanceGuid`s are unique across projects, and a build through `ghuser-builder`.
