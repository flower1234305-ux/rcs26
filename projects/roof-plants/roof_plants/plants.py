"""Plant -> planter opening: the three numbers one planter's pocket is cut with.

Pure Python on purpose: this module imports no Rhino, no compas_vol and no
numpy, so its functions run and are tested anywhere, and can sit behind a
Grasshopper component later. (Importing it as ``roof_plants.plants`` still runs
the package's ``__init__``, which needs compas_vol.)
"""

import json

__all__ = ["REQUIRED", "DATUMS", "PlanterFitError", "opening_spec", "load_plants", "assign", "reassign",
           "brief_spec", "check_control", "floor_height", "check_fit"]

#: Fields every plant record must carry.
REQUIRED = ("id", "name_zh", "root_type", "growth", "offset", "rim", "depth", "depth_datum", "source")

#: The plant id that stands for the original roof's planter.
CONTROL = "control"

#: What ``depth`` is measured from: the slab's nominal top, or the lowest deck over the planter.
DATUMS = ("nominal", "local_min")


class PlanterFitError(ValueError):
    """A planter's floor leaves too little slab under it for its wall."""


def opening_spec(plant):
    """The opening one planter is cut with, from the plant growing in it.

    Parameters
    ----------
    plant : dict
        One record of ``plants.json``.

    Returns
    -------
    dict
        ``{"id", "offset", "rim", "depth", "depth_datum", "top"}``, lengths in mm:

        * ``offset`` -- how far the drawn outline is grown (+) or shrunk (-)
          at the pocket floor;
        * ``rim`` -- how much further it flares out from the floor to the top;
        * ``depth`` -- how far the flat floor lies below ``depth_datum``;
        * ``depth_datum`` -- one of :data:`DATUMS`, see :func:`floor_height`;
        * ``top`` -- ``offset + rim``, the growth of the outline at the top.

    Raises
    ------
    KeyError
        A field is missing; the message names it.
    ValueError
        A value is not a number, ``depth <= 0``, ``rim < 0`` or the datum is unknown.

    Notes
    -----
    TEMPORARY SHORTCUT (2026-11-03): ``plants.json`` stores the three opening
    values directly, and this function only validates and passes them on. The
    values are assumptions with no literature behind them. Later this must be
    replaced by a conversion from the plant's root type, growth direction and
    rooting depth (根系類型 + 生長方向 + 根深) to ``offset``, ``rim`` and
    ``depth``. Callers depend only on the returned dict, so that change stays
    inside this function.

    Examples
    --------
    >>> spec = opening_spec({"id": "x", "name_zh": "x", "root_type": "x", "growth": "x",
    ...                      "offset": 300, "rim": 400, "depth": 200, "depth_datum": "local_min", "source": "x"})
    >>> spec["top"], spec["depth"]
    (700.0, 200.0)
    """
    if not isinstance(plant, dict):
        raise TypeError("plant must be a dict, got {}".format(type(plant).__name__))
    missing = [key for key in REQUIRED if key not in plant]
    if missing:
        raise KeyError("plant {!r} is missing field(s): {}".format(plant.get("id", "?"), ", ".join(missing)))

    values = {}
    for key in ("offset", "rim", "depth"):
        value = plant[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            raise ValueError("plant {!r}: {} must be a number, got {!r}".format(plant["id"], key, value))
        values[key] = float(value)
    if values["depth"] <= 0:
        raise ValueError("plant {!r}: depth must be > 0, got {}".format(plant["id"], values["depth"]))
    if values["rim"] < 0:
        raise ValueError("plant {!r}: rim must be >= 0, got {}".format(plant["id"], values["rim"]))
    if plant["depth_datum"] not in DATUMS:
        raise ValueError("plant {!r}: depth_datum must be one of {}, got {!r}".format(
            plant["id"], ", ".join(DATUMS), plant["depth_datum"]))

    return {"id": plant["id"], "offset": values["offset"], "rim": values["rim"], "depth": values["depth"],
            "depth_datum": plant["depth_datum"], "top": values["offset"] + values["rim"]}


def load_plants(path):
    """``plants.json`` as ``{id: record}``; duplicate ids raise ``ValueError``."""
    with open(path, encoding="utf-8") as f:
        records = json.load(f)["plants"]
    plants = {}
    for record in records:
        if record["id"] in plants:
            raise ValueError("duplicate plant id {!r}".format(record["id"]))
        plants[record["id"]] = record
    return plants


def assign(plants, planter_plants, count):
    """One plant record per planter, in drawing order.

    ``planter_plants`` is the parsed ``planter_plants.json``; ``count`` is how
    many planters the drawing has. Every planter must be assigned exactly once
    and every id must exist in ``plants``.
    """
    rows = planter_plants["planters"]
    indices = sorted(row["index"] for row in rows)
    if indices != list(range(count)):
        raise ValueError("planter_plants.json must assign planters 0..{} once each, got {}".format(count - 1, indices))
    unknown = [row["plant"] for row in rows if row["plant"] not in plants]
    if unknown:
        raise KeyError("unknown plant id(s) in planter_plants.json: {}".format(", ".join(unknown)))
    return [plants[row["plant"]] for row in sorted(rows, key=lambda r: r["index"])]


def reassign(planter_plants, index, plant_id):
    """A copy of ``planter_plants`` with one planter growing another plant.

    Examples
    --------
    >>> reassign({"planters": [{"index": 0, "plant": "a"}]}, 0, "b")
    {'planters': [{'index': 0, 'plant': 'b'}]}

    Raises ``ValueError`` if no planter has that index.
    """
    if not any(row["index"] == index for row in planter_plants["planters"]):
        raise ValueError("no planter {}; there are {}".format(index, [r["index"] for r in planter_plants["planters"]]))
    rows = [dict(row, plant=plant_id) if row["index"] == index else dict(row) for row in planter_plants["planters"]]
    return dict(planter_plants, planters=rows)


def brief_spec(brief):
    """The one opening the original roof gives every planter, as an :func:`opening_spec` result."""
    return {"id": "control", "offset": 0.0, "rim": float(brief.planter_rim), "depth": float(brief.planter_depth),
            "depth_datum": "nominal", "top": float(brief.planter_rim)}


def check_control(specs, brief):
    """Raise ``ValueError`` if a planter called ``control`` is not the planter this brief gives the original roof.

    ``plants.json`` writes the control's numbers out, and they match the default
    ``Brief``. With another brief the control would silently stop being a control.

    Examples
    --------
    >>> from types import SimpleNamespace
    >>> brief = SimpleNamespace(planter_depth=350.0, planter_rim=220.0)
    >>> check_control([brief_spec(brief)], brief)
    """
    original = brief_spec(brief)
    for n, spec in enumerate(specs):
        different = [k for k in ("offset", "rim", "depth", "depth_datum")
                     if spec["id"] == CONTROL and spec[k] != original[k]]
        if different:
            raise ValueError("planter {} is control, but its {} differ from this brief's planter ({}): change "
                             "plants.json, or use brief_spec(brief) for it".format(
                                 n, ", ".join("{} {}".format(k, spec[k]) for k in different),
                                 ", ".join("{} {}".format(k, original[k]) for k in different)))


def floor_height(spec, thickness, deck_min=None):
    """The height of a planter's flat floor, in mm above the soffit.

    ``nominal`` measures from the slab's top (``thickness``), as the original
    does; the deck falls to the drains, so the soil is shallower than ``depth``.
    ``local_min`` measures from ``deck_min``, the lowest real deck over the
    planter, so ``depth`` is the shallowest soil the planter has.

    Examples
    --------
    >>> floor_height({"depth": 350.0, "depth_datum": "nominal"}, 600.0)
    250.0
    >>> floor_height({"depth": 200.0, "depth_datum": "local_min"}, 600.0, 515.0)
    315.0
    """
    if spec["depth_datum"] == "nominal":
        return thickness - spec["depth"]
    if deck_min is None:
        raise ValueError("depth_datum {!r} needs the deck height".format(spec["depth_datum"]))
    return deck_min - spec["depth"]


def check_fit(specs, floors, planter_wall):
    """Raise :class:`PlanterFitError` if any floor leaves less than ``planter_wall`` above the soffit (z = 0).

    The message lists every planter that does not fit and the deepest
    ``depth`` that would, so it can be fixed in one go.

    Examples
    --------
    >>> check_fit([{"id": "a", "depth": 200.0}], [315.0], 150.0)
    """
    problems = []
    for n, (spec, floor) in enumerate(zip(specs, floors)):
        if floor < planter_wall:
            problems.append("planter {} ({}): floor at z = {:.1f} leaves less than planter_wall {} mm above the "
                            "soffit; depth {} must be at most {} mm".format(
                                n, spec["id"], floor, planter_wall, spec["depth"],
                                int(spec["depth"] + floor - planter_wall)))
    if problems:
        raise PlanterFitError("; ".join(problems))
