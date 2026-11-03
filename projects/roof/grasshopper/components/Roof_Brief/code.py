"""
Every number the roof depends on. Unwired inputs keep the defaults, or the
values in file; the rest of the brief (grid, water, fabrication) comes from
there too.

    Args:
        file: A brief.json, as the notebook saves it. Optional.
        beam: Beam width, mm. Default 600.
        beam_depth: Depth every beam keeps, mm. Default 500.
        skin: Solid deck over the pores, mm. Default 120.
        pore: Pore to pore, mm. Default 700.
        fraction_soffit: Solid share at the soffit, 0 to 1. Default 0.42.
        opening_flare: How much wider a light opening is at the faces, mm. Default 260.
        planter_depth: Planter soil depth, mm. Default 350.
        panel: Largest panel, mm. Default 3000.
        voxel: Sample spacing, mm: 40 to look, 10 to 15 to make. Default 40.
    Returns:
        brief: The brief, for Roof Design and Roof Piece.
        numbers: Every number in the brief, one per line.
"""
# Rhino 8 evaluates the type annotations it adds to RunScript, so both names
# must exist even though nothing here uses them.
import System  # noqa: F401
import Rhino  # noqa: F401
from ghpythonlib.componentbase import executingcomponent as component


class GridRoofBrief(component):
    def RunScript(
        self,
        file: str,
        beam: float,
        beam_depth: float,
        skin: float,
        pore: float,
        fraction_soffit: float,
        opening_flare: float,
        planter_depth: float,
        panel: float,
        voxel: float,
    ):
        from grid_roof import nodes

        brief = nodes.brief(
            file or None, beam=beam, beam_depth=beam_depth, skin=skin, pore=pore, fraction_soffit=fraction_soffit,
            opening_flare=opening_flare, planter_depth=planter_depth, panel=panel, voxel=voxel,
        )
        return brief, "\n".join("{}: {}".format(k, v) for k, v in brief.to_dict().items())
