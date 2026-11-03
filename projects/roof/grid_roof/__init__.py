"""The grid roof: an 18 x 12 m eroded roof on a 6 m beam grid, built in pieces.

An application of compas_vol. On a Grasshopper canvas its parts would be:

* :class:`Brief` -- the sliders: every number, saved as JSON.
* :class:`Drawing` -- the referenced curves and points.
* :mod:`grid_roof.design` -- the components, one function per step;
  :func:`design_roof` runs them all, like a cluster.
* :mod:`grid_roof.checks`, :mod:`grid_roof.preview` -- panels and the viewport.
* :mod:`grid_roof.nodes` -- the Grasshopper components, as plain functions.

:class:`Drainage`, :class:`Incision`, :class:`VolHeightField`,
:class:`Spinodoid` and :func:`grid_kit` are specific to this roof and live
here.
"""

from . import nodes, preview
from .brief import Brief
from .checks import beam_depth, clear_apertures
from .design import (
    Beams,
    Design,
    Roof,
    Slab,
    Soffit,
    Voids,
    beams,
    box,
    carve,
    design,
    design_roof,
    keep,
    kit,
    plan_mask,
    region,
    slab,
    soffit,
    voids,
    water,
    weathering,
)
from .drainage import Drainage, Incision
from .drawing import Drawing, blob, outline
from .heightfield import VolHeightField
from .kit import beam_bands, grid_kit
from .spinodoid import Spinodoid

__all__ = [
    "Beams",
    "Brief",
    "Design",
    "Drainage",
    "Drawing",
    "Incision",
    "Roof",
    "Slab",
    "Soffit",
    "Spinodoid",
    "Voids",
    "VolHeightField",
    "beam_bands",
    "beam_depth",
    "beams",
    "blob",
    "box",
    "carve",
    "clear_apertures",
    "design",
    "design_roof",
    "grid_kit",
    "keep",
    "kit",
    "outline",
    "plan_mask",
    "nodes",
    "preview",
    "region",
    "slab",
    "soffit",
    "voids",
    "water",
    "weathering",
]
