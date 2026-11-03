"""The roof as Grasshopper components, without Grasshopper: one function each.

Each takes its component's inputs by name, as plain Python or COMPAS values,
so a component's ``code.py`` only converts Rhino objects and calls one of
these. Points can be anything with ``X``, ``Y``, ``Z`` (a Rhino point) or a
sequence of two or three numbers.
"""

from compas.geometry import Point, Polyline

from .brief import Brief
from .checks import beam_depth, clear_apertures
from .design import design_roof
from .drawing import Drawing

__all__ = ["brief", "drawing", "design", "report", "pieces", "piece"]


def brief(file=None, **numbers):
    """The brief: the defaults, or ``file``, with every number given replacing its own.

    Examples
    --------
    >>> brief(pore=500, voxel=None).pore
    500.0
    >>> brief(colour=3)
    Traceback (most recent call last):
    ...
    ValueError: Not in the brief: colour
    """
    result = Brief.load(file) if file else Brief()
    for name, value in numbers.items():
        if not hasattr(result, name):
            raise ValueError("Not in the brief: {}".format(name))
        if value is not None:
            setattr(result, name, float(value))
    return result


def _point(p):
    if hasattr(p, "X"):
        return [float(p.X), float(p.Y), float(p.Z)]
    coordinates = [float(c) for c in p]
    return (coordinates + [0.0])[:3]


def _outline(points):
    points = [_point(p) for p in points]
    if points[0] != points[-1]:
        points.append(points[0])
    return Polyline(points)


def drawing(file=None, openings=None, planters=None, drains=None):
    """The drawing: ``file`` or the sample, with each part given replacing its own.

    ``openings`` and ``planters`` are outlines, each a list of points;
    ``drains`` is a list of points. Outlines are closed for you.

    Examples
    --------
    >>> square = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
    >>> d = drawing(openings=[square])
    >>> len(d.openings), len(d.planters), d.openings[0][0] == d.openings[0][-1]
    (1, 4, True)
    """
    result = Drawing.load(file) if file else Drawing.sample()
    if openings is not None:
        result.openings = [_outline(o) for o in openings]
    if planters is not None:
        result.planters = [_outline(p) for p in planters]
    if drains is not None:
        result.drains = [Point(*_point(p)) for p in drains]
    return result


def design(brief, drawing):
    """Every design step, as :func:`grid_roof.design_roof`."""
    return design_roof(brief, drawing)


def report(built, brief, drawing):
    """What the checks say about a design, one line each."""
    water = built.incision.summary()
    lines = ["water: {:.0f} m of channel, {} of {} outlets reached, {} puddles, {} cells with nowhere to drain".format(
        water["channel_length"] / 1000, water["outlets_used"], water["outlets"], water["reverse_falls"],
        water["stranded"])]
    for n, aperture in enumerate(clear_apertures(brief, drawing, built.design.roof)):
        lines.append("opening {}: drawn {:.2f} m2, clear {:.2f} m2".format(n, aperture["drawn"], aperture["clear"]))
    roles = [p.role for p in built.assembly]
    lines.append("kit: {} pieces: {} nodes, {} beams, {} panels".format(
        len(roles), roles.count("node"), roles.count("beam"), roles.count("panel")))
    return "\n".join(lines)


def pieces(built):
    """Each piece's ``(name, bounds)``, bounds as ``(xmin, ymin, zmin, xmax, ymax, zmax)``."""
    return [(p.name, tuple(float(v) for v in p.bounds)) for p in built.assembly]


def piece(built, brief, name, voxel=None):
    """One piece, weathered and jointed: ``(vertices, faces, report)``.

    ``voxel`` overrides the brief's, in mm: 40 to look, 10 to 15 to make.
    """
    from compas_vol import nodes
    from compas_vol.meshing import is_watertight

    names = [p.name for p in built.assembly]
    if name not in names:
        raise ValueError("No piece {!r}; the kit has {}".format(name, ", ".join(names)))
    target = built.assembly.find(name)
    voxel = float(voxel or brief.voxel)
    _, finished, processed = next(built.assembly.build(built.weathering, voxel, brief.halo, pieces=[target]))
    vertices, faces = nodes.mesh(finished.to_volume(), None, None, 0)
    size = " x ".join("{:.0f}".format(v) for v in target.size)
    lines = ["{}: {} mm, {} dowels, {:,} triangles at {:.0f} mm, watertight {}".format(
        name, size, len(target.joints), len(faces), voxel, is_watertight(vertices, faces))]
    if target.role in ("node", "beam"):
        lines.append("least beam depth: {:.0f} mm".format(beam_depth(processed, built.beams, target.bounds)))
    return vertices, faces, "\n".join(lines)
