# Build

`build.py` runs the design and builds every piece, one at a time, so the whole roof never
has to fit in memory. It reads `brief.json` and `drawing.json` when present, the defaults
otherwise.

```bash
uv run python projects/roof/build.py                                 # every piece at the brief's voxel (40 mm)
uv run python projects/roof/build.py --out out                       # also write STLs, a plan and a manifest
uv run python projects/roof/build.py --voxel 12 --out out            # production resolution
uv run python projects/roof/build.py --voxel 12 --pieces panel_0_1_00 --out out   # one piece, by name or role
```

## Output

| File | |
|---|---|
| `<piece>.stl` | one per piece, in mm, at full scale |
| `plan.png` | beams, water, openings, planters and the kit |
| `roof_preview.stl` | the whole roof, coarse and unweathered |
| `manifest.json` | the brief, the water and light checks, the seams, and each piece's size, dowels, triangles, watertightness and beam depth |

The run ends with one line of checks: pieces watertight, least beam depth, seams.

## Resolution and cost

| Voxel | Use | Cost |
|---|---|---|
| 40 mm | looking, the default | whole roof about 2 minutes, under 0.5 GB |
| 10–15 mm | making | one 3 m panel at 12 mm: about 2.5 minutes, 2.6 GB |

A feature needs about three voxels to survive, so the voxel sets the finest detail.

## Printing

The STLs are at full scale, in mm. To print a sample, open a piece in a slicer and scale it
there. Walls and dowel fits shrink with it, so check them at small scales.
