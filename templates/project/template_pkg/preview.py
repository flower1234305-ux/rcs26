"""The preview: what a Rhino viewport would show, as plots."""

import numpy as np

__all__ = ["section"]


def section(brief, solid, y=0.0, samples=300, title=""):
    """A section at constant Y: solid in black."""
    import matplotlib.pyplot as plt

    x0, _, z0, x1, _, z1 = brief.bounds
    xs, zs = np.linspace(x0, x1, samples), np.linspace(z0, z1, samples)
    values = solid.get_distance_numpy(xs[:, None, None], np.full((1, 1, 1), float(y)), zs[None, None, :])
    _, ax = plt.subplots(figsize=(5, 5))
    ax.imshow((values[:, 0, :] < 0).T, origin="lower", cmap="Greys", extent=(x0, x1, z0, z1))
    ax.set_title("{} (y = {:.0f} mm)".format(title, y).strip())
    return ax
