"""A drain in every planter: a bore from the pocket's floor out through the soffit.

The original planter is a blind pocket (``Voids.pockets``), and Step 4 lets the
planters soak water up, so without a way out the water stays in the soil. This
module adds the way out, on the plant branch's Step 7 (:func:`plant_steps_drained`
wraps :func:`roof_plants.plant_voids.plant_steps`), and checks it.

Why a vertical bore that is part of the pocket, and not a new outlet:

* ``keep`` unites each planter's wall, ``Shell(pocket, planter_wall)``, after
  everything is carved, so anything cut through the wall -- a bore in
  ``Voids.outlets`` included -- is filled back in (see
  :data:`roof_plants.plant_checks.DRAIN_GAP`). A bore that is *part of the
  pocket* is inside the shell instead: the shell wraps it as a sleeve
  ``planter_wall`` thick down to the soffit, so the bore stays open and the
  water cannot leak sideways into the foam.
* Straight down needs no route through the slab. A pipe across to the nearest
  roof drain would cross the foam, perhaps a beam, and the drain's own bore.
* The bore is placed off every beam band, so ``beams.core`` (united in ``keep``)
  never fills it and it never takes anything from the 500 mm a beam keeps.

The floor of a pocket is a plane, but its edge is blended into the wall over
about 120 mm, so the pocket reaches its floor height first where the floor
is widest. The bore goes there: at the point deepest inside the floor outline
(of equals, the one nearest its middle) that keeps the bore off the beams. A
small floor may be all blend -- planter 3 with ``group3_upright`` is 97 mm deep
at most, so the pocket's bottom is a dimple a few cm across -- and the bore
then takes the dimple out entirely; :func:`bore_check` reports this as
``flat = False``. One bore per separate piece of floor, so a planter whose
floor splits in two (a connected planter whose neck is narrower than twice the
floor's inset) drains both.

PROVISIONAL (2026-11-08): the bore's radius is ``brief.outlet`` (80 mm, as the
roof's own drain outlets) unless one is given. No source sets either number.
Where the water goes below the soffit (a spout, a pipe, a gutter) is not
modelled; nor is any filter layer or drainage mat in the soil.
"""

import dataclasses

import numpy as np
from compas.geometry import Frame

from compas_vol import nodes

from .design import water
from .design import voids as base_voids_step
from .kit import beam_bands
from .plant_checks import all_ok, planter_rows, plan_distance
from .plant_voids import plant_steps, planter_floors

__all__ = ["EDGE", "BELOW", "Bore", "gap_to_beams", "drain_points", "planter_drains", "bore_field", "drained_voids",
           "plant_steps_drained", "bore_check", "drain_rows", "drained_planter_rows", "all_ok_drained", "drain_table"]

#: The blend of the floor into the wall, mm: a bore with ``radius + EDGE`` of floor around it opens in a flat floor.
EDGE = 120.0

#: How far below the soffit (z = 0) the bore runs, so it opens cleanly through the bottom face.
BELOW = 200.0


@dataclasses.dataclass(frozen=True)
class Bore:
    """One planter drain: a vertical bore at ``(x, y)``, from ``top`` down through the soffit."""

    x: float
    y: float
    radius: float
    top: float          # the floor height of its pocket
    inset: float = 0.0  # how far inside the floor outline its axis is

    def to_dict(self):
        return dataclasses.asdict(self)


def _beam_gap(brief, x, y):
    """Plan distance from points to the nearest beam band (0 inside one)."""
    gap = np.full(np.broadcast_shapes(np.shape(x), np.shape(y)), np.inf)
    for lo, hi in beam_bands(brief.grid_x, brief.beam, 0, brief.length):
        gap = np.minimum(gap, np.maximum(np.maximum(lo - x, x - hi), 0.0))
    for lo, hi in beam_bands(brief.grid_y, brief.beam, 0, brief.width):
        gap = np.minimum(gap, np.maximum(np.maximum(lo - y, y - hi), 0.0))
    return gap


def gap_to_beams(brief, x, y, radius):
    """Plan gap from the edge of a bore of ``radius`` at ``(x, y)`` to the nearest beam band.

    The one rule for both placing a bore and checking it: a bore is clear of the beams when this is > 0.
    """
    return _beam_gap(brief, x, y) - radius


def drain_points(brief, outline, spec, radius=None, step=25.0):
    """Where a planter's bores go, in plan: one ``(x, y, inset)`` per separate piece of its floor.

    The floor is the outline grown by ``spec["offset"]``. In each piece the bore
    takes the point deepest inside the floor (``inset`` mm) among the points
    where :func:`gap_to_beams` is > 0, the rule :func:`bore_check` checks.

    Raises ``ValueError`` if a piece of floor lies all on a beam; the message says which.
    """
    from scipy import ndimage

    radius = brief.outlet if radius is None else radius
    points = np.array(outline)[:, :2]
    margin = max(spec["offset"], 0.0) + step
    gx = np.arange(points[:, 0].min() - margin, points[:, 0].max() + margin + step, step)
    gy = np.arange(points[:, 1].min() - margin, points[:, 1].max() + margin + step, step)
    depth = spec["offset"] - plan_distance(outline, gx, gy)     # how far inside the floor, > 0 inside
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    floor = depth > 0
    if not floor.any():
        raise ValueError("planter {!r}: no floor left at an offset of {} mm".format(spec["id"], spec["offset"]))
    pieces, count = ndimage.label(floor)
    allowed = gap_to_beams(brief, X, Y, radius) > 0
    result = []
    for n in range(1, count + 1):
        here = (pieces == n) & allowed
        if not here.any():
            raise ValueError("planter {!r}: a piece of its floor ({:.2f} m2) has no point {} mm clear of the beams "
                             "for a bore".format(spec["id"], (pieces == n).sum() * step * step / 1e6, radius))
        deepest = here & (depth >= depth[here].max() - step / 2)       # ties: the one nearest the middle
        cx, cy = X[pieces == n].mean(), Y[pieces == n].mean()
        best = np.argmin(np.where(deepest, np.hypot(X - cx, Y - cy), np.inf))
        result.append((float(X.flat[best]), float(Y.flat[best]), float(depth.flat[best])))
    return result


def planter_drains(brief, drawing, specs, deck, radius=None):
    """Every planter's bores, in drawing order: a list of :class:`Bore` per planter.

    Deterministic, so a check can rebuild the same bores the step cut.
    """
    radius = brief.outlet if radius is None else float(radius)
    floors = planter_floors(brief, drawing, specs, deck)
    return [[Bore(x, y, radius, float(floor), inset) for x, y, inset in drain_points(brief, outline, spec, radius)]
            for outline, spec, floor in zip(drawing.planters, specs, floors)]


def bore_field(bore, overlap=50.0):
    """The bore as a solid: from ``overlap`` above the floor to :data:`BELOW` under the soffit."""
    z0, z1 = -BELOW, bore.top + overlap
    return nodes.cylinder(Frame([bore.x, bore.y, (z0 + z1) / 2], [1, 0, 0], [0, 1, 0]), bore.radius, z1 - z0)


def drained_voids(brief, drawing, slab, specs, made, radius=None):
    """``made`` (the result of a Step 7) with each planter's bores united into its pocket."""
    if len(made.pockets) != len(drawing.planters):
        raise ValueError("{} pockets for {} planters".format(len(made.pockets), len(drawing.planters)))
    drains = planter_drains(brief, drawing, specs, getattr(slab, "deck", None), radius)
    pockets = [nodes.boolean([p] + [bore_field(b) for b in bores], "union", 0)
               for p, bores in zip(made.pockets, drains)]
    return dataclasses.replace(made, pockets=pockets)


def plant_steps_drained(brief, specs, base_water=water, base_voids=base_voids_step, radius=None):
    """:func:`roof_plants.plant_voids.plant_steps`, with a drain bore in every planter.

    Use as ``roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))``.
    The water step is the planted one, unchanged: the bores do not change the deck.
    """
    steps = plant_steps(brief, specs, base_water, base_voids)
    planted_voids = steps["voids"]

    def voids_step(brief_, drawing, slab):
        return drained_voids(brief_, drawing, slab, specs, planted_voids(brief_, drawing, slab), radius)

    return dict(steps, voids=voids_step)


def bore_check(brief, bore, built, dz=10.0, ring=8):
    """Is one bore open from the pocket to the soffit, in the design and in what is kept?

    Samples ``design.roof``, ``design.drawn`` and ``keep`` on the bore's axis and
    on a ring at half its radius, every ``dz`` from 20 mm above its floor down
    to 5 mm above the soffit. A point is open where all three fields are > 0.

    Returns
    -------
    dict
        ``x``, ``y``, ``radius``, ``floor_z``; ``inset`` and ``flat`` (whether ``inset`` leaves
        ``radius + EDGE`` of floor around the bore, so it opens in a flat floor; reported only);
        ``open_fraction`` (of the samples);
        ``first_blocked_z`` (the highest blocked sample, ``None`` if none);
        ``gap_to_beam`` (plan gap from the bore's edge to the nearest beam band,
        > 0 means it takes nothing from a beam); ``ok``.
    """
    angles = np.linspace(0, 2 * np.pi, ring, endpoint=False)
    px = np.concatenate([[bore.x], bore.x + 0.5 * bore.radius * np.cos(angles)])
    py = np.concatenate([[bore.y], bore.y + 0.5 * bore.radius * np.sin(angles)])
    zs = np.arange(bore.top + 20.0, 5.0 - 1e-9, -dz)
    X, Z = np.meshgrid(px, zs, indexing="ij")
    Y = np.broadcast_to(py[:, None], X.shape)
    open_ = np.ones(X.shape, dtype=bool)
    for field in (built.design.roof, built.design.drawn, built.keep):
        open_ &= field.get_distance_numpy(X, Y, Z) > 0
    blocked = ~open_.all(axis=0)
    gap = float(gap_to_beams(brief, np.array(bore.x), np.array(bore.y), bore.radius))
    return {"x": bore.x, "y": bore.y, "radius": bore.radius, "floor_z": bore.top, "inset": bore.inset,
            "flat": bool(bore.inset >= bore.radius + EDGE), "open_fraction": float(open_.mean()),
            "first_blocked_z": float(zs[np.argmax(blocked)]) if blocked.any() else None,
            "gap_to_beam": gap, "ok": bool(open_.all() and gap > 0)}


def drain_rows(brief, drawing, specs, built, radius=None):
    """One row per planter: how many bores it has, and whether every one is open. A list of rows."""
    drains = planter_drains(brief, drawing, specs, built.slab.deck, radius)
    rows = []
    for n, (spec, bores) in enumerate(zip(specs, drains)):
        checks = [bore_check(brief, b, built) for b in bores]
        rows.append({"planter": n, "plant": spec["id"], "bores": len(checks),
                     "open_fraction_min": min(c["open_fraction"] for c in checks),
                     "gap_to_beam_min": min(c["gap_to_beam"] for c in checks),
                     "radius": checks[0]["radius"], "positions": [(c["x"], c["y"]) for c in checks],
                     "flat": all(c["flat"] for c in checks),
                     "ok": bool(checks) and all(c["ok"] for c in checks)})
    return rows


def drained_planter_rows(brief, drawing, specs, built, radius=None, **kwargs):
    """:func:`roof_plants.plant_checks.planter_rows` for a roof built with :func:`plant_steps_drained`.

    ``floor_check`` measures the kept wall in columns under the floor, and a
    bore is a column with no wall by design. So the bores are filled back into
    ``keep`` for that check only -- the wall is checked everywhere *else* --
    and :func:`drain_rows` checks the bores themselves, on the real ``keep``.
    """
    bores = [bore_field(b) for planter in planter_drains(brief, drawing, specs, built.slab.deck, radius)
             for b in planter]
    patched = dataclasses.replace(built, keep=nodes.boolean([built.keep] + bores, "union", 0))
    return planter_rows(brief, drawing, specs, patched, **kwargs)


def all_ok_drained(rows, water, drains):
    """:func:`roof_plants.plant_checks.all_ok`, and every planter drains."""
    return all_ok(rows, water) and all(row["ok"] for row in drains)


def drain_table(drains):
    """The drain rows as a fixed-width text table, in mm."""
    head = ["P", "plant", "bores", "radius", "flat", "open", "beam_gap", "ok"]
    grid = [head] + [[str(r["planter"]), r["plant"], str(r["bores"]), "{:.0f}".format(r["radius"]), str(r["flat"]),
                      "{:.0%}".format(r["open_fraction_min"]), "{:.0f}".format(r["gap_to_beam_min"]), str(r["ok"])]
                     for r in drains]
    widths = [max(len(line[i]) for line in grid) for i in range(len(head))]
    return "\n".join("  ".join(t.ljust(w) for t, w in zip(line, widths)).rstrip() for line in grid)
