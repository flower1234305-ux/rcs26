"""Build the grid roof piece by piece.

    uv run python projects/roof/build.py                                # every piece at the brief's voxel (40 mm)
    uv run python projects/roof/build.py --out out                      # also the plan, STLs and a manifest
    uv run python projects/roof/build.py --voxel 12 --out out           # production
    uv run python projects/roof/build.py --voxel 12 --pieces beam,node  # one machine's share

Reads brief.json and drawing.json when present, the defaults otherwise.
"""

import argparse
import json
import os
import time

import grid_roof as roof
from compas_vol import nodes
from compas_vol.assembly import Seams
from compas_vol.meshing import export_stl, is_watertight, write_stl

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--brief", default=os.path.join(HERE, "brief.json"), help="brief JSON (default: brief.json)")
    parser.add_argument("--drawing", default=os.path.join(HERE, "drawing.json"), help="drawing JSON")
    parser.add_argument("--voxel", type=float, help="override the brief's voxel size, in mm")
    parser.add_argument("--pieces", help="comma-separated piece names or roles: node, beam, panel")
    parser.add_argument("--out", help="folder for the plan, a coarse whole-roof STL, the pieces and a manifest")
    args = parser.parse_args()

    brief = roof.Brief.load(args.brief) if os.path.exists(args.brief) else roof.Brief()
    if args.voxel:
        brief.voxel = args.voxel
    drawing = roof.Drawing.load(args.drawing) if os.path.exists(args.drawing) else roof.Drawing.sample()

    started = time.time()
    built = roof.design_roof(brief, drawing)
    water = built.incision.summary()
    print("design: {:.0f} m of channel, {} of {} outlets used, {} puddles, in {:.0f}s".format(
        water["channel_length"] / 1000, water["outlets_used"], water["outlets"], water["reverse_falls"],
        time.time() - started))
    apertures = roof.clear_apertures(brief, drawing, built.design.roof)
    for n, aperture in enumerate(apertures):
        print("  opening {}: drawn {drawn:.2f} m2, clear {clear:.2f} m2".format(n, **aperture))

    assembly = built.assembly
    cost = assembly.cost(voxel=brief.voxel, halo=brief.halo)
    print("kit: {} pieces; at {:.0f} mm the whole roof is {:,} samples ({:,.0f} MB per array), the largest piece "
          "{:,} ({:,.0f} MB)".format(len(assembly), brief.voxel, cost["whole_model"], cost["whole_model_bytes"] / 1e6,
                                     cost["per_piece"], cost["per_piece_bytes"] / 1e6))

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ax = roof.preview.plan(brief, drawing, built.beams, built.incision, pieces=assembly)
        ax.figure.savefig(os.path.join(args.out, "plan.png"), dpi=130)
        plt.close(ax.figure)
        # The whole roof is affordable only coarsely, and only unweathered.
        export_stl(built.design.roof, os.path.join(args.out, "roof_preview.stl"),
                   (-100, -100, -100, brief.length + 100, brief.width + 100, brief.thickness + 100), (183, 123, 11))

    chosen = list(assembly)
    if args.pieces:
        wanted = args.pieces.split(",")
        chosen = [p for p in assembly if p.name in wanted or p.role in wanted]

    seams, rows, last = Seams(assembly, brief.voxel), [], time.time()
    for piece, field, raw in assembly.build(built.weathering, brief.voxel, brief.halo, pieces=chosen, seams=seams):
        vertices, faces = nodes.mesh(field.to_volume(), None, None, 0)
        row = {"name": piece.name, "role": piece.role, "size_mm": [round(v) for v in piece.size],
               "dowels": len(piece.joints), "triangles": int(len(faces)), "watertight": is_watertight(vertices, faces)}
        if piece.role in ("node", "beam"):
            row["beam_depth_mm"] = roof.beam_depth(raw, built.beams, piece.bounds)
        if args.out:
            write_stl(os.path.join(args.out, piece.name + ".stl"), vertices, faces, name=piece.name)
        rows.append(row)
        print("  {name:<14} {triangles:>9,} triangles  watertight {watertight}".format(**row)
              + ("  beam depth {:.0f} mm".format(row["beam_depth_mm"]) if "beam_depth_mm" in row else "")
              + "  {:.1f}s".format(time.time() - last))
        last = time.time()

    seam = seams.summary()
    depths = [r["beam_depth_mm"] for r in rows if r.get("beam_depth_mm") is not None]
    print("checks: {} of {} watertight; least beam depth {}; {} seams within {:.1f} mm, {:.2%} disagreement".format(
        sum(r["watertight"] for r in rows), len(rows), "{:.0f} mm".format(min(depths)) if depths else "-",
        seam["faces"], seam["offset"], seam["disagreement"]))
    print("done in {:.0f}s".format(time.time() - started))

    if args.out:
        manifest = {"brief": brief.to_dict(), "water": water, "openings": apertures, "seams": seam, "pieces": rows}
        with open(os.path.join(args.out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1, default=float)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
