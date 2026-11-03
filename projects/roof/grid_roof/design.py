"""The roof's components: one function per step, each a group on the canvas.

Each step takes the brief and what the steps before it produced, and returns
what the steps after it need -- inputs and outputs, as a Grasshopper component
has. They are built from compas_vol's own components (``compas_vol.nodes``)
wherever one exists, so a step written out on a canvas gives the same field.
:func:`design_roof` runs them all, the way a cluster collapses a group.
"""

from dataclasses import dataclass

import numpy as np
from compas.geometry import Frame, Plane

from compas_vol import nodes
from compas_vol.assembly import Pins, segment
from compas_vol.combinations import Intersection, SmoothIntersection, Subtraction
from compas_vol.modifications import Offset, Remap, Shell
from compas_vol.primitives import VolExtrusion, VolPlane
from compas_vol.processes import abrasion, fbm, hardness, opened, pitting

from .drainage import Drainage
from .kit import beam_bands, grid_kit
from .spinodoid import Spinodoid

__all__ = [
    "Beams", "Slab", "Soffit", "Voids", "Design", "Roof",
    "beams", "water", "slab", "soffit", "voids", "carve", "keep", "design", "kit", "weathering", "design_roof",
    "box", "region", "plan_mask",
]


# ==============================================================================
# small shapes the steps share
# ==============================================================================


def box(x0, y0, z0, x1, y1, z1):
    """A box from its extent, as **Volumetric Box** takes it: a plane at its centre and three sizes."""
    centre = Frame([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2], [1, 0, 0], [0, 1, 0])
    return nodes.box(centre, x1 - x0, y1 - y0, z1 - z0, 0)


def region(outline, z0, z1):
    """A plan outline as a solid between two heights."""
    return VolExtrusion(list(outline), z1 - z0, frame=Frame([0, 0, (z0 + z1) / 2], [1, 0, 0], [0, 1, 0]))


def plan_mask(outlines, x, y, grow=0.0):
    """Which plan cells lie inside any of the outlines, grown by ``grow``."""
    if not outlines:
        return np.zeros(np.broadcast_shapes(np.shape(x), np.shape(y)), dtype=bool)
    zero = np.zeros((1, 1, 1))
    xs, ys = np.asarray(x)[:, :, None], np.asarray(y)[:, :, None]
    return np.any([region(o, -1, 1).get_distance_numpy(xs, ys, zero)[:, :, 0] < grow for o in outlines], axis=0)


# ==============================================================================
# the steps
# ==============================================================================


@dataclass
class Beams:
    core: object        # the solid every beam keeps
    xbands: list        # (lo, hi) across each beam running along Y
    ybands: list        # (lo, hi) across each beam running along X


def beams(brief):
    """Step 3, structure. *Canvas: Volumetric Box x 7 -> Volumetric Boolean.*

    Reads ``grid_x``, ``grid_y``, ``beam``, ``beam_depth``. Each beam is a box
    centred on its grid line, as deep as the depth it keeps; edge beams are
    held inboard, flush with the roof's edge.
    """
    xbands = beam_bands(brief.grid_x, brief.beam, 0, brief.length)
    ybands = beam_bands(brief.grid_y, brief.beam, 0, brief.width)
    parts = [box(lo, 0, 0, hi, brief.width, brief.beam_depth) for lo, hi in xbands]
    parts += [box(0, lo, 0, brief.length, hi, brief.beam_depth) for lo, hi in ybands]
    return Beams(nodes.boolean(parts, "union", 0), xbands, ybands)


def water(brief, drawing, beams):
    """Step 4, water. *Canvas: no component yet.*

    Reads ``fall``, ``relief``, ``plan_cell``, ``upstand`` and the
    ``channel_*`` fields. The deck falls to the nearest drain, routing keeps
    water off the light openings and lets the planters soak it up, and the
    channels are sized by their catchments and may not cut below the beams.

    Returns
    -------
    :class:`grid_roof.Incision`
    """
    cell = brief.plan_cell
    x, y = np.meshgrid(np.arange(int(brief.length / cell) + 1) * cell, np.arange(int(brief.width / cell) + 1) * cell,
                       indexing="ij")
    drains = [(p[0], p[1]) for p in drawing.drains]
    distance = np.min([np.hypot(x - a, y - b) for a, b in drains], axis=0)
    heights = brief.thickness - brief.fall * (distance.max() - distance)
    heights = heights + brief.relief * fbm(x, y, 0 * x, cell_size=2400, octaves=4, seed=brief.relief_seed)
    heights = np.minimum(heights, brief.thickness)

    on_beam = np.zeros(x.shape, dtype=bool)
    for lo, hi in beams.xbands:
        on_beam |= (x >= lo) & (x <= hi)
    for lo, hi in beams.ybands:
        on_beam |= (y >= lo) & (y <= hi)

    dry = ~plan_mask(drawing.openings, x, y, grow=brief.upstand)
    outlets = Drainage(heights, (0, 0), (cell, cell), drains=drains, mask=dry).drains
    routed = Drainage(heights, (0, 0), (cell, cell), drains=outlets | plan_mask(drawing.planters, x, y), mask=dry)
    floor = np.where(on_beam, brief.beam_depth, brief.thickness - brief.channel_reach)
    return routed.incise(onset=brief.channel_onset, width=brief.channel_width, depth=brief.channel_depth,
                         limit=brief.channel_limit, floor=floor, fall=0.005)


@dataclass
class Slab:
    deck: object        # the worn top surface, as a solid below it
    solid: object       # the slab: the roof outline under the deck
    flat: object        # the slab before anything happens to it


def slab(brief, incision):
    """Step 5, deck and slab. *Canvas: Volumetric Box -> Volumetric Boolean (intersection).*"""
    deck = incision.to_volume()
    outline = box(0, 0, 0, brief.length, brief.width, brief.thickness + 400)
    return Slab(deck, nodes.boolean([outline, deck], "intersection", 0),
                box(0, 0, 0, brief.length, brief.width, brief.thickness))


@dataclass
class Soffit:
    porous: object      # the slab with its pores
    deep: object        # everything more than `skin` below the deck


def soffit(brief, slab, beams):
    """Step 6, the porous soffit. *Canvas: no component yet.*

    Reads ``skin``, ``pore``, ``fraction_deck``, ``fraction_soffit``,
    ``beam_haunch``, ``foam_seed``. A foam that is solid at the deck, open at
    the soffit and closes up towards the beams; ``Intersection`` keeps the
    larger of two fields, here the denser of two fractions.
    """
    by_height = Remap(VolPlane(Plane([0, 0, 0], [0, 0, 1])), (0.0, brief.thickness - brief.skin),
                      (brief.fraction_soffit, brief.fraction_deck), "smooth")
    by_beam = Remap(beams.core, (0.0, brief.beam_haunch), (1.0, 0.0), "smooth")
    foam = Spinodoid(brief.pore, Intersection(by_height, by_beam), waves=32, seed=brief.foam_seed)
    deep = Offset(slab.deck, -brief.skin)
    return Soffit(Subtraction(slab.solid, Subtraction(deep, foam)), deep)


@dataclass
class Voids:
    openings: list      # through the full depth, flared at both faces
    pockets: list       # blind planter pockets, rims flared
    outlets: list       # a bore at each drain


def voids(brief, drawing, slab):
    """Step 7, light and planters. *Canvas: no component yet for the shapes; Volumetric Cylinder for the outlets.*

    Reads ``opening_flare``, ``planter_depth``, ``planter_rim``, ``outlet``.
    """
    t = brief.thickness
    flare = Remap(slab.flat, (-t / 2, 0.0), (0.0, brief.opening_flare), "smooth")
    openings = [Offset(region(o, -500, t + 500), flare) for o in drawing.openings]
    floor = t - brief.planter_depth
    rim = Remap(VolPlane(Plane([0, 0, floor], [0, 0, 1])), (0.0, brief.planter_depth), (0.0, brief.planter_rim),
                "smooth")
    above = VolPlane(Plane([0, 0, floor], [0, 0, -1]))
    pockets = [SmoothIntersection(Offset(region(o, -500, t + 500), rim), above, 120.0) for o in drawing.planters]
    outlets = [nodes.cylinder(Frame([p[0], p[1], t / 2], [1, 0, 0], [0, 1, 0]), brief.outlet, 2 * t)
               for p in drawing.drains]
    return Voids(openings, pockets, outlets)


def carve(solid, voids):
    """Cut the voids out of a solid. *Canvas: Volumetric Boolean (difference, with a blend).*"""
    for opening in voids.openings:
        solid = nodes.boolean([solid, opening], "difference", 60.0)
    for pocket in voids.pockets:
        solid = nodes.boolean([solid, pocket], "difference", 80.0)
    return nodes.boolean([solid] + voids.outlets, "difference", 0)


def keep(brief, beams, slab, soffit, voids):
    """Step 8, what must stay. *Canvas: Volumetric Boolean (union).*

    Reads ``planter_wall``. The beams, the deck (carved, so keeping it never
    refills an opening, a planter or an outlet), and each planter's wall and
    floor (a shell to the outside of the pocket, clipped to the slab).
    """
    deck = carve(Subtraction(slab.solid, soffit.deep), voids)
    walls = [Intersection(Shell(pocket, brief.planter_wall, 0.0), slab.solid) for pocket in voids.pockets]
    return nodes.boolean([beams.core, deck] + walls, "union", 0)


@dataclass
class Design:
    roof: object        # the design, with what must stay
    drawn: object       # the same without its foam, to place joints against


def design(slab, soffit, voids, keep):
    """The design: the carved roof united with what must stay. *Canvas: Volumetric Boolean (union).*"""
    return Design(nodes.boolean([carve(soffit.porous, voids), keep], "union", 0),
                  nodes.boolean([carve(slab.solid, voids), keep], "union", 0))


def kit(brief, design):
    """Step 10, kit of parts. *Canvas: no component yet.*

    Reads ``grid_x``, ``grid_y``, ``beam``, ``panel``, ``cut_shift``,
    ``clearance``, ``dowel``, ``dowel_fit``. Nodes, whole beams and panels; panel joints are
    placed against ``design.drawn``.

    Returns
    -------
    :class:`compas_vol.assembly.Assembly`
    """
    cells = grid_kit(brief.bounds, brief.grid_x, brief.grid_y, brief.beam, brief.panel, model=design.drawn,
                     shift=brief.cut_shift, step=50.0)
    pins = Pins(diameter=brief.dowel, depth=80.0, fit=brief.dowel_fit, spacing=700.0, margin=60.0, limit=3)
    return segment(design.roof, brief.bounds, cells=cells, clearance=brief.clearance, joint=pins)


def weathering(brief, keep, slab):
    """Step 11, the process each piece goes through. *Canvas: Volumetric Pitting -> Abrasion -> Morphology.*

    Reads ``erosion_margin``, ``skin``, ``pit_depth``, ``wear``,
    ``min_feature``, ``hardness_seed``, ``voxel``. Returns ``process(field)``
    for :meth:`compas_vol.assembly.Assembly.build`. ``keep`` is a constraint,
    so no step can take a beam, the deck or a planter wall away, and erosion
    fades out as it approaches them. Pitting stays out of the rock just
    under the deck; abrasion wears every edge; opening removes anything
    thinner than ``min_feature``.
    """
    length = max(120.0, 3 * brief.voxel)          # curvature is measured against a real length

    def process(field):
        field = field.constrain(keep=keep, margin=brief.erosion_margin)
        x, y, z = field.coordinates()
        under_deck = slab.deck.height_at(x, y) - z < brief.skin + 60.0
        resistance = np.where(under_deck, 1.0, hardness(field, cell_size=900.0, octaves=4, seed=brief.hardness_seed))
        field = pitting(field, resistance=resistance, depth=brief.pit_depth, length=length, threshold=0.1,
                        feedback=1.4)
        field = abrasion(field, depth=brief.wear, length=1.5 * length, edge_bias=1.5)
        return opened(field, brief.min_feature / 2)

    return process


# ==============================================================================
# the cluster
# ==============================================================================


@dataclass
class Roof:
    beams: Beams
    incision: object
    slab: Slab
    soffit: Soffit
    voids: Voids
    keep: object
    design: Design
    assembly: object
    weathering: object


def design_roof(brief, drawing):
    """Every step, in order: the whole definition as one call.

    Returns
    -------
    :class:`Roof`
        Each step's output, by name.
    """
    b = beams(brief)
    incision = water(brief, drawing, b)
    s = slab(brief, incision)
    f = soffit(brief, s, b)
    v = voids(brief, drawing, s)
    k = keep(brief, b, s, f, v)
    d = design(s, f, v, k)
    return Roof(b, incision, s, f, v, k, d, kit(brief, d), weathering(brief, k, s))
