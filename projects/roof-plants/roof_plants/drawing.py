"""The drawing: where light comes through, where plants grow, where water leaves."""

import math
from dataclasses import dataclass, field

import compas
import numpy as np
from compas.geometry import Point, Polyline

__all__ = ["Drawing", "blob", "outline"]


@dataclass
class Drawing:
    """The plan-drawn inputs: light openings, planters and drains, as COMPAS geometry.

    Any CAD with COMPAS can write them with ``compas.json_dump``.

    Attributes
    ----------
    openings : list[:class:`compas.geometry.Polyline`]
        Closed outlines of the light openings, cut through the full depth.
    planters : list[:class:`compas.geometry.Polyline`]
        Closed outlines of the planting pockets.
    drains : list[:class:`compas.geometry.Point`]
        Rainwater outlets.

    Examples
    --------
    >>> drawing = Drawing.sample()
    >>> len(drawing.openings), len(drawing.planters), len(drawing.drains)
    (3, 4, 6)
    >>> Drawing.from_data(compas.json_loads(compas.json_dumps(drawing.to_data()))).drains[0] == drawing.drains[0]
    True
    """

    openings: list = field(default_factory=list)
    planters: list = field(default_factory=list)
    drains: list = field(default_factory=list)

    def to_data(self):
        return {"openings": self.openings, "planters": self.planters, "drains": self.drains}

    @classmethod
    def from_data(cls, data):
        return cls(
            [Polyline(p) for p in data.get("openings", [])],
            [Polyline(p) for p in data.get("planters", [])],
            [Point(*p) for p in data.get("drains", [])],
        )

    def save(self, path):
        compas.json_dump(self.to_data(), path, pretty=True)
        return path

    @classmethod
    def load(cls, path):
        return cls.from_data(compas.json_load(path))

    @classmethod
    def sample(cls):
        """The drawing the examples use: smooth blobs standing in for drawn curves."""
        return cls(
            [blob((2600, 8600), 1150, 1), blob((9300, 2700), 900, 2), blob((15400, 8800), 800, 3)],
            [blob((3600, 3300), 650, 4), blob((8300, 9300), 750, 5), blob((14400, 2600), 600, 6),
             blob((10700, 8000), 450, 7)],
            [Point(4300, 1700, 0), Point(10600, 4300, 0), Point(16100, 4100, 0), Point(4200, 10300, 0),
             Point(9600, 10600, 0), Point(16300, 10400, 0)],
        )


def blob(centre, radius, seed=0, count=48):
    """A closed organic outline around ``centre``: a circle of ``radius`` mm with a few smooth lobes.

    ``seed`` picks the lobes; the sample drawing is made of these.

    Examples
    --------
    >>> shape = blob((9000, 6000), 800, seed=1)
    >>> len(shape), shape[0] == shape[-1]
    (49, True)
    """
    rng = np.random.default_rng(seed)
    lobes = [(k, rng.uniform(0.04, 0.12) / k ** 0.3, rng.uniform(0, 2 * math.pi)) for k in (2, 3, 5)]
    points = []
    for n in range(count):
        a = 2 * math.pi * n / count
        r = radius * (1 + sum(amp * math.cos(k * a + phase) for k, amp, phase in lobes))
        points.append([centre[0] + r * math.cos(a), centre[1] + r * math.sin(a), 0.0])
    return Polyline(points + [points[0]])


def outline(points):
    """A closed outline through ``points``, each ``(x, y)`` in mm.

    Examples
    --------
    >>> square = outline([(2000, 2000), (4000, 2000), (4000, 3500), (2000, 3500)])
    >>> len(square), square[0] == square[-1]
    (5, True)
    """
    points = [[float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0] for p in points]
    if points[0] != points[-1]:
        points.append(points[0])
    return Polyline(points)
