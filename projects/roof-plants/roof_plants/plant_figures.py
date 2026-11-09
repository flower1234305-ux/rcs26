"""The comparison drawings: plan and sections, original against planted.

Each function returns the matplotlib figure, and saves it first if given a path.
"""

import numpy as np

from . import preview
from .plant_voids import offset_outline, planter_floors
from .plants import brief_spec

__all__ = ["plan_comparison", "section_comparison"]

LABELS = {"control": "control", "group1_creeping": "G1 creeping", "group3_upright": "G3 upright"}
COLOURS = {"control": "tab:green", "group1_creeping": "tab:purple", "group3_upright": "tab:red"}


def _outlines(ax, drawing, specs):
    for n, (outline, spec) in enumerate(zip(drawing.planters, specs)):
        colour = COLOURS.get(spec["id"], "k")
        floor = np.array(offset_outline(outline, spec["offset"]))[:, :2] / 1000
        top = np.array(offset_outline(outline, spec["top"]))[:, :2] / 1000
        ax.plot(floor[:, 0], floor[:, 1], "-", color=colour, lw=1.6)
        ax.plot(top[:, 0], top[:, 1], "--", color=colour, lw=1.2)
        centre = np.array(outline)[:, :2].mean(axis=0) / 1000
        ax.annotate("P{} {}\nd{:.0f} o{:+.0f} r{:.0f}".format(n, LABELS.get(spec["id"], spec["id"]), spec["depth"],
                                                             spec["offset"], spec["rim"]),
                    (centre[0], top[:, 1].max() + 0.15), ha="center", va="bottom", fontsize=8, color=colour,
                    bbox={"fc": "white", "ec": "none", "alpha": 0.8, "pad": 1})


def _finish(fig, path):
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=130)
    return fig


def plan_comparison(brief, drawing, original, planted, specs, path=None, before=None):
    """Two plans side by side; solid line = pocket floor outline, dashed = top outline.

    The left one is the original roof, or, given ``before`` (its specs), another planted roof.
    """
    import matplotlib.pyplot as plt

    left = [brief_spec(brief)] * len(specs) if before is None else before
    titles = (("original (all planters: brief values)", "planted (each planter sized by its plant)") if before is None
              else ("before the change", "after the change"))
    fig, axes = plt.subplots(1, 2, figsize=(20, 7))
    for ax, built, sp, title in ((axes[0], original, left, titles[0]), (axes[1], planted, specs, titles[1])):
        preview.plan(brief, drawing, built.beams, built.incision, ax=ax, title=title)
        _outlines(ax, drawing, sp)
    fig.suptitle("Planter openings: solid = pocket floor outline, dashed = top outline (offset + rim); "
                 "thin green = drawn outline. d/o/r = depth/offset/rim in mm", fontsize=11)
    return _finish(fig, path)


def section_comparison(brief, drawing, original, planted, specs, planters=None, path=None):
    """For each planter index (by default those not ``control``): a section at its centroid, original vs planted.

    Grey = solid of the design without its foam (``design.drawn``), red = the
    pocket's zero level, orange = what is kept (beams, deck, planter walls),
    blue dotted = the flat floor, green = the real deck.
    """
    import matplotlib.pyplot as plt

    if planters is None:
        planters = [n for n, spec in enumerate(specs) if spec["id"] != "control"]
    t = brief.thickness
    fig, axes = plt.subplots(len(planters), 2, figsize=(16, 2.3 * len(planters) + 0.6), squeeze=False)
    cases = ((original, [brief_spec(brief)] * len(specs), "original"), (planted, specs, "planted"))
    floors = {name: planter_floors(brief, drawing, sp, built.slab.deck) for built, sp, name in cases}
    for row, index in enumerate(planters):
        outline = np.array(drawing.planters[index])[:, :2]
        y = float(outline[:, 1].mean())
        x0, x1 = outline[:, 0].min() - 1300, outline[:, 0].max() + 1300
        xs = np.arange(x0, x1, 10.0)
        zs = np.arange(-40, t + 40, 5.0)
        grid = (xs[:, None, None], np.full((1, 1, 1), y), zs[None, None, :])
        for col, (built, sp, name) in enumerate(cases):
            ax = axes[row][col]
            spec, floor = sp[index], floors[name][index]
            solid = built.design.drawn.get_distance_numpy(*grid)[:, 0, :] < 0
            ax.imshow(solid.T, origin="lower", cmap="Greys", vmin=0, vmax=1.6, aspect="equal",
                      extent=(xs[0], xs[-1], zs[0], zs[-1]))
            ax.contour(xs, zs, built.voids.pockets[index].get_distance_numpy(*grid)[:, 0, :].T, levels=[0],
                       colors="tab:red", linewidths=1.2)
            ax.contour(xs, zs, built.keep.get_distance_numpy(*grid)[:, 0, :].T, levels=[0],
                       colors="tab:orange", linewidths=0.8)
            ax.axhline(floor, color="tab:blue", ls=":", lw=1)
            ax.plot(xs, built.slab.deck.height_at(xs, np.full(xs.shape, y)), color="tab:green", lw=0.8)
            ax.set_title("P{} {} -- {}: depth {:.0f} ({}), floor z {:.0f}, offset {:+.0f}, rim {:.0f}".format(
                index, LABELS.get(spec["id"], spec["id"]), name, spec["depth"], spec["depth_datum"], floor,
                spec["offset"], spec["rim"]), fontsize=9)
            ax.set_xlabel("x (mm), section at y = {:.0f} mm".format(y))
            ax.set_ylabel("z (mm)")
    fig.suptitle("Sections through planters (true scale). grey = solid without foam, red = pocket, "
                 "orange = kept, blue dotted = flat floor, green = real deck", fontsize=11)
    return _finish(fig, path)
