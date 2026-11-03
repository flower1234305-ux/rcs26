"""Water on a plan surface: where it goes, and the channels it cuts.

Drainage is a question about the top surface, so it is answered on a plan grid
of heights, over the whole roof at once. The channels follow two rules from
geomorphology: width and depth grow with catchment to the 0.5 and 0.4 powers
(Leopold and Maddock, 1953), and beds fall towards the outlet, rising over
anything they may not cut into, so no bed holds water.
"""

import heapq
import math

import numpy as np

from compas_vol.runtime import require

__all__ = ["Drainage", "Incision"]

#: The eight neighbours of a plan cell.
_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))


class Drainage:
    """Rain on a surface: which way each cell drains, and how much passes through it.

    Hollows are filled by a priority flood from the outlets (Barnes et al., 2014),
    then each cell drains to its steepest neighbour. Cells from which water cannot
    reach an outlet are reported in ``stranded``.

    Parameters
    ----------
    heights : array-like
        Surface height per plan cell, shape ``(nx, ny)``, in model units.
    origin : sequence[float]
        Plan coordinates of ``heights[0, 0]``.
    spacing : sequence[float]
        Plan cell size ``(dx, dy)``.
    drains : array-like | sequence[point], optional
        Where water leaves: a boolean array over the cells, or plan points
        (each marks its nearest cell). A planter that soaks water up is a
        drain as far as the surface is concerned.
    mask : array-like, optional
        Cells water can run over. ``False`` is a hole -- an opening that water
        is kept away from by its upstand, or the outside of an irregular plan.
    outfall : bool
        Whether water can also leave over the edge of the grid and of the
        mask. Off by default: a roof with a parapet only drains at its drains.

    Attributes
    ----------
    filled : :class:`numpy.ndarray`
        The surface water sees, hollows filled.
    receiver : :class:`numpy.ndarray`
        For each cell, the flat index of the cell it drains into, or ``-1``
        at an outlet, a hole, or a cell with no way out.
    area : :class:`numpy.ndarray`
        Catchment: the plan area draining through each cell, in squared
        model units, its own included.
    stranded : :class:`numpy.ndarray`
        Cells from which water cannot reach any outlet: a basin with no drain,
        which is a design error to fix.

    Examples
    --------
    A 2 m square falling 1:50 towards a drain in its middle: everything
    reaches it, so the drain's catchment is the whole surface.

    >>> import numpy as np
    >>> from grid_roof import Drainage
    >>> x, y = np.meshgrid(np.arange(41) * 50.0, np.arange(41) * 50.0, indexing="ij")
    >>> heights = 600.0 + 0.02 * np.hypot(x - 1000, y - 1000)
    >>> drainage = Drainage(heights, (0, 0), (50, 50), drains=[(1000, 1000)])
    >>> float(drainage.area.max()) == drainage.area.size * 50 * 50
    True
    >>> int(drainage.stranded.sum())
    0
    """

    def __init__(self, heights, origin=(0.0, 0.0), spacing=(1.0, 1.0), drains=None, mask=None, outfall=False):
        self.heights = np.asarray(heights, dtype=float)
        if self.heights.ndim != 2:
            raise ValueError("Heights are a plan grid; got shape {}.".format(self.heights.shape))
        self.origin = tuple(float(v) for v in origin)[:2]
        self.spacing = tuple(float(v) for v in spacing)[:2]
        self.mask = np.ones(self.heights.shape, dtype=bool) if mask is None else np.asarray(mask, dtype=bool).copy()
        self.mask &= np.isfinite(self.heights)
        self.drains = self._as_cells(drains) & self.mask
        self.outfall = bool(outfall)
        if not self.drains.any() and not self.outfall:
            raise ValueError("Water has nowhere to go: give at least one drain, or allow outfall over the edge.")
        self._route()

    # ==========================================================================
    # plan grid
    # ==========================================================================

    @property
    def shape(self):
        """tuple[int, int]: Cells along each plan axis."""
        return self.heights.shape

    def coordinates(self):
        """tuple[:class:`numpy.ndarray`, :class:`numpy.ndarray`]: Plan ``x`` and ``y`` of every cell."""
        nx, ny = self.shape
        x = self.origin[0] + np.arange(nx) * self.spacing[0]
        y = self.origin[1] + np.arange(ny) * self.spacing[1]
        return np.meshgrid(x, y, indexing="ij")

    def cell_of(self, point):
        """tuple[int, int]: The cell nearest a plan point."""
        return tuple(
            int(np.clip(round((float(v) - o) / s), 0, n - 1))
            for v, o, s, n in zip(point[:2], self.origin, self.spacing, self.shape)
        )

    def _as_cells(self, drains):
        cells = np.zeros(self.shape, dtype=bool)
        if drains is None:
            return cells
        array = np.asarray(drains)
        if array.dtype == bool and array.shape == self.shape:
            return array.copy()
        for point in drains:
            cells[self.cell_of(point)] = True
        return cells

    # ==========================================================================
    # routing
    # ==========================================================================

    def _route(self):
        nx, ny = self.shape
        heights, mask = self.heights, self.mask
        filled = np.where(mask, heights, np.inf)
        reached = ~mask
        queue = []

        seeds = self.drains.copy()
        if self.outfall:
            ndimage = require("scipy.ndimage")
            edge = np.zeros(self.shape, dtype=bool)
            edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
            seeds |= mask & (edge | ~ndimage.binary_erosion(mask, structure=np.ones((3, 3)), border_value=0))
        for i, j in np.argwhere(seeds):
            heapq.heappush(queue, (filled[i, j], int(i), int(j)))
            reached[i, j] = True

        # A fall far below anything a model resolves, so a filled hollow still
        # has a direction without its height visibly changing.
        rise = 1e-6 * min(self.spacing)
        while queue:
            level, i, j = heapq.heappop(queue)
            for di, dj in _OFFSETS:
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny and not reached[a, b]:
                    reached[a, b] = True
                    filled[a, b] = max(filled[a, b], level + rise)
                    heapq.heappush(queue, (filled[a, b], a, b))

        self.stranded = mask & ~reached
        self.filled = np.where(mask & reached, filled, np.nan)

        # Steepest descent on the filled surface. Every reached cell that is
        # not an outlet has a strictly lower neighbour: the one it was flooded
        # from, at the least.
        surface = np.where(mask & reached, filled, np.inf)
        padded = np.pad(surface, 1, constant_values=np.inf)
        best = np.zeros(self.shape)
        receiver = np.full(self.shape, -1, dtype=np.int64)
        index = np.arange(nx * ny).reshape(self.shape)
        padded_index = np.pad(index, 1, constant_values=-1)
        for di, dj in _OFFSETS:
            neighbour = padded[1 + di:1 + di + nx, 1 + dj:1 + dj + ny]
            distance = math.hypot(di * self.spacing[0], dj * self.spacing[1])
            with np.errstate(invalid="ignore"):
                slope = (surface - neighbour) / distance
            slope = np.where(np.isfinite(slope), slope, 0.0)
            better = slope > best
            best = np.where(better, slope, best)
            receiver = np.where(better, padded_index[1 + di:1 + di + nx, 1 + dj:1 + dj + ny], receiver)
        receiver[seeds | ~mask | self.stranded] = -1
        self.receiver = receiver

        # Accumulate from the top of the surface down: a cell is settled only
        # once everything that drains into it has been.
        area = np.where(mask, self.spacing[0] * self.spacing[1], 0.0).ravel()
        flat_receiver = receiver.ravel()
        order = np.argsort(np.where(mask & reached, filled, -np.inf), axis=None)[::-1]
        for cell in order:
            target = flat_receiver[cell]
            if target >= 0:
                area[target] += area[cell]
        self.area = area.reshape(self.shape)
        self._order = order

    # ==========================================================================
    # channels
    # ==========================================================================

    def incise(self, onset=2.0e6, width=200.0, depth=70.0, reference=1.0e7, exponents=(0.5, 0.4), limit=None,
               floor=None, fall=0.0):
        """Cut the channels this drainage would erode, sized by their catchments.

        Parameters
        ----------
        onset : float
            Catchment, in squared model units, at which a channel begins: the
            channel head. Upstream of it the surface only sheds water as a
            sheet. The default is 2 m^2 in millimetres.
        width, depth : float
            Channel width and depth where the catchment equals ``reference``.
        reference : float
            The catchment ``width`` and ``depth`` are given at. Default 10 m^2.
        exponents : tuple[float, float]
            How width and depth grow with catchment. The defaults are Leopold
            and Maddock's downstream hydraulic geometry.
        limit : float, optional
            The deepest any channel may be.
        floor : float | array-like, optional
            The lowest the surface may be cut to, per cell: a beam that must
            keep its depth, a minimum skin over something below. A channel
            that meets a higher floor passes over it, and the bed upstream
            rises to meet it, so no hollow is left behind it.
        fall : float
            Least fall along a channel bed, as a gradient (``0.005`` is 1:200),
            imposed from each outlet upstream.

        Returns
        -------
        :class:`Incision`
        """
        nx, ny = self.shape
        channel = (self.area >= onset) & self.mask & ~self.stranded
        scale = np.where(channel, self.area / float(reference), 0.0)
        widths = np.where(channel, width * scale ** exponents[0], 0.0)
        depths = np.where(channel, depth * scale ** exponents[1], 0.0)
        if limit is not None:
            depths = np.minimum(depths, float(limit))
        floor = np.full(self.shape, -np.inf) if floor is None else np.broadcast_to(np.asarray(floor, float), self.shape)

        # Grade the beds from the outlets upstream: never lower than the floor,
        # never lower than the bed downstream plus the least fall.
        bed = np.where(channel, np.maximum(self.heights - depths, floor), np.nan)
        flat_bed, flat_receiver = bed.ravel(), self.receiver.ravel()
        flat_channel = channel.ravel()
        for cell in self._order[::-1]:
            if not flat_channel[cell]:
                continue
            target = flat_receiver[cell]
            if target >= 0 and flat_channel[target]:
                i, j = divmod(int(cell), ny)
                a, b = divmod(int(target), ny)
                step = math.hypot((a - i) * self.spacing[0], (b - j) * self.spacing[1])
                flat_bed[cell] = max(flat_bed[cell], flat_bed[target] + fall * step)
        bed = np.minimum(flat_bed.reshape(self.shape), self.heights)

        # Each channel cell presses a parabolic dish into the surface, as wide
        # as the channel and as deep as its graded bed; the surface is the
        # lowest of them, which keeps the trough continuous through bends and
        # confluences.
        surface = self.heights.copy()
        dx, dy = self.spacing
        for i, j in np.argwhere(channel):
            half = 0.5 * widths[i, j]
            cut = self.heights[i, j] - bed[i, j]
            if half <= 0 or cut <= 0:
                surface[i, j] = min(surface[i, j], bed[i, j])
                continue
            ri, rj = int(half // dx) + 1, int(half // dy) + 1
            i0, i1, j0, j1 = max(i - ri, 0), min(i + ri + 1, nx), max(j - rj, 0), min(j + rj + 1, ny)
            u = ((np.arange(i0, i1) - i) * dx)[:, None]
            v = ((np.arange(j0, j1) - j) * dy)[None, :]
            r2 = (u * u + v * v) / (half * half)
            dish = np.where(r2 < 1.0, bed[i, j] + cut * r2, np.inf)
            np.minimum(surface[i0:i1, j0:j1], dish, out=surface[i0:i1, j0:j1])
        surface = np.where(self.mask, np.maximum(surface, floor), self.heights)
        return Incision(self, surface, channel, widths, depths, bed)


class Incision:
    """The channels a :class:`Drainage` cuts, and the surface they leave.

    Attributes
    ----------
    drainage : :class:`Drainage`
    surface : :class:`numpy.ndarray`
        The cut surface, per plan cell.
    channel : :class:`numpy.ndarray`
        Cells on a channel's centre line.
    width, depth : :class:`numpy.ndarray`
        Width and ungraded depth per channel cell, from hydraulic geometry.
    bed : :class:`numpy.ndarray`
        Graded bed height per channel cell; ``nan`` elsewhere.
    """

    def __init__(self, drainage, surface, channel, width, depth, bed):
        self.drainage = drainage
        self.surface = surface
        self.channel = channel
        self.width = width
        self.depth = depth
        self.bed = bed

    @property
    def cut(self):
        """:class:`numpy.ndarray`: How much was cut, per plan cell."""
        return self.drainage.heights - self.surface

    def reverse_falls(self, tolerance=1e-6):
        """Channel cells whose surface is lower than the cell they drain into.

        A graded network has none: each would hold a puddle. Counted on the
        final surface, after the channels overlap and the floor is applied,
        because that is the surface the water actually meets.

        Returns
        -------
        int
        """
        surface, receiver = self.surface.ravel(), self.drainage.receiver.ravel()
        cells = np.flatnonzero(self.channel.ravel() & (receiver >= 0))
        return int((surface[receiver[cells]] > surface[cells] + tolerance).sum())

    def summary(self):
        """The numbers worth looking at, in model units.

        ``outlets_used`` counts outlets that receive water from beyond
        themselves; an outlet drawn as a region -- a planter -- counts once.
        """
        ndimage = require("scipy.ndimage")

        cell = self.drainage.spacing[0] * self.drainage.spacing[1]
        drains = self.drainage.drains
        labels, count = ndimage.label(drains, structure=np.ones((3, 3)))
        receiving = (self.drainage.area > cell) & drains
        used = len(np.unique(labels[receiving])) if receiving.any() else 0
        return {
            "channel_length": float(self.channel.sum() * math.sqrt(cell)),
            "deepest_cut": float(self.cut.max()),
            "widest": float(self.width.max()),
            "outlets": int(count),
            "outlets_used": int(used),
            "largest_catchment": float(self.drainage.area[drains].max()) if drains.any() else 0.0,
            "stranded": int(self.drainage.stranded.sum()),
            "reverse_falls": self.reverse_falls(),
        }

    def to_volume(self, name=None):
        """The solid below the cut surface, as a :class:`grid_roof.VolHeightField`."""
        from .heightfield import VolHeightField

        return VolHeightField(self.surface, self.drainage.origin, self.drainage.spacing, name=name)
