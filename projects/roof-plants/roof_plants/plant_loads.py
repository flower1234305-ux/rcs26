"""Load inventory of the planted roof: how heavy each planter, each piece and the whole roof are.

An inventory only. It adds up masses read off the fields and turns them into
kN and kN/m2; it does not compare them with anything. Whether the roof can carry
them -- structural safety -- is outside what this tool does, and no function
here says "safe" or "unsafe".

Every density and load is a parameter (:class:`LoadAssumptions`). The defaults
are PROVISIONAL (2026-11-08): order-of-magnitude placeholders, there so the
numbers come out at all. :data:`SCENARIOS` (2026-11-09) sets the soil and the
standing water from the sources Wei approved, and :data:`SLAB_DENSITIES` lists
the slab densities to compare while the material is unspecified;
:func:`compare` puts them side by side. Comparing is all it does: it chooses
no scenario and no material.

Volumes are integrated by sampling the signed distance fields on a regular grid
of cell centres: a cell counts as solid (or soil) when the field at its centre
says so. The grid step is reported with every result; halve it to see how much
the numbers move.
"""

import dataclasses

import numpy as np

from .plant_voids import planter_floors

__all__ = ["G", "LoadAssumptions", "Scenario", "SCENARIOS", "SLAB_DENSITIES", "grid", "solid_volume", "soil_cells",
           "planter_loads", "piece_loads", "roof_loads", "loads", "plant_weights", "compare", "scenario_table",
           "slab_table", "load_table"]

#: Standard gravity, m/s2.
G = 9.80665


@dataclasses.dataclass
class LoadAssumptions:
    """The densities and loads the inventory multiplies by.

    PROVISIONAL (2026-11-08): the default values are not checked against any source.
    :data:`SCENARIOS` sets the soil and standing water from sources. Structural
    safety is outside this tool.

    Attributes
    ----------
    soil_dry : float
        Soil (growing medium) density when dry, kg/m3.
    soil_saturated : float
        The same soil at its maximum water capacity, kg/m3: the water it still holds after it
        has been saturated and then left to drain freely (in the FLL guideline, 2 hours of
        dripping). Not the soil with every pore full; standing water is ``ponding_mm``.
    slab : float
        Density of the roof's solid material, kg/m3. PROVISIONAL: the material is not
        specified anywhere; 2400 is about the 24 kN/m3 of normal-weight concrete in
        EN 1991-1-1 Table A.1 (x 100, simplified). The exact conversion is 24 kN/m3 / g =
        2447 kg/m3, so 2400 makes the slab about 1.9 % lighter than that table's value.
        Annex A gives dry densities: the water a wet slab takes up is not counted.
        :data:`SLAB_DENSITIES` lists others to compare.
    plant_kg_m2 : float
        Mass of the plants per m2 of planter footprint, kg/m2. 0 leaves the plants out.
        ``plant_weights`` in :func:`loads` overrides it per plant id.
    ponding_mm : float
        Depth of water standing on the soil in the saturated case, mm. 0 assumes none.
    water : float
        Density of water, kg/m3.
    """

    soil_dry: float = 1200.0
    soil_saturated: float = 1800.0
    slab: float = 2400.0
    plant_kg_m2: float = 0.0
    ponding_mm: float = 0.0
    water: float = 1000.0

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Scenario:
    """One set of assumptions to compare, with where its numbers come from."""

    name: str
    assumptions: LoadAssumptions
    source: str


#: The load cases compared by default (2026-11-09, Wei). Only the saturated case differs between them,
#: so :func:`scenario_table` compares saturated loads. ``soil_dry`` stays at its PROVISIONAL default.
SCENARIOS = (
    Scenario("light_medium", LoadAssumptions(soil_saturated=1400.0),
             "lightweight growing medium, saturated 1400 kg/m3: ZinCo Info Sheet 2026-01 p.1 (saturated 1300-1500)"),
    Scenario("mineral_soil", LoadAssumptions(soil_saturated=1800.0),
             "mineral soil, saturated 1800 kg/m3: FLL 2018 Table 24 p.115 (intensive soil / mineral mix 1600-1900)"),
    Scenario("drain_blocked", LoadAssumptions(soil_saturated=1800.0, ponding_mm=50.0),
             "mineral soil and 50 mm of standing water: ponding_mm 50 is Wei's to set, PROVISIONAL (2026-11-09)"),
)

#: Slab densities to compare, kg/m3, while the roof's material is unspecified: (density, material, source).
#: Annex A values are dry densities; water taken up by the slab is not counted.
SLAB_DENSITIES = (
    (2000.0, "lightweight concrete LC2.0, upper bound", "EN 1991-1-1 Table A.1 p.32"),
    (2100.0, "fired clay", "EN 1991-1-1 Table A.2 p.33"),
    (2350.0, "3D-printed concrete", "Le et al. 2012, Cement and Concrete Research 42(3):558-566 (abstract only)"),
    (2400.0, "current default", "-"),
    (2500.0, "reinforced concrete", "EN 1991-1-1 Table A.1 note 1"),
)


def _kn(kg):
    return kg * G / 1000.0


def grid(bounds, step):
    """Cell centres filling ``bounds`` (xmin, ymin, zmin, xmax, ymax, zmax), at most ``step`` apart.

    Each axis is split into equal cells, so the cells tile the box exactly.
    Returns ``(xs, ys, zs, cell_volume_mm3)``.

    Examples
    --------
    >>> xs, ys, zs, v = grid((0, 0, 0, 100, 50, 10), 30)
    >>> len(xs), len(ys), len(zs), v
    (4, 2, 1, 6250.0)
    """
    axes = []
    for lo, hi in zip(bounds[:3], bounds[3:]):
        n = max(1, int(np.ceil((hi - lo) / step - 1e-9)))
        size = (hi - lo) / n
        axes.append((lo + size * (np.arange(n) + 0.5), size))
    (xs, dx), (ys, dy), (zs, dz) = axes
    return xs, ys, zs, float(dx * dy * dz)


def solid_volume(field, bounds, step, chunk=40):
    """Volume of ``field < 0`` inside ``bounds``, in m3, sampled at ``step`` mm. Chunked along X to bound memory."""
    xs, ys, zs, cell = grid(bounds, step)
    count = 0
    for i in range(0, len(xs), chunk):
        x = xs[i:i + chunk]
        count += int((field.get_distance_numpy(x[:, None, None], ys[None, :, None], zs[None, None, :]) < 0).sum())
    return count * cell / 1e9


def soil_cells(pocket, floor, deck, bounds, step):
    """Where a planter holds soil: inside the pocket, above its floor, below the deck.

    The soil is taken to fill the pocket from its flat floor up to the deck
    surface. A drain bore under the floor is not soil, and the 80 mm blend
    ``carve`` puts on the pocket's edge is not counted. Returns
    ``(xs, ys, zs, cell_volume_mm3, mask)``, ``mask`` of shape (x, y, z).
    """
    lo = list(bounds[:3])
    lo[2] = max(lo[2], floor)
    xs, ys, zs, cell = grid(tuple(lo) + tuple(bounds[3:]), step)
    inside = pocket.get_distance_numpy(xs[:, None, None], ys[None, :, None], zs[None, None, :]) < 0
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    below_deck = zs[None, None, :] <= np.asarray(deck.height_at(X, Y))[:, :, None]
    return xs, ys, zs, cell, inside & below_deck


def _nearest_piece(pieces, X, Y):
    """Index of the piece whose plan box is nearest each point (0 inside it), so a clearance gap is not lost."""
    best = np.full(X.shape, np.inf)
    index = np.zeros(X.shape, dtype=int)
    for n, piece in enumerate(pieces):
        x0, y0, _, x1, y1, _ = piece.bounds
        d = np.hypot(np.maximum(np.maximum(x0 - X, X - x1), 0), np.maximum(np.maximum(y0 - Y, Y - y1), 0))
        closer = d < best
        best, index = np.where(closer, d, best), np.where(closer, n, index)
    return index


def planter_loads(brief, drawing, specs, built, assumptions=None, plant_weights=None, step=25.0, pieces=None):
    """Each planter's soil volume and loads; with ``pieces``, also how they split between the pieces.

    Returns a list of dicts, one per planter: ``soil_m3``, ``footprint_m2`` (plan
    area holding soil), ``soil_dry_kN``, ``soil_saturated_kN``, ``plant_kN``,
    ``ponding_kN``, ``dry_kN`` (soil dry + plants), ``saturated_kN`` (soil
    saturated + plants + ponding), the same two per m2 of footprint, and
    ``step_mm``. With ``pieces`` (the assembly's pieces), ``by_piece`` maps a
    piece's position in that list to ``(soil_m3, footprint_m2)``.
    """
    a = assumptions or LoadAssumptions()
    weights = plant_weights or {}
    floors = planter_floors(brief, drawing, specs, built.slab.deck)
    rows = []
    for n, (outline, spec, floor, pocket) in enumerate(zip(drawing.planters, specs, floors, built.voids.pockets)):
        points = np.array(outline)[:, :2]
        reach = max(spec["offset"] + spec["rim"], spec["offset"], 0.0) + 2 * step
        bounds = (points[:, 0].min() - reach, points[:, 1].min() - reach, floor,
                  points[:, 0].max() + reach, points[:, 1].max() + reach, brief.thickness)
        xs, ys, zs, cell, mask = soil_cells(pocket, floor, built.slab.deck, bounds, step)
        columns = mask.sum(axis=2)
        footprint = columns > 0
        column_area = (xs[1] - xs[0]) * (ys[1] - ys[0]) if len(xs) > 1 and len(ys) > 1 else step * step
        soil = float(mask.sum() * cell / 1e9)
        area = float(footprint.sum() * column_area / 1e6)
        plant = weights.get(spec["id"], a.plant_kg_m2)
        row = {"planter": n, "plant": spec["id"], "soil_m3": soil, "footprint_m2": area,
               "soil_dry_kN": _kn(soil * a.soil_dry), "soil_saturated_kN": _kn(soil * a.soil_saturated),
               "plant_kN": _kn(area * plant), "ponding_kN": _kn(area * a.ponding_mm / 1000.0 * a.water),
               "step_mm": float(step)}
        row["dry_kN"] = row["soil_dry_kN"] + row["plant_kN"]
        row["saturated_kN"] = row["soil_saturated_kN"] + row["plant_kN"] + row["ponding_kN"]
        row["dry_kN_m2"] = row["dry_kN"] / area if area else 0.0
        row["saturated_kN_m2"] = row["saturated_kN"] / area if area else 0.0
        if pieces is not None:
            X, Y = np.meshgrid(xs, ys, indexing="ij")
            owner = _nearest_piece(pieces, X, Y)
            row["by_piece"] = {int(k): (float(columns[owner == k].sum() * cell / 1e9),
                                        float(footprint[owner == k].sum() * column_area / 1e6))
                               for k in np.unique(owner[footprint])}
        rows.append(row)
    return rows


def piece_loads(brief, built, planters, assumptions=None, step=50.0, solids=None):
    """Each kit piece's own weight and the planters' loads on it, in kN and kN/m2 of the piece's plan box.

    ``planters`` is :func:`planter_loads` run with ``pieces``. The piece's own
    weight is ``design.roof`` (the design before weathering and joints, which
    only take material away and add dowels) sampled over its box at ``step``.
    ``solids`` (m3 per piece, in assembly order) skips that sampling, so
    several sets of densities can share one.
    """
    a = assumptions or LoadAssumptions()
    pieces = list(built.assembly)
    rows = []
    for k, piece in enumerate(pieces):
        x0, y0, _, x1, y1, _ = piece.bounds
        area = (x1 - x0) * (y1 - y0) / 1e6
        solid = solid_volume(built.design.roof, piece.bounds, step) if solids is None else solids[k]
        row = {"piece": piece.name, "role": piece.role, "plan_m2": area, "solid_m3": solid,
               "slab_kN": _kn(solid * a.slab), "soil_m3": 0.0, "dry_extra_kN": 0.0, "saturated_extra_kN": 0.0,
               "step_mm": float(step)}
        for p in planters:
            soil, footprint = p["by_piece"].get(k, (0.0, 0.0))
            if not soil and not footprint:
                continue
            share = footprint / p["footprint_m2"] if p["footprint_m2"] else 0.0
            row["soil_m3"] += soil
            row["dry_extra_kN"] += _kn(soil * a.soil_dry) + share * p["plant_kN"]
            row["saturated_extra_kN"] += _kn(soil * a.soil_saturated) + share * (p["plant_kN"] + p["ponding_kN"])
        row["dry_kN"] = row["slab_kN"] + row["dry_extra_kN"]
        row["saturated_kN"] = row["slab_kN"] + row["saturated_extra_kN"]
        row["dry_kN_m2"] = row["dry_kN"] / area
        row["saturated_kN_m2"] = row["saturated_kN"] / area
        rows.append(row)
    return rows


def roof_loads(brief, pieces, planters):
    """The whole roof: the pieces summed, per m2 of the roof's plan (length x width)."""
    area = brief.length * brief.width / 1e6
    total = {key: float(sum(p[key] for p in pieces)) for key in ("solid_m3", "slab_kN", "soil_m3", "dry_kN",
                                                                  "saturated_kN")}
    total.update({"plan_m2": area, "dry_kN_m2": total["dry_kN"] / area, "saturated_kN_m2": total["saturated_kN"] / area,
                  "planter_soil_m3": float(sum(p["soil_m3"] for p in planters))})
    return total


def loads(brief, drawing, specs, built, assumptions=None, plant_weights=None, soil_step=25.0, slab_step=50.0):
    """The whole inventory: planters, pieces, roof, and the assumptions and steps it used.

    ``plant_weights`` maps a plant id to kg/m2, overriding
    ``assumptions.plant_kg_m2`` for that plant (for example from the
    ``mature_weight_kg_m2`` column of ``plants.csv``, once it has sourced values).
    Measured 2026-11-08 with the default steps (soil 25 mm, slab 50 mm) on the default brief and
    drawing.json, on a built roof: 2.5 s per call (three runs, 2.50-2.57 s; 20-thread Intel desktop).
    """
    a = assumptions or LoadAssumptions()
    planters = planter_loads(brief, drawing, specs, built, a, plant_weights, soil_step, list(built.assembly))
    pieces = piece_loads(brief, built, planters, a, slab_step)
    return {"assumptions": a.to_dict(), "soil_step_mm": float(soil_step), "slab_step_mm": float(slab_step),
            "planters": planters, "pieces": pieces, "roof": roof_loads(brief, pieces, planters)}


def plant_weights(plants):
    """``{id: kg/m2}`` from plant records that have ``mature_weight_kg_m2`` (``plants.csv``), for :func:`loads`."""
    return {pid: float(r["mature_weight_kg_m2"]) for pid, r in plants.items() if "mature_weight_kg_m2" in r}


def compare(brief, drawing, specs, built, scenarios=SCENARIOS, plant_weights=None, slab_densities=SLAB_DENSITIES,
            soil_step=25.0, slab_step=50.0):
    """The inventory under each scenario, and the slab's weight under each density. Compares; chooses nothing.

    The slab is sampled once and shared. Returns ``{"scenarios": {name: loads result}, "sources": {name: source},
    "plant_weights", "plant_weights_note", "solid_m3", "slab_step_mm", "soil_step_mm", "slab": [rows]}``; each
    slab row has the density, material, source, the slab's kN and kN/m2, and the whole roof's saturated kN/m2
    under every scenario with that slab. ``plant_weights`` is recorded as used; without it the plants weigh each
    scenario's ``plant_kg_m2`` (0 in every default scenario), and ``plant_weights_note`` says so.
    """
    pieces = list(built.assembly)
    solids = [solid_volume(built.design.roof, p.bounds, slab_step) for p in pieces]
    results, sources = {}, {}
    for sc in scenarios:
        planters = planter_loads(brief, drawing, specs, built, sc.assumptions, plant_weights, soil_step, pieces)
        rows = piece_loads(brief, built, planters, sc.assumptions, slab_step, solids)
        results[sc.name] = {"assumptions": sc.assumptions.to_dict(), "planters": planters, "pieces": rows,
                            "roof": roof_loads(brief, rows, planters)}
        sources[sc.name] = sc.source
    area = brief.length * brief.width / 1e6
    solid = float(sum(solids))
    slab = []
    for density, material, source in slab_densities:
        row = {"density": density, "material": material, "source": source, "slab_kN": _kn(solid * density)}
        row["slab_kN_m2"] = row["slab_kN"] / area
        for name, r in results.items():
            extra = sum(p["saturated_extra_kN"] for p in r["pieces"])
            row[name + "_kN_m2"] = (row["slab_kN"] + extra) / area
        slab.append(row)
    if plant_weights:
        note = "plant loads by id (kg/m2), as given"
    else:
        note = "plant loads NOT counted: no plant_weights given; each scenario's plant_kg_m2 is used ({})".format(
            ", ".join("{} {:g}".format(sc.name, sc.assumptions.plant_kg_m2) for sc in scenarios))
    return {"scenarios": results, "sources": sources, "plant_weights": dict(plant_weights or {}),
            "plant_weights_note": note, "solid_m3": solid, "slab_step_mm": float(slab_step),
            "soil_step_mm": float(soil_step), "slab": slab}


def scenario_table(compared):
    """Saturated kN per planter and for the roof (kN and kN/m2), one column per scenario."""
    names = list(compared["scenarios"])
    first = compared["scenarios"][names[0]]
    rows = []
    for n, p in enumerate(first["planters"]):
        row = {"what": "P{} {}".format(n, p["plant"]), "unit": "kN"}
        row.update({name: compared["scenarios"][name]["planters"][n]["saturated_kN"] for name in names})
        rows.append(row)
    row = {"what": "planters, total", "unit": "kN"}
    row.update({name: sum(p["saturated_kN"] for p in compared["scenarios"][name]["planters"]) for name in names})
    rows.append(row)
    for key, unit in (("saturated_kN", "kN"), ("saturated_kN_m2", "kN/m2")):
        row = {"what": "roof (slab + planters)", "unit": unit}
        row.update({name: compared["scenarios"][name]["roof"][key] for name in names})
        rows.append(row)
    return load_table(rows, [("", "what"), ("unit", "unit")] + [(name, name) for name in names])


def slab_table(compared):
    """The slab under each density, and the roof's saturated kN/m2 under each scenario with it."""
    names = list(compared["scenarios"])
    return load_table(compared["slab"], [("kg/m3", "density"), ("slab_kN", "slab_kN"), ("slab_kN/m2", "slab_kN_m2")]
                      + [(name + " kN/m2", name + "_kN_m2") for name in names] + [("material", "material")])


def load_table(rows, columns):
    """Rows as a fixed-width text table; ``columns`` are ``(heading, field)`` pairs."""

    def cell(value):
        return "{:.2f}".format(value) if isinstance(value, float) else str(value)

    grid_ = [[h for h, _ in columns]] + [[cell(r[f]) for _, f in columns] for r in rows]
    widths = [max(len(line[i]) for line in grid_) for i in range(len(columns))]
    return "\n".join("  ".join(t.ljust(w) for t, w in zip(line, widths)).rstrip() for line in grid_)
