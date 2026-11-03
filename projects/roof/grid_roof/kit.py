"""A slab on a beam grid, cut into the parts it would be built from."""

import math

from compas_vol.assembly import place_cuts
from compas_vol.assembly import section_cost
from compas_vol.meshing import normalize_bounds

__all__ = ["beam_bands", "grid_kit"]


def beam_bands(lines, width, low, high):
    """Each beam's extent across its width: centred on its grid line, held inboard
    at the slab's edge.

    Parameters
    ----------
    lines : sequence[float]
        Grid line positions along one axis.
    width : float
        Beam width.
    low, high : float
        The slab's extent along that axis.

    Returns
    -------
    list[tuple[float, float]]

    Examples
    --------
    >>> beam_bands([0, 6000, 12000], 600, 0, 12000)
    [(0.0, 600.0), (5700.0, 6300.0), (11400.0, 12000.0)]
    """
    bands = []
    for line in sorted(float(v) for v in lines):
        lo, hi = line - width / 2.0, line + width / 2.0
        if lo < low:
            lo, hi = low, low + width
        if hi > high:
            lo, hi = high - width, high
        bands.append((float(lo), float(hi)))
    for (_, a), (b, _) in zip(bands[:-1], bands[1:]):
        if b < a - 1e-9:
            raise ValueError("Beams overlap: grid lines closer together than the beam width.")
    return bands


def _gaps(bands, low, high):
    """The spans between bands, and either side of them."""
    edges = [low] + [v for band in bands for v in band] + [high]
    return [(a, b) for a, b in zip(edges[0::2], edges[1::2]) if b - a > 1e-9]


def grid_kit(bounds, xlines, ylines, width, panel, beam=None, model=None, shift=0.0, step=None):
    """Cut a slab on a beam grid into nodes, whole beams and panels.

    Nodes sit where beams cross; beams run whole between nodes, with no joint at
    mid-span; panels fill each bay, divided where larger than ``panel``. With
    ``model`` and ``shift``, each panel cut moves to where it meets the most
    material (:func:`compas_vol.assembly.place_cuts`).

    Parameters
    ----------
    bounds : sequence[float]
        The slab's extent. Every piece spans its full height.
    xlines, ylines : sequence[float]
        Beam centre lines: ``xlines`` are positions along X of beams running
        in Y, and ``ylines`` the other way. A line on the edge of the slab
        gives an edge beam held inboard, flush with the edge.
    width : float
        Beam width.
    panel : float | tuple[float, float]
        Largest panel, along X and Y: a transport or a machine limit.
    beam : float, optional
        Longest beam piece. Beams longer than this are divided too.
    model : :class:`compas_vol.base.VolObject`, optional
        The design, to place the dividing cuts by.
    shift : float
        How far a dividing cut may move from an even split.
    step : float, optional
        Candidate spacing and section sample spacing. Defaults to a tenth of
        ``shift``.

    Returns
    -------
    list[dict]
        One per piece: ``bounds``, ``role`` (``"node"``, ``"beam"`` or
        ``"panel"``) and ``name``, ready for
        :func:`compas_vol.assembly.segment` ``(cells=...)``.

    Examples
    --------
    An 18 by 12 m slab on a 6 m grid, with 600 mm beams and panels no larger
    than 3 m:

    >>> from grid_roof import grid_kit
    >>> cells = grid_kit((0, 0, 0, 18000, 12000, 600), [0, 6000, 12000, 18000], [0, 6000, 12000], 600, 3000)
    >>> roles = [cell["role"] for cell in cells]
    >>> roles.count("node"), roles.count("beam"), roles.count("panel")
    (12, 17, 24)
    >>> panels = [c["bounds"] for c in cells if c["role"] == "panel"]
    >>> max(max(b[3] - b[0], b[4] - b[1]) for b in panels)
    2700.0
    """
    x0, y0, z0, x1, y1, z1 = normalize_bounds(bounds)
    width = float(width)
    px, py = (float(panel), float(panel)) if isinstance(panel, (int, float)) else (float(panel[0]), float(panel[1]))
    step = float(step) if step else (shift / 10.0 if shift else None)

    xbands, ybands = beam_bands(xlines, width, x0, x1), beam_bands(ylines, width, y0, y1)
    xbays, ybays = _gaps(xbands, x0, x1), _gaps(ybands, y0, y1)

    def divide(lo, hi, size, axis, across):
        """Cuts along `axis` between lo and hi, measured over `across` on the other plan axis."""
        cost = None
        if model is not None and shift > 0:
            # The plane is perpendicular to `axis`; its other two axes are the
            # other plan axis and Z, in that order for both X and Y cuts.
            rect = (across[0], z0, across[1], z1)

            def cost(position):
                return section_cost(model, axis, position, rect, step)

        edges = [lo] + place_cuts(lo, hi, size, cost, shift, step) + [hi]
        return list(zip(edges[:-1], edges[1:]))

    cells = []
    for i, (xa, xb) in enumerate(xbands):
        for j, (ya, yb) in enumerate(ybands):
            cells.append({"bounds": (xa, ya, z0, xb, yb, z1), "role": "node", "name": "node_{}_{}".format(i, j)})

    longest = float(beam) if beam else math.inf
    for j, (ya, yb) in enumerate(ybands):
        for i, (xa, xb) in enumerate(xbays):
            for k, (a, b) in enumerate(divide(xa, xb, longest, 0, (ya, yb))):
                name = "beam_x{}_{}_{}".format(j, i, k)
                cells.append({"bounds": (a, ya, z0, b, yb, z1), "role": "beam", "name": name})
    for i, (xa, xb) in enumerate(xbands):
        for j, (ya, yb) in enumerate(ybays):
            for k, (a, b) in enumerate(divide(ya, yb, longest, 1, (xa, xb))):
                name = "beam_y{}_{}_{}".format(i, j, k)
                cells.append({"bounds": (xa, a, z0, xb, b, z1), "role": "beam", "name": name})

    for i, (xa, xb) in enumerate(xbays):
        for j, (ya, yb) in enumerate(ybays):
            for m, (a, b) in enumerate(divide(xa, xb, px, 0, (ya, yb))):
                for n, (c, d) in enumerate(divide(ya, yb, py, 1, (a, b))):
                    name = "panel_{}_{}_{}{}".format(i, j, m, n)
                    cells.append({"bounds": (a, c, z0, b, d, z1), "role": "panel", "name": name})
    return cells
