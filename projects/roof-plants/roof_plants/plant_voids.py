"""Step 7 with one opening per plant: the adapter between :mod:`roof_plants.plants` and :mod:`roof_plants.design`.

Plugs into :func:`roof_plants.design.design_roof` through its ``steps`` and copies
none of them: the light openings and outlets still come from
:func:`roof_plants.design.voids`, so another feature's change to them carries over.

Sign of the offset, checked in ``compas_vol.modifications.Offset``: a positive
distance grows the solid outward, a negative one shrinks it. The pocket is the
solid that is cut away, so ``offset > 0`` widens the planter opening and
``offset < 0`` narrows it.
"""

import dataclasses

import numpy as np
from compas.geometry import Plane, Polyline

from compas_vol.combinations import SmoothIntersection
from compas_vol.modifications import Offset, Remap
from compas_vol.primitives import VolPlane

from .design import region, voids, water
from .plants import check_control, check_fit, floor_height

__all__ = ["pocket", "voids_by_plant", "offset_outline", "water_drawing", "plant_steps", "deck_min",
           "planter_floors"]


def deck_min(deck, outline, grow, step):
    """The lowest deck height inside an outline grown by ``grow`` mm.

    ``deck`` is anything with ``height_at(x, y)``, as ``Slab.deck``. Samples
    sit on multiples of ``step``, so with a step that divides ``plan_cell`` they
    include the deck's own grid points, where a narrow channel bed is lowest.
    """
    points = np.array(outline)[:, :2]
    reach = max(grow, 0.0) + step
    lo, hi = np.floor((points.min(axis=0) - reach) / step), np.ceil((points.max(axis=0) + reach) / step)
    gx, gy = step * np.arange(lo[0], hi[0] + 1), step * np.arange(lo[1], hi[1] + 1)
    inside = region(outline, -1e4, 1e4).get_distance_numpy(gx[:, None, None], gy[None, :, None],
                                                           np.zeros((1, 1, 1)))[:, :, 0] < grow
    if not inside.any():
        raise ValueError("nothing left of the outline at a growth of {} mm".format(grow))
    x, y = np.meshgrid(gx, gy, indexing="ij")
    return float(deck.height_at(x[inside], y[inside]).min())


def planter_floors(brief, drawing, specs, deck):
    """Each planter's floor height, measured as its ``depth_datum`` says.

    ``local_min`` reads the deck inside the top outline (``offset + rim``, the
    drawn outline at z = t). The opening really cut at the deck is a little
    smaller, because the deck lies below t, but its size depends on the floor
    being found here; the top outline contains it and needs no iteration.
    Samples at half of ``plan_cell``, so the deck's own grid points are among them.
    """
    step = brief.plan_cell / 2
    return [floor_height(spec, brief.thickness,
                         deck_min(deck, o, spec["top"], step) if spec["depth_datum"] == "local_min" else None)
            for o, spec in zip(drawing.planters, specs)]


def pocket(brief, outline, spec, floor=None):
    """One planter pocket, as :func:`roof_plants.design.voids` makes it, with this planter's own numbers.

    The outline is grown by ``offset`` at the floor and by ``offset + rim``
    at the top of the slab; in between it eases smoothly, as the original rim.
    ``floor`` is the flat floor's height, by default ``depth`` below the slab's top.
    """
    t = brief.thickness
    floor = t - spec["depth"] if floor is None else floor
    growth = Remap(VolPlane(Plane([0, 0, floor], [0, 0, 1])), (0.0, t - floor),
                   (spec["offset"], spec["offset"] + spec["rim"]), "smooth")
    above = VolPlane(Plane([0, 0, floor], [0, 0, -1]))
    return SmoothIntersection(Offset(region(outline, -500, t + 500), growth), above, 120.0)


def voids_by_plant(brief, drawing, slab, specs, base=voids):
    """Step 7, each planter cut for the plant in it.

    ``specs`` is one :func:`roof_plants.plants.opening_spec` result per planter,
    in drawing order. Everything else comes from ``base``; pass another step
    there to stack this on top of another feature's Step 7. The pockets ``base``
    made are replaced, one for one: their shapes are lost.

    Raises :class:`roof_plants.plants.PlanterFitError` if a planter does not fit
    over the soffit. This runs just after Step 4, before the heavy steps. Raises
    ``ValueError`` if ``base`` made other than one pocket per planter, because
    replacing them would then lose a pocket with no planter to rebuild it from.
    """
    if len(specs) != len(drawing.planters):
        raise ValueError("{} specs for {} planters".format(len(specs), len(drawing.planters)))
    floors = planter_floors(brief, drawing, specs, getattr(slab, "deck", None))
    check_fit(specs, floors, brief.planter_wall)
    pockets = [pocket(brief, o, spec, floor) for o, spec, floor in zip(drawing.planters, specs, floors)]
    made = base(brief, drawing, slab)
    if len(made.pockets) != len(drawing.planters):
        raise ValueError("the base step made {} pockets for {} planters; replacing them would lose some".format(
            len(made.pockets), len(drawing.planters)))
    return dataclasses.replace(made, pockets=pockets)


def offset_outline(outline, distance, step=10.0):
    """A plan outline grown (+) or shrunk (-) by ``distance`` mm, as a closed :class:`Polyline`.

    Read off the exact 2D distance field of the outline (the 0-level of
    ``region(outline) - distance``), so corners round as a true offset does.
    Raises ``ValueError`` if the result is empty or splits into pieces.
    """
    import contourpy

    if distance == 0:
        return Polyline([list(p) for p in outline])
    points = np.array(outline)[:, :2]
    margin = max(distance, 0) + 4 * step
    gx = np.arange(points[:, 0].min() - margin, points[:, 0].max() + margin + step, step)
    gy = np.arange(points[:, 1].min() - margin, points[:, 1].max() + margin + step, step)
    field = region(outline, -1e4, 1e4).get_distance_numpy(gx[:, None, None], gy[None, :, None],
                                                          np.zeros((1, 1, 1)))[:, :, 0]
    lines = contourpy.contour_generator(gx, gy, field.T).lines(distance)
    if len(lines) != 1:
        raise ValueError("offsetting by {} mm gives {} loops, expected 1".format(distance, len(lines)))
    loop = [[float(x), float(y), 0.0] for x, y in lines[0]]
    if loop[0] != loop[-1]:
        loop.append(loop[0])
    return Polyline(loop)


def water_drawing(drawing, specs):
    """The drawing Step 4 (water) should see: each planter as its floor outline, grown by ``offset``.

    Step 4 treats a planter outline as a region that soaks water up. The
    original passes the drawn outline, which is the pocket's floor outline
    (the rim flares beyond it); here the same convention is kept. With every
    ``offset`` at 0 the deck is the original's. Any other ``offset`` changes how
    water runs across the whole roof, so the deck over an unchanged planter can
    change too; only that planter's pocket is sure to stay as it was.
    """
    if len(specs) != len(drawing.planters):
        raise ValueError("{} specs for {} planters".format(len(specs), len(drawing.planters)))
    planters = [offset_outline(o, spec["offset"]) for o, spec in zip(drawing.planters, specs)]
    return dataclasses.replace(drawing, planters=planters)


def plant_steps(brief, specs, base_water=water, base_voids=voids):
    """The ``steps`` that make :func:`roof_plants.design.design_roof` a planted roof.

    ``base_water`` and ``base_voids`` are what the planted steps wrap, so they
    can sit on top of another feature's steps. Use as
    ``roof.design_roof(brief, drawing, steps=plant_steps(brief, specs))``.

    Raises :class:`roof_plants.plants.PlanterFitError` at once if a planter could
    not fit even under a deck at the slab's full height, and ``ValueError`` if a
    ``control`` planter is not the one this brief gives the original roof.
    """
    check_control(specs, brief)
    check_fit(specs, [brief.thickness - spec["depth"] for spec in specs], brief.planter_wall)

    def water_step(brief_, drawing, beams):
        return base_water(brief_, water_drawing(drawing, specs), beams)

    def voids_step(brief_, drawing, slab):
        return voids_by_plant(brief_, drawing, slab, specs, base_voids)

    return {"water": water_step, "voids": voids_step}
