# AGENTS.md

Instructions for AI coding agents in this repository. Read `CONTRIBUTING.md` too: it is how the people here work, and everything in it applies to you.

## What this is

The RCS26 studio repository, where six students each develop a workflow for building-scale porous structures, designed as signed distance fields. Forms come from mathematics (TPMS) and from processes (water channels, erosion, growth), all as fields. It is a uv workspace: one environment and one `uv.lock` for all of `projects/*`, with `compas_vol` pinned to a release in the root `pyproject.toml`.

## Commands

Run everything from the repository root.

```bash
uv sync --all-packages                          # after every pull, and after adding a project
uv run ruff check .
uv run python -m pytest                         # everything: rules, every project, doctests
uv run python -m pytest projects/<name>         # one project
uv run python -m pytest projects/<name>/tests/test_steps.py -k water
uv run python -m pytest tests/test_repo_rules.py
uv run python scripts/run_notebooks.py <name>   # run a project's notebooks in a throwaway copy
uv run --with-editable ../compas_vol python -m pytest projects/<name>   # against a local compas_vol
```

## Boundaries

- **Stay in the student's project.** Find out which project they mean, then change only `projects/<that project>/`. Don't touch another student's project, or shared files (`.github/`, `scripts/`, `templates/`, `tests/`, root `pyproject.toml`, `uv.lock`), unless they ask for that specifically, and then say it needs the maintainer's review.
- **`compas_vol` stays general.** A brief, a drawing, or anything with a building type in its name belongs in a project. Projects don't import each other: copy once, and when a second project needs something, propose moving it to `compas_vol` with tests.
- **Don't merge or force-push, or commit to `main`.** Work on a branch named `<student>/<topic>`, keep each one to a single change, and let the student open and merge the pull request. Commit only when asked.
- **Keep the change small and explain it.** The student must be able to explain every line in review. Prefer the smallest diff that does the job, and say what you did not check.

## How workflows are written

They are written to become Grasshopper components later with little change.

- Every number goes in `Brief`, with a default, in millimetres.
- One function per step in the project's package. It takes the brief and earlier results, and returns its own. Use `compas_vol.nodes` where a component exists.
- Notebook cells call steps and show results. They define no functions or classes (a test enforces this). If you need a helper, it goes in the package.
- No Rhino imports outside `grasshopper/` (a test enforces this). Python 3.9 syntax only; ruff enforces it.
- Fields are defined in world coordinates, so pieces built separately still meet. Never make a field depend on a piece's bounds.
- Geometry goes in `out/`, which git ignores. Commit no STLs. Slicing is the slicer's job, so add nothing printer-specific.
- Grasshopper components are parked for now: don't add or build any unless asked.

## Testing and checking

- Write the failing test first for a bug. A new rule needs a check and a test.
- For geometry, assert a known distance at a known point. "It runs" isn't evidence the field is right.
- After editing a notebook, run it with `scripts/run_notebooks.py`. Tests only parse it.
- Commit notebooks without outputs; `uv run nbstripout <path>` strips them, and the pre-commit hook does it too.
- If `uv.lock` conflicts: `git checkout origin/main -- uv.lock && uv lock`. Never edit it by hand.
- Don't weaken or delete a test to get CI green. Tell the student what's failing instead.

Read `projects/roof/AGENTS.md` before working on the roof. It's also the fullest example of the conventions above. `compas_vol` has its own `AGENTS.md`.
