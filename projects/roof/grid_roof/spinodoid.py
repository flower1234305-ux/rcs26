import math

import numpy as np

from compas_vol.base import VolObject
from compas_vol.base import broadcast_distances
from compas_vol.base import format_number
from compas_vol.runtime import require


class Spinodoid(VolObject):
    """A bicontinuous foam defined everywhere in world coordinates.

    Cahn's model of spinodal decomposition (1965): a sum of waves of one wavelength
    in random directions, taken on one side of a level. Every box evaluates the
    same foam, so pieces built separately meet at their seams; the
    :func:`compas_vol.processes.spinodal` simulation, run per piece, would not.
    The solid fraction is close to ``fraction`` (within a few points at 32 waves)
    and may be a field.

    Parameters
    ----------
    wavelength : float
        The wavelength of the waves, in model units: roughly the spacing from
        one pore to the next. Walls and pores are each about half of it.
    fraction : float | :class:`compas_vol.base.VolObject`
        Solid fraction, in ``[0, 1]``. Given a field (a
        :class:`compas_vol.modifications.Remap`, typically), it is read per
        point, so the foam can be graded -- dense near a beam, open at a
        soffit -- without a seam between the two.
    waves : int
        How many waves are summed. More is more random and slower; below
        about 16 the structure starts to look periodic.
    seed : int
        Choice of foam. The same seed is the same foam everywhere.

    Notes
    -----
    The sum is normalised to unit variance, so it is close to a standard
    normal variable, and the surface for a solid fraction ``f`` is taken at
    its ``f`` quantile. The fraction that comes out is close to the one asked
    for (within a few points at 32 waves) but not exact; the simulation
    picks its level from the result and is exact. The value is divided by the
    wavenumber, which makes it an approximate distance near the surface;
    a process redistances it anyway.

    Examples
    --------
    >>> import numpy as np
    >>> from grid_roof import Spinodoid
    >>> foam = Spinodoid(wavelength=10.0, fraction=0.4, seed=3)
    >>> x, y, z = np.ogrid[0:60:61j, 0:60:61j, 0:60:61j]
    >>> round(float((foam.get_distance_numpy(x, y, z) < 0).mean()), 1)
    0.4
    >>> grid = foam.get_distance_numpy(*np.ogrid[12.5:13:2j, 3:4:2j, 7:8:2j])
    >>> bool(np.isclose(foam.get_distance([12.5, 3.0, 7.0]), grid[0, 0, 0]))
    True
    """

    def __init__(self, wavelength=10.0, fraction=0.5, waves=32, seed=0, name=None):
        super().__init__(name=name)
        self.wavelength = float(wavelength)
        self.fraction = fraction if isinstance(fraction, VolObject) else float(fraction)
        self.waves = int(waves)
        self.seed = int(seed)
        if self.wavelength <= 0:
            raise ValueError("wavelength must be positive, got {}.".format(wavelength))
        if self.waves < 1:
            raise ValueError("waves must be at least 1, got {}.".format(waves))
        rng = np.random.default_rng(self.seed)
        directions = rng.normal(size=(self.waves, 3))
        directions /= np.linalg.norm(directions, axis=1)[:, None]
        self._k = 2.0 * math.pi / self.wavelength
        self._vectors = directions * self._k
        self._phases = rng.uniform(0.0, 2.0 * math.pi, self.waves)

    # ==========================================================================
    # data
    # ==========================================================================

    @property
    def __data__(self):
        return {"wavelength": self.wavelength, "fraction": self.fraction, "waves": self.waves, "seed": self.seed}

    @classmethod
    def __from_data__(cls, data):
        return cls(data["wavelength"], data["fraction"], data["waves"], data["seed"])

    def __repr__(self):
        fraction = repr(self.fraction) if isinstance(self.fraction, VolObject) else format_number(self.fraction)
        return "Spinodoid({},{},{},{})".format(format_number(self.wavelength), fraction, self.waves, self.seed)

    # ==========================================================================
    # distance functions
    # ==========================================================================

    def _level(self, fraction):
        """The value of the normalised sum below which a share ``fraction`` lies."""
        ndtri = require("scipy.special").ndtri
        return ndtri(np.clip(fraction, 1e-6, 1.0 - 1e-6))

    def _sum(self, x, y, z):
        total = 0.0
        for (kx, ky, kz), phase in zip(self._vectors, self._phases):
            total = total + np.cos(kx * x + ky * y + kz * z + phase)
        return total * math.sqrt(2.0 / self.waves)

    def get_distance(self, point):
        p = self._as_point(point)
        value = self._sum(np.array(p.x), np.array(p.y), np.array(p.z))
        fraction = self.fraction.get_distance(point) if isinstance(self.fraction, VolObject) else self.fraction
        return float((value - self._level(fraction)) / self._k)

    def get_distance_numpy(self, x, y, z):
        value = self._sum(x, y, z)
        if isinstance(self.fraction, VolObject):
            value, fraction = broadcast_distances([value, self.fraction.get_distance_numpy(x, y, z)], x, y, z)
        else:
            fraction = self.fraction
        return (value - self._level(fraction)) / self._k
