"""One workflow, written the way a Grasshopper definition is drawn.

* :class:`Brief` -- the sliders: every number, saved as JSON.
* :mod:`roof_plants.steps` -- the components: one function per step.
* :mod:`roof_plants.preview` -- the viewport.
"""

from . import preview, steps
from .brief import Brief

__all__ = ["Brief", "preview", "steps"]
