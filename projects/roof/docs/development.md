# Development

Tests, linting and pull requests are in the root [CONTRIBUTING](../../../CONTRIBUTING.md).

The components below are parked for now, and CI does not build or test them.

## Grasshopper components

Each component is a folder in `grasshopper/components/`: `code.py`, `metadata.json` and a
24 × 24 `icon.png`. `code.py` converts Rhino objects and calls one function in
`grid_roof/nodes.py`, which the tests cover.

`projects/roof/scripts/ghuser` compiles them with
[ghuser-builder](https://git.rccn.dev/libs/ghuser-builder), cloned next to this repository:

```bash
projects/roof/scripts/ghuser dev build     # build and verify into build/ghuser-dev; Grasshopper untouched
projects/roof/scripts/ghuser dev           # Mac + Rhino 8: also link into Grasshopper and reload
projects/roof/scripts/ghuser               # Docker, as CI: dist/ghuser/, for a release
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
5. Add a 12 × 12 sketch to `projects/roof/scripts/make_icons.py` and run it.
