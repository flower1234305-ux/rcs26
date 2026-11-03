"""The preview: what the Rhino viewport would show, as plots."""

import numpy as np

__all__ = ["plan", "section", "meshes"]


def _axes(ax, size):
    if ax is None:
        import matplotlib.pyplot as plt

        _, ax = plt.subplots(figsize=size)
    return ax


def plan(brief, drawing, beams, incision=None, pieces=None, ax=None, title=None):
    """The roof in plan: deck and channels, beams, light, planters, drains, pieces."""
    from matplotlib.patches import Polygon, Rectangle

    ax = _axes(ax, (10, 6.5))
    extent = (0, brief.length / 1000, 0, brief.width / 1000)
    if incision is not None:
        image = ax.imshow(incision.surface.T, origin="lower", extent=extent, cmap="Greys_r",
                          vmin=brief.thickness - 200, vmax=brief.thickness)
        ax.imshow(np.ma.masked_where(~incision.channel, incision.width).T, origin="lower", extent=extent,
                  cmap="Blues", vmin=0, vmax=incision.width.max())
        ax.figure.colorbar(image, ax=ax, shrink=0.7, label="deck height (mm)")
    ax.add_patch(Rectangle((0, 0), brief.length / 1000, brief.width / 1000, fill=False, lw=1))
    for lo, hi in beams.xbands:
        ax.add_patch(Rectangle((lo / 1000, 0), (hi - lo) / 1000, brief.width / 1000, color="tab:orange", alpha=0.25,
                               lw=0))
    for lo, hi in beams.ybands:
        ax.add_patch(Rectangle((0, lo / 1000), brief.length / 1000, (hi - lo) / 1000, color="tab:orange", alpha=0.25,
                               lw=0))
    for outlines, colour in ((drawing.openings, "gold"), (drawing.planters, "green")):
        for outline in outlines:
            ax.add_patch(Polygon([(p[0] / 1000, p[1] / 1000) for p in outline], fill=False, color=colour, lw=2))
    ax.plot([p[0] / 1000 for p in drawing.drains], [p[1] / 1000 for p in drawing.drains], "o", color="tab:blue")
    for piece in pieces or []:
        x0, y0, _, x1, y1, _ = piece.bounds
        ax.add_patch(Rectangle((x0 / 1000, y0 / 1000), (x1 - x0) / 1000, (y1 - y0) / 1000, fill=False,
                               color="tab:red", lw=0.7))
    ax.set_xlim(-0.3, brief.length / 1000 + 0.3)
    ax.set_ylim(-0.3, brief.width / 1000 + 0.3)
    ax.set_aspect("equal")
    ax.set_xlabel("m")
    ax.set_title(title or "beams (orange), light (gold), planters (green), drains (blue)")
    return ax


def section(brief, obj, y, x_range=None, keep=None, ax=None, title=""):
    """A section along a line of constant Y: solid in black, kept material outlined in orange."""
    x_range = x_range or (0, brief.length)
    xs = np.linspace(*x_range, 1200)
    zs = np.linspace(-50, brief.thickness + 50, 120)
    grid = (xs[:, None, None], np.full((1, 1, 1), float(y)), zs[None, None, :])
    ax = _axes(ax, (11, 2.4))
    solid = obj.get_distance_numpy(*grid)[:, 0, :] < 0
    ax.imshow(solid.T, origin="lower", aspect="auto", cmap="Greys", extent=(x_range[0] / 1000, x_range[1] / 1000,
                                                                          zs[0], zs[-1]))
    if keep is not None:
        ax.contour(xs / 1000, zs, keep.get_distance_numpy(*grid)[:, 0, :].T, levels=[0], colors="tab:orange",
                   linewidths=1)
    ax.set_title("{} (y = {:.1f} m)".format(title, y / 1000).strip())
    ax.set_xlabel("m")
    ax.set_ylabel("mm")
    return ax


def meshes(parts, ax=None, elev=35, azim=-60, title=""):
    """Shaded triangle meshes, each ``(vertices, faces)``, drawn together in metres."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    if ax is None:
        import matplotlib.pyplot as plt

        ax = plt.figure(figsize=(7, 5)).add_subplot(projection="3d")
    light = np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8])
    corners = []
    for vertices, faces in parts:
        triangles = np.asarray(vertices)[np.asarray(faces)] / 1000
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
        shade = 0.35 + 0.65 * np.clip(normals @ light, 0, 1)
        ax.add_collection3d(Poly3DCollection(triangles, facecolors=np.outer(shade, [0.82, 0.78, 0.72]),
                                             linewidths=0))
        corners.append(triangles.reshape(-1, 3))
    points = np.concatenate(corners)
    low, high = points.min(axis=0), points.max(axis=0)
    middle, span = (low + high) / 2, (high - low).max() / 2
    ax.set_xlim(middle[0] - span, middle[0] + span)
    ax.set_ylim(middle[1] - span, middle[1] + span)
    ax.set_zlim(middle[2] - span, middle[2] + span)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title)
    return ax
