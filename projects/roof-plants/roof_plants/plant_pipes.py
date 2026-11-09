"""Under-slab pipes from each planter's drain bore to the nearest roof drain: data, not geometry.

The bore of :mod:`roof_plants.plant_drains` ends at the soffit. Here each bore gets
a pipe hung under the slab to the nearest of the drawing's drains. It ends right
under that drain, below the soffit by its own radius and its fall, where it would
join the drain's downpipe (not modelled). The pipes are **not cut into or
added to the roof's distance field**; they are a record (:class:`Pipe`: start,
end, route, length, fall) with a polyline and an optional tube mesh to draw.

The drain is the one nearest the bore by straight plan distance. If every route to
it is blocked, the pipe is reported with what it crosses; the next nearest drain
is not tried.

The route, for each bore:

1. down from the bore's exit at the soffit (z = 0) by the pipe's radius, so the
   pipe's top runs flush under the soffit;
2. along the beam grid's two directions -- X then Y, else Y then X -- falling at
   ``slope`` all the way; a straight run is the last resort, when both are blocked;
3. to the point under the drain, below the soffit by the pipe's radius and its
   fall, where it would meet the drain's downpipe, which is not modelled.

The first of those runs that crosses nothing is taken. "Crosses" is in plan:
another planter's bore, another drain's outlet, or a light opening (``Voids.openings``,
at their widest), each grown by the pipe's radius. What the pipe passes under
otherwise (a beam, a planter) is below the slab and not a crossing.

The fall needs ``slope x length`` of height under the soffit, plus the pipe
itself: :attr:`Pipe.depth_below_soffit`. No clear height under the slab is
defined anywhere, so that is reported, not judged.

PROVISIONAL (2026-11-09): ``slope`` 1 % and the pipe radius (the bore's, 80 mm)
have no source. The FLL guideline asks for an inspection chamber over every
roof drain inside a planted area; this tool does not model one.
"""

import dataclasses

import numpy as np

from .plant_checks import light_plan
from .plant_drains import planter_drains

__all__ = ["SLOPE", "Pipe", "route", "planter_pipes", "pipe_rows", "pipe_table", "pipe_overlaps", "pipe_mesh",
           "plot_plan", "plot_profiles"]

#: PROVISIONAL (2026-11-09): fall of the under-slab pipes, 1 %. No source.
SLOPE = 0.01


@dataclasses.dataclass
class Pipe:
    """One planter drain's pipe under the slab, in mm. ``points`` run from the bore to the drain, falling."""

    planter: int
    bore: tuple            # (x, y) of the bore
    drain: int             # index into drawing.drains
    kind: str              # "x-then-y", "y-then-x" or "straight"
    radius: float
    slope: float
    points: list           # [(x, y, z)], from the bore's exit at the soffit to the point under the drain
    length: float          # horizontal run, mm
    crossings: list        # what the chosen route crosses in plan; empty when clear

    @property
    def start(self):
        return self.points[0]

    @property
    def end(self):
        return self.points[-1]

    @property
    def drop(self):
        """Height the fall takes over the run, mm."""
        return self.slope * self.length

    @property
    def depth_below_soffit(self):
        """How far under the soffit the pipe's bottom gets, at the drain: the fall plus the pipe's diameter."""
        return self.drop + 2 * self.radius

    @property
    def clear(self):
        return not self.crossings


def _corners(kind, a, b):
    if kind == "x-then-y":
        return [a, (b[0], a[1]), b]
    if kind == "y-then-x":
        return [a, (a[0], b[1]), b]
    return [a, b]


def _samples(corners, step):
    points = []
    for p, q in zip(corners[:-1], corners[1:]):
        n = max(1, int(np.ceil(np.hypot(q[0] - p[0], q[1] - p[1]) / step)))
        t = np.linspace(0, 1, n + 1)
        points.append(np.stack([p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])], axis=1))
    return np.vstack(points)


def _crossings(samples, radius, obstacles, light, light_grid):
    found = []
    for name, (x, y, r) in obstacles:
        if np.hypot(samples[:, 0] - x, samples[:, 1] - y).min() < r + radius:
            found.append(name)
    if light is not None:
        gx, gy, step = light_grid
        reach = int(np.ceil(radius / step))
        i = np.clip(np.round((samples[:, 0] - gx[0]) / step).astype(int), 0, len(gx) - 1)
        j = np.clip(np.round((samples[:, 1] - gy[0]) / step).astype(int), 0, len(gy) - 1)
        hit = np.zeros(len(samples), dtype=bool)
        for di in range(-reach, reach + 1):
            for dj in range(-reach, reach + 1):
                if (di * di + dj * dj) * step * step <= radius * radius:
                    hit |= light[np.clip(i + di, 0, len(gx) - 1), np.clip(j + dj, 0, len(gy) - 1)]
        if hit.any():
            found.append("light opening")
    return found


def route(a, b, radius, obstacles, light=None, light_grid=None, step=25.0):
    """The first clear plan route from ``a`` to ``b``: x-then-y, y-then-x, straight.

    ``obstacles`` are ``(name, (x, y, r))``. If none is clear, the straight run is
    returned with what it crosses. Returns ``(kind, corners, length, crossings)``.
    """
    tried = []
    for kind in ("x-then-y", "y-then-x", "straight"):
        corners = _corners(kind, a, b)
        corners = [c for n, c in enumerate(corners) if n == 0 or c != corners[n - 1]]
        length = float(sum(np.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(corners[:-1], corners[1:])))
        crossings = _crossings(_samples(corners, step), radius, obstacles, light, light_grid)
        if not crossings:
            return kind, corners, length, []
        tried.append((kind, corners, length, crossings))
    return tried[-1]


def planter_pipes(brief, drawing, specs, built, slope=SLOPE, radius=None, step=25.0):
    """One :class:`Pipe` per bore, in drawing order, to the drain nearest it in plan.

    ``radius`` is the pipe's, by default the bore's. Reads the bores from
    :func:`roof_plants.plant_drains.planter_drains`, the drains from the drawing and the
    light openings from ``built.voids``; changes nothing.
    """
    drains = [(float(p[0]), float(p[1])) for p in drawing.drains]
    if not drains:
        raise ValueError("the drawing has no drains to pipe the planters to")
    bores = planter_drains(brief, drawing, specs, built.slab.deck)
    light = light_plan(brief, built.voids.openings, step)
    grid_ = (np.arange(0, brief.length + step, step), np.arange(0, brief.width + step, step), step)
    pipes = []
    for n, planter in enumerate(bores):
        for bore in planter:
            r = bore.radius if radius is None else float(radius)
            target = int(np.argmin([np.hypot(bore.x - x, bore.y - y) for x, y in drains]))
            obstacles = [("drain {}".format(k), (x, y, brief.outlet)) for k, (x, y) in enumerate(drains) if k != target]
            obstacles += [("bore of P{}".format(m), (b.x, b.y, b.radius)) for m, other in enumerate(bores)
                          for b in other if (b.x, b.y) != (bore.x, bore.y)]
            kind, corners, length, crossings = route((bore.x, bore.y), drains[target], r, obstacles, light, grid_, step)
            z0 = -r                       # pipe's centre, its top flush with the soffit
            points, run = [(bore.x, bore.y, 0.0), (bore.x, bore.y, z0)], 0.0
            for p, q in zip(corners[:-1], corners[1:]):
                run += float(np.hypot(q[0] - p[0], q[1] - p[1]))
                points.append((float(q[0]), float(q[1]), z0 - slope * run))
            pipes.append(Pipe(n, (bore.x, bore.y), target, kind, r, float(slope), points, length, crossings))
    return pipes


def pipe_rows(pipes):
    """One flat dict per pipe, for a table or JSON. ``clear`` is the plan crossing check; depth is reported only."""
    return [{"planter": p.planter, "drain": p.drain, "route": p.kind, "length_mm": p.length, "slope": p.slope,
             "drop_mm": p.drop, "depth_below_soffit_mm": p.depth_below_soffit, "radius": p.radius,
             "start": p.start, "end": p.end, "crossings": ", ".join(p.crossings), "clear": p.clear} for p in pipes]


def pipe_table(pipes):
    """The pipes as a fixed-width text table, in mm."""
    head = ["P", "to drain", "route", "length", "slope", "drop", "below_soffit", "clear", "crossings"]
    lines = [head] + [[str(p.planter), str(p.drain), p.kind, "{:.0f}".format(p.length), "{:.1%}".format(p.slope),
                       "{:.0f}".format(p.drop), "{:.0f}".format(p.depth_below_soffit), str(p.clear),
                       ", ".join(p.crossings) or "-"] for p in pipes]
    widths = [max(len(line[i]) for line in lines) for i in range(len(head))]
    return "\n".join("  ".join(t.ljust(w) for t, w in zip(line, widths)).rstrip() for line in lines)


def _run_samples(pipe, step):
    """Points every ``step`` along the pipe's sloping run (its first point, the drop under the bore, left out)."""
    points = np.array(pipe.points[1:], dtype=float)
    out = []
    for p, q in zip(points[:-1], points[1:]):
        n = max(1, int(np.ceil(np.hypot(*(q[:2] - p[:2])) / step)))
        t = np.linspace(0, 1, n + 1)[:, None]
        out.append(p + t * (q - p))
    return np.vstack(out)


def pipe_overlaps(pipes, step=25.0):
    """Where two pipes come closer in plan than their radii allow: numbers only, nothing judged.

    For each pair that does: how long a stretch of the first lies within ``r1 + r2``
    of the second in plan (mm, sampled every ``step``), and at the closest such
    point the two centres' plan distance and their height difference. Two pipes
    that end at the same drain always meet there; whether they cross, run side
    by side or join is not modelled.
    """
    samples = [_run_samples(p, step) for p in pipes]
    found = []
    for i in range(len(pipes)):
        for j in range(i + 1, len(pipes)):
            a, b = samples[i], samples[j]
            d = np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])
            near = d.min(axis=1) < pipes[i].radius + pipes[j].radius
            if not near.any():
                continue
            k = int(np.argmin(d.min(axis=1)))
            m = int(np.argmin(d[k]))
            found.append({"pipes": (i, j), "planters": (pipes[i].planter, pipes[j].planter),
                          "same_drain": pipes[i].drain == pipes[j].drain,
                          "overlap_length_mm": float(near.sum() * step),
                          "closest_plan_mm": float(d[k, m]), "height_difference_mm": float(abs(a[k, 2] - b[m, 2]))})
    return found


def pipe_mesh(pipe, sides=8):
    """A tube along the pipe's polyline, for a preview only: ``(vertices, faces)``, quads split into triangles."""
    points = np.array(pipe.points, dtype=float)
    vertices, faces = [], []
    for k, (p, q) in enumerate(zip(points[:-1], points[1:])):
        axis = q - p
        axis /= np.linalg.norm(axis)
        helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(axis, helper)
        u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        angles = np.linspace(0, 2 * np.pi, sides, endpoint=False)
        ring = pipe.radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
        base = len(vertices)
        vertices += list(p + ring) + list(q + ring)
        for s in range(sides):
            a, b = base + s, base + (s + 1) % sides
            c, d = a + sides, b + sides
            faces += [(a, b, d), (a, d, c)]
    return np.array(vertices), np.array(faces)


def plot_plan(ax, pipes, drawing=None, scale=1e-3):
    """Draw the pipes on a plan; ``scale`` 1e-3 for the plans of :mod:`roof_plants.preview`, which are in metres."""
    for p in pipes:
        xy = np.array(p.points)[:, :2] * scale
        ax.plot(xy[:, 0], xy[:, 1], color="tab:blue" if p.clear else "tab:red", linewidth=1.6,
                linestyle="-" if p.clear else "--", zorder=5)
        ax.plot(p.bore[0] * scale, p.bore[1] * scale, "o", color="tab:blue", markersize=4, zorder=6)
    if drawing is not None:
        for k, d in enumerate(drawing.drains):
            ax.annotate("D{}".format(k), (d[0] * scale, d[1] * scale), fontsize=7, color="tab:blue")


def plot_profiles(ax, pipes):
    """Each pipe's fall against its run: distance along the pipe (m) against height under the soffit (mm)."""
    for p in pipes:
        pts = np.array(p.points)
        run = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts[:, :2], axis=0).T))])
        ax.plot(run / 1000, pts[:, 2], label="P{} to drain {}".format(p.planter, p.drain))
    ax.axhline(0, color="0.3", linewidth=0.8)
    ax.set_xlabel("along the pipe, m")
    ax.set_ylabel("pipe centre, mm (soffit = 0)")
    ax.legend(fontsize=7)
