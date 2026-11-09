"""The planters as a :class:`Contribution`: an adapter between the plant branch and a shared module interface.

A classmate proposed that each of the six roof modules hand over the same
three fields -- what it adds, what it cuts, what it keeps -- so that the
modules can be combined without knowing each other. :class:`Contribution` and
:func:`combine` are copied here from that proposal (the projects cannot import
each other), with one fix: ``combine`` drops a ``None`` add.

This is an adapter only. It changes nothing in :mod:`roof_plants.design`,
:mod:`roof_plants.plant_voids` or :mod:`roof_plants.plant_drains` and copies none
of their logic: the pockets come from :func:`roof_plants.plant_voids.voids_by_plant`,
the bores from :func:`roof_plants.plant_drains.drained_voids`, and the wall is the
formula of :func:`roof_plants.design.keep`.

Not in the Contribution: :func:`roof_plants.plant_voids.water_drawing`, which
routes the roof's water around each planter. It does not add, cut or keep a
solid; it changes what the water step (Step 4) is given, so it changes the
deck and the slab that every other module works on. Whether a module may
change another step's inputs, and how the interface would say so, is for Wei
to decide. Until then, build the slab with the planted water step
(:func:`roof_plants.plant_drains.plant_steps_drained` does) before asking for
the Contribution.
"""

from dataclasses import dataclass

from compas_vol import nodes
from compas_vol.combinations import Intersection
from compas_vol.modifications import Shell

from .plant_drains import drained_voids
from .plant_voids import voids_by_plant

__all__ = ["Contribution", "combine", "plant_contribution"]


@dataclass
class Contribution:
    add: object = None   # solid the module puts in
    cut: object = None   # space the module needs empty
    keep: object = None  # solid no later process (erosion, foam, weathering) may remove


def combine(host, contributions):
    """(host + every add) - every cut. keep is not applied here.

    A module that only cuts (as the planters do) leaves ``add`` as ``None``.
    The ``None`` adds and cuts are dropped before the booleans, so such a
    module is simply not part of the union. (The original proposal passed the
    ``None`` adds on; ``nodes.boolean`` happens to drop them too, but this
    does not rely on it.)
    """
    adds = [c.add for c in contributions if c.add is not None]
    solid = nodes.boolean([host] + adds, "union", 0) if adds else host
    cuts = [c.cut for c in contributions if c.cut is not None]
    return nodes.boolean([solid] + cuts, "difference", 0) if cuts else solid


def plant_contribution(brief, drawing, specs, slab, radius=None):
    """The planters as a :class:`Contribution`: nothing added, the drained pockets cut, their walls kept.

    Parameters
    ----------
    brief, drawing, specs
        As :func:`roof_plants.plant_drains.plant_steps_drained` takes them:
        ``specs`` is one :func:`roof_plants.plants.opening_spec` per planter.
    slab : :class:`roof_plants.design.Slab`
        Step 5's output (``Roof.slab``), built with the planted water step.
        Its ``deck`` sets each planter's floor where ``depth_datum`` is
        ``local_min``; its ``solid`` clips the walls.
    radius : float, optional
        The drain bore radius, as :func:`roof_plants.plant_drains.planter_drains`; ``brief.outlet`` by default.

    Returns
    -------
    :class:`Contribution`
        ``add`` is ``None``. ``cut`` is the union of every planter pocket
        with its drain bores, the same pockets the drained Step 7 cuts.
        ``keep`` is the union of every planter's wall,
        ``Intersection(Shell(pocket, brief.planter_wall, 0.0), slab.solid)``,
        as :func:`roof_plants.design.keep` makes it. Both are ``None`` for a drawing with no planters.

    Raises
    ------
    :class:`roof_plants.plants.PlanterFitError`, ``ValueError``
        As :func:`roof_plants.plant_voids.voids_by_plant` and :func:`roof_plants.plant_drains.drain_points` raise them.
    """
    made = drained_voids(brief, drawing, slab, specs, voids_by_plant(brief, drawing, slab, specs), radius)
    walls = [Intersection(Shell(p, brief.planter_wall, 0.0), slab.solid) for p in made.pockets]
    return Contribution(add=None, cut=nodes.boolean(made.pockets, "union", 0),
                        keep=nodes.boolean(walls, "union", 0))
