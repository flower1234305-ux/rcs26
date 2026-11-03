import numpy as np

from compas_vol.base import VolObject


class VolHeightField(VolObject):
    """The solid below a surface given as heights on a plan grid.

    Heights are interpolated bilinearly and held at the edge value beyond the
    grid. The distance is the vertical offset divided by
    ``sqrt(1 + |grad h|^2)``: exact for a plane, close for gently curved surfaces.
    Negative below the surface.

    Parameters
    ----------
    heights : array-like
        Surface height per plan sample, shape ``(nx, ny)``.
    origin : sequence[float]
        Plan coordinates ``(x, y)`` of ``heights[0, 0]``.
    spacing : sequence[float]
        Plan sample spacing ``(dx, dy)``.

    Examples
    --------
    >>> import numpy as np
    >>> from grid_roof import VolHeightField
    >>> flat = VolHeightField(np.full((5, 5), 600.0), (0, 0), (100, 100))
    >>> flat.get_distance([200, 200, 450])
    -150.0
    >>> x = np.linspace(0, 1000, 11)[:, None] + np.zeros((1, 3))
    >>> ramp = VolHeightField(0.1 * x, (0, 0), (100, 100))   # a 1:10 fall
    >>> round(ramp.get_distance([500, 50, 60]), 4)          # 10 mm above it, measured square to it
    9.9504
    """

    def __init__(self, heights, origin=(0.0, 0.0), spacing=(1.0, 1.0), name=None):
        super().__init__(name=name)
        self._heights = None
        self.origin = tuple(float(v) for v in origin)[:2]
        self.spacing = tuple(float(v) for v in spacing)[:2]
        self.heights = heights

    # ==========================================================================
    # data
    # ==========================================================================

    @property
    def __data__(self):
        return {
            "heights": self.heights.tolist(),
            "origin": list(self.origin),
            "spacing": list(self.spacing),
        }

    @classmethod
    def __from_data__(cls, data):
        return cls(data["heights"], data["origin"], data["spacing"])

    # ==========================================================================
    # descriptors
    # ==========================================================================

    @property
    def heights(self):
        """:class:`numpy.ndarray`: The surface height per plan sample."""
        return self._heights

    @heights.setter
    def heights(self, heights):
        heights = np.asarray(heights, dtype=float)
        if heights.ndim != 2 or min(heights.shape) < 2:
            raise ValueError("Heights are a plan grid of at least 2 x 2; got shape {}.".format(heights.shape))
        self._heights = heights
        self._slopes = np.gradient(heights, *self.spacing)

    @property
    def bounds(self):
        """tuple: ``(xmin, ymin, xmax, ymax)`` of the plan grid."""
        nx, ny = self.heights.shape
        x0, y0 = self.origin
        return (x0, y0, x0 + (nx - 1) * self.spacing[0], y0 + (ny - 1) * self.spacing[1])

    def __repr__(self):
        return "VolHeightField({}x{} @ {:.3f})".format(self.heights.shape[0], self.heights.shape[1], min(self.spacing))

    # ==========================================================================
    # distance functions
    # ==========================================================================

    def height_at(self, x, y):
        """The surface height at plan points, interpolated bilinearly.

        Parameters
        ----------
        x, y : float | array-like
            Plan coordinates, broadcastable.

        Returns
        -------
        :class:`numpy.ndarray`
        """
        return self._interpolate(self.heights, x, y)

    def _interpolate(self, grid, x, y):
        shape = np.broadcast_shapes(np.shape(x), np.shape(y))
        result = []
        for value, origin, step, n in zip((x, y), self.origin, self.spacing, grid.shape):
            u = np.clip((np.broadcast_to(np.asarray(value, dtype=float), shape) - origin) / step, 0.0, n - 1)
            i = np.minimum(np.floor(u).astype(int), n - 2)
            result.append((i, u - i))
        (i, fx), (j, fy) = result
        return (
            grid[i, j] * (1 - fx) * (1 - fy)
            + grid[i + 1, j] * fx * (1 - fy)
            + grid[i, j + 1] * (1 - fx) * fy
            + grid[i + 1, j + 1] * fx * fy
        )

    def get_distance(self, point):
        p = self._as_point(point)
        return float(self.get_distance_numpy(np.array(p.x), np.array(p.y), np.array(p.z)))

    def get_distance_numpy(self, x, y, z):
        # The surface depends only on (x, y): evaluate it once per plan point
        # and broadcast along z.
        height = self._interpolate(self.heights, x, y)
        gx = self._interpolate(self._slopes[0], x, y)
        gy = self._interpolate(self._slopes[1], x, y)
        return (np.asarray(z, dtype=float) - height) / np.sqrt(1.0 + gx * gx + gy * gy)
