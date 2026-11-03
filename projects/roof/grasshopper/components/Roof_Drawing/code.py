"""
Light openings, planters and drains, drawn in Rhino in mm on the 18 x 12 m
plan, origin at a corner. Unwired inputs keep the sample drawing, or the one
in file.

    Args:
        file: A drawing.json. Optional; without it, the sample drawing.
        openings: Closed curves: light openings, cut through the slab.
        planters: Closed curves: planting pockets.
        drains: Points: rainwater outlets.
    Returns:
        drawing: The drawing, for Roof Design.
        outlines: The openings and planters as the roof reads them, to check against your curves.
"""
# Rhino 8 evaluates the type annotations it adds to RunScript, so both names
# must exist even though nothing here uses them.
import System  # noqa: F401
import Rhino  # noqa: F401
from ghpythonlib.componentbase import executingcomponent as component

#: Points read along each curve.
SAMPLES = 48


class GridRoofDrawing(component):
    def RunScript(self, file: str, openings, planters, drains):
        import Rhino.Geometry as rg
        from grid_roof import nodes

        def points(curve):
            return [curve.PointAt(t) for t in curve.DivideByCount(SAMPLES, True)]

        drawing = nodes.drawing(
            file or None,
            openings=[points(c) for c in openings if c] if openings else None,
            planters=[points(c) for c in planters if c] if planters else None,
            drains=[p for p in drains if p] if drains else None,
        )
        outlines = [rg.PolylineCurve([rg.Point3d(*p) for p in outline])
                    for outline in drawing.openings + drawing.planters]
        return drawing, outlines
