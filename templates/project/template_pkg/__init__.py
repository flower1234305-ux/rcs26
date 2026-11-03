"""One workflow, written the way a Grasshopper definition is drawn.

* :class:`Brief` -- the sliders: every number, saved as JSON.
* :mod:`template_pkg.steps` -- the components: one function per step.
* :mod:`template_pkg.preview` -- the viewport.
"""

from . import preview, steps
from .brief import Brief

__all__ = ["Brief", "preview", "steps"]
