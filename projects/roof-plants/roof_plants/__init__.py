"""The grid roof with plants: planters shaped by what grows in them.

The roof itself is a copy, not an import, because projects don't import each
other (CONTRIBUTING.md, "Once: copy it into your project"). These modules were
copied from ``projects/roof/grid_roof`` at commit ``f4c0b44``:

``brief``, ``checks``, ``design``, ``drainage``, ``drawing``, ``heightfield``,
``kit``, ``preview``, ``spinodoid``

They are unchanged except that ``grid_roof`` reads ``roof_plants`` in their
docstrings, and :func:`design_roof` takes ``steps=``, which lets the planter
modules replace Step 4 (``water``) and Step 7 (``voids``). ``drawing.json`` is
copied from ``projects/roof`` at the same commit. ``grid_roof.nodes`` (the
Grasshopper layer) is not copied: nothing here uses it.

The planter modules are ``plants`` and ``plant_*``; import them by module, as
``from roof_plants.plants import load_plants``.
"""

from . import preview
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
    "preview",
    "region",
    "slab",
    "soffit",
    "voids",
    "water",
    "weathering",
]
