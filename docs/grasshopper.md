# Grasshopper

Optional. Five components on a *Grid Roof* tab run the same steps as the notebook; nothing
else in these docs needs them. They need Rhino 8, and the component downloads from the
two repositories' releases.

## Install

Rhino 8 runs its own Python 3.9, so install both packages into it from the clones in
[install](install.md). In the `grid-roof` folder:

macOS:

```bash
~/.rhinocode/py39-rh8/python3.9 -m pip install -e "../compas_vol[meshing,processes]"
~/.rhinocode/py39-rh8/python3.9 -m pip install --no-deps -e .
```

Windows (PowerShell):

```powershell
& "$env:USERPROFILE\.rhinocode\py39-rh8\python.exe" -m pip install -e "..\compas_vol[meshing,processes]"
& "$env:USERPROFILE\.rhinocode\py39-rh8\python.exe" -m pip install --no-deps -e .
```

`--no-deps` stops pip from looking for compas_vol on PyPI: it is already installed from the
clone. If the Rhino Python path is missing, start Rhino 8 once and open the *ScriptEditor*.

Then download `compas_vol-ghuser.zip` from the
[compas_vol releases](https://github.com/rccn-dev/compas_vol/releases) and
`grid-roof-ghuser.zip` from the [grid-roof releases](https://github.com/rccn-dev/grid-roof/releases),
unzip both into Grasshopper's User Object folder (*File › Special Folders › User Object
Folder*), and restart Rhino.

**Check:** **Volumetric Info** on the *COMPAS Vol* tab lists what is installed, and the
*Grid Roof* tab holds five components.

| Symptom | Fix |
|---|---|
| *Error getting GH_ScriptInstance instance* | install the latest release of the components |
| a component cannot import `grid_roof` or `compas_vol` | install into Rhino's Python as above, then restart Rhino |

## Components

| Component | Inputs | Outputs |
|---|---|---|
| **Roof Brief** | `file`, and nine numbers: `beam`, `beam_depth`, `skin`, `pore`, `fraction_soffit`, `opening_flare`, `planter_depth`, `panel`, `voxel` | `brief`, `numbers` |
| **Roof Drawing** | `file`, `openings` (curves), `planters` (curves), `drains` (points) | `drawing`, `outlines` |
| **Roof Design** | `brief`, `drawing`, `run` | `roof`, `design`, `bounds`, `pieces`, `names`, `report` |
| **Roof Piece** | `roof`, `brief`, `name`, `voxel`, `run` | `mesh`, `report` |

Unwired inputs keep the defaults: the brief's numbers, the sample drawing.

## On the canvas

```
sliders ─────────► Roof Brief ──┬──────────────────────────────┐
curves, points ──► Roof Drawing ─┴► Roof Design ─ design, bounds ─► Volumetric Mesh
                                         └─ roof, names ──────────► Roof Piece ─► mesh
```

1. **Roof Brief**: wire number sliders to the values you want to change.
2. **Roof Drawing**: draw closed curves and points in Rhino, in mm, on the 18 × 12 m plan
   with its origin at a corner, and set them as the inputs. `outlines` shows what the roof
   reads.
3. **Roof Design**: runs steps 3 to 10 in about 7 seconds. Wire `design` and `bounds` into
   **Volumetric Mesh** (*COMPAS Vol › Meshing*) to see it. A `resolution` of 100 is half a
   million triangles, in a second or two; much more is slow to hand to Rhino.
   `report` holds the checks for water, light and the kit.
4. **Roof Piece**: pick a piece by name from `names` (a **List Item** works). About 4
   seconds at 40 mm. Bake `mesh` to export it.

Set `run` to `False` with a **Boolean Toggle** to hold a result while you change things
upstream.

## Saving the drawing

To use a drawing from Rhino in the notebook or `build.py`, save it from a Python 3
**Script** component wired to `drawing`:

```python
drawing.save(r"C:\path\to\grid-roof\drawing.json")
```

## Going further

Roof Design runs every step at once. To change one step, call it from a Python 3
**Script** component: `import grid_roof as roof`, then for example
`roof.soffit(brief, slab, beams)`. The functions are listed in [workflow](workflow.md).
