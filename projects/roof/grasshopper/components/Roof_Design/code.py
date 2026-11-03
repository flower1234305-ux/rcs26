"""
Every design step, from beams to the kit of parts, as one component. Mesh
design over bounds with Volumetric Mesh to see it; the weathering happens per
piece, in Roof Piece.

    Args:
        brief: From Roof Brief.
        drawing: From Roof Drawing.
        run: False holds the last result while you change things upstream. Unwired, it runs.
    Returns:
        roof: Every step's result, for Roof Piece.
        design: The designed roof, before weathering: a volumetric object for Volumetric Mesh.
        bounds: The roof's box, for Volumetric Mesh.
        pieces: The kit of parts, one box per piece.
        names: Each piece's name, in the order of pieces, for Roof Piece.
        report: What the checks say: water, light, kit.
"""
# Rhino 8 evaluates the type annotations it adds to RunScript, so both names
# must exist even though nothing here uses them.
import System  # noqa: F401
import Rhino  # noqa: F401
from ghpythonlib.componentbase import executingcomponent as component


def box(bounds):
    import Rhino.Geometry as rg

    x0, y0, z0, x1, y1, z1 = bounds
    return rg.Box(rg.BoundingBox(rg.Point3d(x0, y0, z0), rg.Point3d(x1, y1, z1)))


class GridRoofDesign(component):
    def RunScript(self, brief, drawing, run: bool):
        from grid_roof import nodes

        # The script instance survives between solutions, so it can hold a result.
        if run is not False and brief is not None and drawing is not None:
            built = nodes.design(brief, drawing)
            listed = nodes.pieces(built)
            self.held = (
                built,
                built.design.roof,
                box(brief.bounds),
                [box(b) for _, b in listed],
                [name for name, _ in listed],
                nodes.report(built, brief, drawing),
            )
        return getattr(self, "held", (None,) * 6)
