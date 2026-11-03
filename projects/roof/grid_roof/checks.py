"""The checks the brief's rules need, beyond what compas_vol checks for any model."""

import numpy as np

from .design import region

__all__ = ["clear_apertures", "beam_depth"]


def clear_apertures(brief, drawing, roof, step=50.0):
    """For each light opening: the area drawn, and the area with a clear line of sight through the slab, in m2.

    Read off the design. Every process after it only removes material outside
    what is kept, so this is a lower bound on what is built -- unless a kept
    beam crosses an opening, which shows here as a shortfall.
    """
    result = []
    for outline in drawing.openings:
        xs, ys = np.array(outline)[:, 0], np.array(outline)[:, 1]
        reach = brief.opening_flare + step
        gx = np.arange(xs.min() - reach, xs.max() + reach, step)
        gy = np.arange(ys.min() - reach, ys.max() + reach, step)
        zs = np.linspace(1.0, brief.thickness - 1.0, 13)
        values = roof.get_distance_numpy(gx[:, None, None], gy[None, :, None], zs[None, None, :])
        clear = (values > 0).all(axis=2).sum() * step * step / 1e6
        inside = region(outline, -1, 1).get_distance_numpy(gx[:, None, None], gy[None, :, None], np.zeros((1, 1, 1)))
        result.append({"drawn": float((inside < 0).sum() * step * step / 1e6), "clear": float(clear)})
    return result


def beam_depth(field, beams, bounds):
    """The least continuous solid above the soffit, over every column inside a beam, in mm.

    Measure the weathered field, before the joints: a dowel socket would read
    as lost depth. ``None`` for a piece with no beam in it.
    """
    x, y, z = field.coordinates()
    px, py = np.broadcast_arrays(x[:, :, 0], y[:, :, 0])
    inside = np.zeros(px.shape, dtype=bool)
    for lo, hi in beams.xbands:
        inside |= (px > lo) & (px < hi)
    for lo, hi in beams.ybands:
        inside |= (py > lo) & (py < hi)
    inside &= (px > bounds[0]) & (px < bounds[3]) & (py > bounds[1]) & (py < bounds[4])
    if not inside.any():
        return None
    zs = z[0, 0, :]
    above = zs > 0
    solid = field.values[:, :, above] < 0
    heights = zs[above]
    first_void = np.argmax(~solid, axis=2)
    depth = np.where((~solid).any(axis=2), heights[first_void] - 0.5 * (heights[1] - heights[0]), heights[-1])
    return float(np.where(solid[:, :, 0], depth, 0.0)[inside].min())
