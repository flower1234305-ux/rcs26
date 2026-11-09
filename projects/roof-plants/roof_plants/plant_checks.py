"""The checks for plant-sized planters, read off the fields: no meshing needed.

Each check returns its numbers and an ``ok``. A check that fails does not raise,
so the table shows every planter at once; :func:`roof_plants.plants.check_fit` is
the one rule that stops the run, because nothing after it could be built.
"""

import numpy as np

from .design import region
from .plant_voids import offset_outline, planter_floors

__all__ = ["DRAIN_GAP", "plan_distance", "wall_normal", "floor_check", "light_plan", "clearance_check", "drain_check",
           "top_opening", "water_check", "planter_rows", "all_ok", "table"]

#: PROVISIONAL (2026-11-07): how far a planter's top outline stays from any drain, in mm.
#: grid-roof has no such rule and no source gives one. It is here so that the distance is
#: looked at, until the drainage branch or the studio sets a real number. Below it there is a
#: hard limit no parameter can lower, ``planter_wall + outlet``. ``keep`` does not carve the walls
#: and they are united last, so closer than that a wall fills the drain's bore back in and blocks
#: the drain. The limit is for a straight wall; a flared rim draws the wall back at the deck.
DRAIN_GAP = 500.0

ZERO = np.zeros((1, 1, 1))


def plan_distance(outline, gx, gy):
    """Signed plan distance to an outline on the grid ``gx x gy`` (negative inside)."""
    return region(outline, -1e4, 1e4).get_distance_numpy(gx[:, None, None], gy[None, :, None], ZERO)[:, :, 0]


def wall_normal(brief, spec, floor):
    """The thinnest the planter's wall gets, measured square to its surface: by formula, not sampled.

    ``keep`` makes the wall with ``Shell(pocket, planter_wall)``, so ``planter_wall``
    is a thickness of the pocket's field. That field is a plan distance less the
    rim's growth at each height, so the thickness is measured horizontally. Where
    the rim leans, the wall is thinner than that, square to its surface::

        planter_wall / sqrt(1 + slope ** 2)

    ``slope`` is the rim's steepest growth per height. The rim eases with a
    smoothstep, whose steepest slope is 1.5 times the average, so
    ``slope = 1.5 * rim / (thickness - floor)``. ``tests/test_plant_checks.py``
    compares this with the distance measured between the field's contours.
    """
    slope = 1.5 * spec["rim"] / (brief.thickness - floor)
    return float(brief.planter_wall / (1.0 + slope * slope) ** 0.5)


def floor_check(brief, outline, spec, floor, keep, deck, step=25.0, dz=5.0):
    """Is there a full planter wall under the floor, and how deep is the soil on it?

    The soffit is z = 0: ``keep`` clips each planter's wall to ``slab.solid``,
    so a floor lower than ``planter_wall`` above it gets a thinner wall, or a hole.

    Returns
    -------
    dict
        * ``floor_z`` -- the flat floor's height;
        * ``wall_margin`` -- ``floor_z - planter_wall``, what is left over the soffit;
        * ``kept_under_floor_min`` -- the least kept thickness measured under the floor,
          on columns 100 mm inside the floor outline (its edge is blended), or on the whole
          floor if it is too small for that;
        * ``soil_min``, ``soil_max`` -- deck height less floor over the floor outline (``offset``),
          where the pocket really reaches the flat floor. The flared rim holds less;
        * ``wall_normal_min`` -- reported only, it does not affect ``ok``: see :func:`wall_normal`.
          ``planter_wall`` and ``kept_under_floor_min`` are field values and vertical or
          horizontal measures, not the thickness square to a leaning wall;
        * ``ok`` -- the wall stands, and the floor lies below the deck everywhere (``soil_min > 0``).
    """
    nominal = floor - brief.planter_wall
    points = np.array(outline)[:, :2]
    grow = spec["offset"] + 50
    gx = np.arange(points[:, 0].min() - grow, points[:, 0].max() + grow, step)
    gy = np.arange(points[:, 1].min() - grow, points[:, 1].max() + grow, step)
    distance = plan_distance(outline, gx, gy)
    X, Y = np.meshgrid(gx, gy, indexing="ij")

    floor_plan = distance < spec["offset"]
    if not floor_plan.any():
        raise ValueError("nothing left of the planter's floor at an offset of {} mm".format(spec["offset"]))
    inner = distance < spec["offset"] - 100.0
    xs, ys = (X[inner], Y[inner]) if inner.any() else (X[floor_plan], Y[floor_plan])   # a very small floor
    zs = np.arange(0.5 * dz, floor, dz)
    if zs.size:
        kept = keep.get_distance_numpy(xs[:, None], ys[:, None], zs[None, :]) < 0
        run = np.argmin(kept[:, ::-1], axis=1)      # contiguous kept material, down from just under the floor
        run = np.where(kept.all(axis=1), kept.shape[1], run) * dz
        least = float(run.min())
    else:
        least = 0.0

    surface = deck.height_at(X[floor_plan], Y[floor_plan])
    return {"floor_z": float(floor), "wall_margin": float(nominal), "kept_under_floor_min": least,
            "soil_min": float((surface - floor).min()), "soil_max": float((surface - floor).max()),
            "wall_normal_min": wall_normal(brief, spec, floor),
            "ok": bool(nominal >= 0 and least >= brief.planter_wall - 2 * dz and (surface - floor).min() > 0)}


def light_plan(brief, openings, step=25.0):
    """Plan cells any light opening covers at any height, from the opening fields themselves (``Voids.openings``).

    Sampled at five heights through the slab, which includes both faces, where they flare most.
    """
    gx = np.arange(0, brief.length + step, step)
    gy = np.arange(0, brief.width + step, step)
    zs = np.linspace(0.0, brief.thickness, 5)
    covered = np.zeros((gx.size, gy.size), dtype=bool)
    for opening in openings:
        covered |= (opening.get_distance_numpy(gx[:, None, None], gy[None, :, None], zs[None, None, :]) < 0).any(axis=2)
    return covered


def clearance_check(brief, beams, outline, spec, light, step=25.0):
    """Plan gaps from the top of the pocket (outline grown by ``offset + rim``) to the beams and light openings.

    ``light`` is :func:`light_plan`. A planter's wall may merge into a beam, as
    both are kept, so the beam only has to stay clear of the opening. Next to a
    light opening the wall must fit too, or keeping it would narrow the light:
    that gap has to be more than ``planter_wall``.
    """
    top = spec["offset"] + spec["rim"]
    gx = np.arange(0, brief.length + step, step)
    gy = np.arange(0, brief.width + step, step)
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    on_beam = np.zeros(X.shape, dtype=bool)
    for lo, hi in beams.xbands:
        on_beam |= (X >= lo) & (X <= hi)
    for lo, hi in beams.ybands:
        on_beam |= (Y >= lo) & (Y <= hi)
    gap = plan_distance(outline, gx, gy) - top
    beam_gap = float(gap[on_beam].min())
    light_gap = float(gap[light].min()) if light.any() else float("inf")
    beam_ok, light_ok = bool(beam_gap > 0), bool(light_gap > brief.planter_wall)
    return {"top_growth": top, "gap_to_beam": beam_gap, "gap_to_light": light_gap, "beam_ok": beam_ok,
            "light_ok": light_ok, "ok": beam_ok and light_ok}


def drain_check(brief, drawing, outline, spec, min_gap=DRAIN_GAP):
    """Plan gap from the top of the pocket to the nearest drain.

    ``min_gap`` is provisional, see :data:`DRAIN_GAP`. ``hard_gap``, the wall
    and the bore of the drain, holds whatever ``min_gap`` says.
    """
    hard = brief.planter_wall + brief.outlet
    if not drawing.drains:
        return {"gap_to_drain": float("inf"), "min_gap": min_gap, "hard_gap": hard, "ok": True}
    xs = np.array([p[0] for p in drawing.drains], dtype=float)
    ys = np.array([p[1] for p in drawing.drains], dtype=float)
    distance = region(outline, -1e4, 1e4).get_distance_numpy(xs, ys, np.zeros(xs.shape))
    gap = float(distance.min() - (spec["offset"] + spec["rim"]))
    return {"gap_to_drain": gap, "min_gap": min_gap, "hard_gap": hard, "ok": bool(gap >= max(min_gap, hard))}


def top_opening(brief, outline, spec, drawn, deck, step=20.0):
    """The planter's opening at the deck: nominal (at z = t) and measured (in the design, 10 mm under the deck).

    Sizes are the plan extents along X and Y and the area. The measured one
    includes the deck falling below ``t`` and the 80 mm blend of the cut.
    """
    top = spec["offset"] + spec["rim"]
    nominal = np.array(offset_outline(outline, top))[:, :2]
    window = max(top, 0) + 250.0
    points = np.array(outline)[:, :2]
    gx = np.arange(points[:, 0].min() - window, points[:, 0].max() + window, step)
    gy = np.arange(points[:, 1].min() - window, points[:, 1].max() + window, step)
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    near = plan_distance(outline, gx, gy) < window
    void = (drawn.get_distance_numpy(X, Y, deck.height_at(X, Y) - 10.0) > 0) & near
    xs, ys = X[void], Y[void]
    x, y = nominal[:, 0], nominal[:, 1]
    return {
        "nominal_dx": float(np.ptp(x)), "nominal_dy": float(np.ptp(y)),
        "nominal_area": float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2e6),
        "deck_dx": float(np.ptp(xs) + step) if xs.size else 0.0,
        "deck_dy": float(np.ptp(ys) + step) if ys.size else 0.0,
        "deck_area": float(void.sum() * step * step / 1e6),
    }


def water_check(incision):
    """Puddles (stranded cells), reverse falls, and whether every outlet is used."""
    s = incision.summary()
    return {"stranded": s["stranded"], "reverse_falls": s["reverse_falls"], "outlets": s["outlets"],
            "outlets_used": s["outlets_used"], "channel_length_m": s["channel_length"] / 1000,
            "ok": s["stranded"] == 0 and s["reverse_falls"] == 0 and s["outlets_used"] == s["outlets"]}


def planter_rows(brief, drawing, specs, built, min_gap=DRAIN_GAP):
    """Every planter check on a built roof, one flat dict per planter."""
    deck = built.slab.deck
    floors = planter_floors(brief, drawing, specs, deck)
    light = light_plan(brief, built.voids.openings)
    rows = []
    for n, (outline, spec, floor) in enumerate(zip(drawing.planters, specs, floors)):
        checks = [floor_check(brief, outline, spec, floor, built.keep, deck),
                  clearance_check(brief, built.beams, outline, spec, light),
                  drain_check(brief, drawing, outline, spec, min_gap)]
        row = {"planter": n, "plant": spec["id"], "datum": spec["depth_datum"], "depth": spec["depth"]}
        for check in checks:
            row.update({k: v for k, v in check.items() if k != "ok"})
        row.update(top_opening(brief, outline, spec, built.design.drawn, deck))
        row["ok"] = all(check["ok"] for check in checks)
        rows.append(row)
    return rows


def all_ok(rows, water):
    """Did every planter and the water pass?"""
    return all(row["ok"] for row in rows) and water["ok"]


#: The columns of :func:`table`: heading, then field.
COLUMNS = (("P", "planter"), ("plant", "plant"), ("datum", "datum"), ("depth", "depth"), ("floor_z", "floor_z"),
           ("wall_margin", "wall_margin"), ("kept", "kept_under_floor_min"), ("wall_normal", "wall_normal_min"),
           ("soil_min", "soil_min"), ("soil_max", "soil_max"), ("beam_gap", "gap_to_beam"),
           ("light_gap", "gap_to_light"), ("drain_gap", "gap_to_drain"), ("area_m2", "deck_area"), ("ok", "ok"))


def table(rows):
    """The rows as a fixed-width text table, in mm and m2."""

    def cell(value):
        if isinstance(value, bool) or not isinstance(value, float):
            return str(value)
        return "{:.2f}".format(value) if abs(value) < 100 and value != int(value) else "{:.0f}".format(value)

    grid = [[heading for heading, _ in COLUMNS]] + [[cell(row[field]) for _, field in COLUMNS] for row in rows]
    widths = [max(len(line[i]) for line in grid) for i in range(len(COLUMNS))]
    return "\n".join("  ".join(text.ljust(width) for text, width in zip(line, widths)).rstrip() for line in grid)
