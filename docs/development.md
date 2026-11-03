# Development

## Tests

```bash
uv sync --extra notebook --group dev
uv run python -m pytest        # tests and doctests, about 20 seconds
uv run ruff check .
```

The tests run on Python 3.9 too, the version Rhino embeds. They check that the
notebook parses and calls nothing that has gone; run the notebook itself after editing it.

## Grasshopper components

Each component is a folder in `grasshopper/components/`: `code.py`, `metadata.json` and a
24 × 24 `icon.png`. `code.py` converts Rhino objects and calls one function in
`grid_roof/nodes.py`, which the tests cover.

`scripts/ghuser` compiles them with
[ghuser-builder](https://git.rccn.dev/libs/ghuser-builder), cloned next to this repository:

```bash
scripts/ghuser dev build     # build and verify into build/ghuser-dev; Grasshopper untouched
scripts/ghuser dev           # Mac + Rhino 8: also link into Grasshopper and reload
scripts/ghuser               # Docker, as CI: dist/ghuser/, for a release
```

For a release, zip `dist/ghuser/*.ghuser` as `grid-roof-ghuser.zip` and attach it to a
GitHub release.

## Adding a component

1. Add a function to `grid_roof/nodes.py` that takes the inputs by name, and a test for it.
2. Add `grasshopper/components/Roof_Something/` with `code.py` and `metadata.json`,
   copying an existing one.
3. Keep `import System` and `import Rhino` at the top of `code.py`: Rhino 8 evaluates the
   type annotations on `RunScript` and fails without them.
4. Give it a fresh `instanceGuid` (`python -c "import uuid; print(uuid.uuid4())"`).
5. Add a 12 × 12 sketch to `scripts/make_icons.py` and run it.
