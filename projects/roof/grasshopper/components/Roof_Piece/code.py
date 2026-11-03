"""
One piece of the kit, weathered and jointed, as a Rhino mesh. A few seconds
at 40 mm voxels; minutes at the 10 to 15 mm a print needs, so set run to
False while you change things upstream.

    Args:
        roof: From Roof Design.
        brief: The same brief Roof Design used.
        name: A piece's name, from Roof Design's names. Defaults to the first.
        voxel: Sample spacing, mm. Defaults to the brief's. 40 to look, 10 to 15 to make.
        run: False holds the last result while you change things upstream. Unwired, it runs.
    Returns:
        mesh: The piece, weathered, with its dowel sockets.
        report: Size, dowels, triangles, watertight, and beam depth for nodes and beams.
"""
# Rhino 8 evaluates the type annotations it adds to RunScript, so both names
# must exist even though nothing here uses them.
import System  # noqa: F401
import Rhino  # noqa: F401
from ghpythonlib.componentbase import executingcomponent as component


class GridRoofPiece(component):
    def RunScript(self, roof, brief, name: str, voxel: float, run: bool):
        from compas_vol.ghpython import mesh_to_rhino
        from grid_roof import nodes

        # The script instance survives between solutions, so it can hold a result.
        if run is not False and roof is not None and brief is not None:
            name = name or nodes.pieces(roof)[0][0]
            vertices, faces, report = nodes.piece(roof, brief, name, voxel)
            self.held = (mesh_to_rhino(vertices, faces), report)
        return getattr(self, "held", (None, None))
