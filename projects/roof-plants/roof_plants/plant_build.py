"""Build the planted roof piece by piece: every piece weathered, meshed, checked and written.

    uv run python -m roof_plants.plant_build --out out     # all 53 pieces at 40 mm, a few minutes

Run it from the repository root. Reads brief.json from the current folder when present, like
projects/roof/build.py, and drawing.json, plants.json and planter_plants.json (or --planters) from
projects/roof-plants. Writes one STL per piece, the merged roof and results.json.
Exits with 1 if a check fails or a piece is not watertight.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

from compas_vol import nodes
from compas_vol.assembly import Seams
from compas_vol.meshing import is_watertight, write_stl

from .brief import Brief
from .checks import beam_depth
from .design import design_roof
from .drawing import Drawing
from .plant_checks import all_ok, table, water_check
from .plant_drains import drain_rows, drain_table, drained_planter_rows, plant_steps_drained
from .plants import PlanterFitError, assign, load_plants, opening_spec

__all__ = ["build_pieces", "passed", "stand_in"]

#: The project folder, which holds drawing.json and the plant files.
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The stand-in planting, to name when the intended one does not fit.
FALLBACK = "planter_plants_fallback.json"


def stand_in(planting):
    """Whether a parsed planter_plants file says it is a stand-in, not the design (its ``note`` says STAND-IN)."""
    return "STAND-IN" in str(planting.get("note", ""))


def build_pieces(brief, built, out, pieces=None, merged="roof_plant.stl"):
    """Build ``pieces`` (by default all), writing STLs under ``out``; returns the counts ``build.py`` prints."""
    pieces_dir = os.path.join(out, "pieces")
    os.makedirs(pieces_dir, exist_ok=True)
    assembly = built.assembly
    seams, rows = Seams(assembly, brief.voxel), []
    all_vertices, all_faces, base = [], [], 0
    chosen = list(assembly) if pieces is None else pieces
    for piece, field, raw in assembly.build(built.weathering, brief.voxel, brief.halo, pieces=chosen, seams=seams):
        vertices, faces = nodes.mesh(field.to_volume(), None, None, 0)
        row = {"name": piece.name, "role": piece.role, "triangles": int(len(faces)),
               "watertight": bool(is_watertight(vertices, faces))}
        if piece.role in ("node", "beam"):
            row["beam_depth_mm"] = beam_depth(raw, built.beams, piece.bounds)
        write_stl(os.path.join(pieces_dir, piece.name + ".stl"), vertices, faces, name=piece.name)
        all_vertices.append(np.asarray(vertices))
        all_faces.append(np.asarray(faces) + base)
        base += len(vertices)
        rows.append(row)
    if merged and rows:
        write_stl(os.path.join(out, merged), np.concatenate(all_vertices), np.concatenate(all_faces), name="roof_plant")
    depths = [r["beam_depth_mm"] for r in rows if r.get("beam_depth_mm") is not None]
    return {"pieces": rows, "count": len(rows), "watertight": sum(r["watertight"] for r in rows),
            "least_beam_depth": min(depths) if depths else None, "seams": seams.summary()}


def passed(rows, water, result):
    """Did every check pass, and is every built piece watertight?"""
    return all_ok(rows, water) and result["watertight"] == result["count"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="out")
    parser.add_argument("--voxel", type=float, help="override the brief's voxel size, in mm")
    parser.add_argument("--planters", default=os.path.join(PROJECT, "planter_plants.json"),
                        help="which plant grows in each planter; planter_plants_fallback.json is the stand-in")
    args = parser.parse_args()

    brief = Brief.load("brief.json") if os.path.exists("brief.json") else Brief()
    if args.voxel:
        brief.voxel = args.voxel
    drawing = Drawing.load(os.path.join(PROJECT, "drawing.json"))
    with open(args.planters, encoding="utf-8") as f:
        planting = json.load(f)
    note = planting.get("note")
    if stand_in(planting):
        print("WARNING: STAND-IN planting, not the design ({}): {}".format(args.planters, note))
    chosen = assign(load_plants(os.path.join(PROJECT, "plants.json")), planting, len(drawing.planters))
    specs = [opening_spec(p) for p in chosen]

    started = time.time()
    try:
        built = design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    except PlanterFitError as error:
        print("does not fit:", error)
        print("the stand-in that fits: --planters projects/roof-plants/{} (P1 grows control; "
              "see projects/roof-plants/docs/roof-plants.md, v2, item 5)".format(FALLBACK))
        return 1
    rows = drained_planter_rows(brief, drawing, specs, built)
    water = water_check(built.incision)
    drains = drain_rows(brief, drawing, specs, built)
    print(table(rows))
    print(drain_table(drains))
    print("water:", water)
    print("all checks pass:", all_ok(rows, water) and all(d["ok"] for d in drains))

    os.makedirs(args.out, exist_ok=True)
    result = build_pieces(brief, built, args.out)
    result["seconds"] = time.time() - started
    print("build: {watertight} of {count} watertight; least beam depth {least_beam_depth} mm; "
          "{seconds:.0f}s".format(**result))
    print("seams:", result["seams"])
    ok = passed(rows, water, result) and all(d["ok"] for d in drains)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"all_ok": ok, "planting": args.planters, "stand_in": stand_in(planting), "planting_note": note,
                   "planters": rows, "drains": drains, "water": water, "build": result}, f, indent=1,
                  ensure_ascii=False, default=float)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
