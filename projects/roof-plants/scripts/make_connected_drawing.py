"""Write drawing_connected.json: drawing.json with planters 1 and 3 drawn as one dumbbell.

    uv run python projects/roof-plants/scripts/make_connected_drawing.py             # neck 800 mm, as committed
    uv run python projects/roof-plants/scripts/make_connected_drawing.py --neck 500  # a new file

The first writes drawing_connected.json; any other neck writes drawing_connected_neck<width>.json,
so the committed one stays. Both go next to drawing.json, in projects/roof-plants.

The two planters are the closest pair, 2.7 m apart, with no beam between them.
Their outlines are joined by a straight neck ``NECK`` mm wide between their
centres, read off the union of the three plan distance fields, and the loop is
resampled to about one point every ``SPACING`` mm (a loop of hundreds of
points makes every field evaluation slower). Everything else in the drawing is
copied as it is; the dumbbell takes the place of planter 1 and planter 3 is
removed, so the planters are 0, the dumbbell, 2.
"""

import argparse
import os

import contourpy
import numpy as np

from roof_plants.drawing import Drawing, outline
from roof_plants.plant_checks import plan_distance

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
JOIN = (1, 3)
NECK = 800.0
SPACING = 80.0
STEP = 10.0


def capsule(a, b, gx, gy):
    """Plan distance to the segment ``a``-``b``."""
    X, Y = np.meshgrid(gx, gy, indexing="ij")
    d = np.subtract(b, a)
    t = np.clip(((X - a[0]) * d[0] + (Y - a[1]) * d[1]) / d.dot(d), 0, 1)
    return np.hypot(X - a[0] - t * d[0], Y - a[1] - t * d[1])


def dumbbell(first, second, neck=NECK, spacing=SPACING, step=STEP):
    points = np.vstack([np.array(first)[:, :2], np.array(second)[:, :2]])
    gx = np.arange(points[:, 0].min() - 200, points[:, 0].max() + 200, step)
    gy = np.arange(points[:, 1].min() - 200, points[:, 1].max() + 200, step)
    a, b = np.array(first)[:-1, :2].mean(axis=0), np.array(second)[:-1, :2].mean(axis=0)
    field = np.minimum.reduce([plan_distance(first, gx, gy), plan_distance(second, gx, gy),
                               capsule(a, b, gx, gy) - neck / 2])
    lines = contourpy.contour_generator(gx, gy, field.T).lines(0.0)
    if len(lines) != 1:
        raise ValueError("the dumbbell has {} loops, expected 1".format(len(lines)))
    loop = lines[0]
    length = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(loop, axis=0).T))])
    count = max(16, int(round(length[-1] / spacing)))
    at = np.linspace(0, length[-1], count, endpoint=False)
    xs, ys = np.interp(at, length, loop[:, 0]), np.interp(at, length, loop[:, 1])
    return outline([(round(float(x), 1), round(float(y), 1)) for x, y in zip(xs, ys)])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--neck", type=float, default=NECK, help="neck width, mm")
    parser.add_argument("--out", help="output file; by default drawing_connected.json for the 800 mm neck, "
                                      "drawing_connected_neck<width>.json for any other, so the committed one stays")
    args = parser.parse_args()
    if args.out is None:
        name = "drawing_connected.json" if args.neck == NECK else "drawing_connected_neck{:g}.json".format(args.neck)
        args.out = os.path.join(HERE, name)
    drawing = Drawing.load(os.path.join(HERE, "drawing.json"))
    joined = dumbbell(drawing.planters[JOIN[0]], drawing.planters[JOIN[1]], neck=args.neck)
    planters = [joined if n == JOIN[0] else p for n, p in enumerate(drawing.planters) if n != JOIN[1]]
    connected = Drawing(drawing.openings, planters, drawing.drains)
    path = connected.save(args.out)
    print("wrote", os.path.normpath(path), "with", len(planters), "planters; the dumbbell has", len(joined), "points")


if __name__ == "__main__":
    main()
