"""The load inventory: volumes against shapes worked out by hand, and sums that must agree."""

import json
import os
import types

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.plant_drains import plant_steps_drained
from roof_plants.plant_loads import (
    G,
    SCENARIOS,
    SLAB_DENSITIES,
    LoadAssumptions,
    compare,
    grid,
    load_table,
    loads,
    plant_weights,
    planter_loads,
    scenario_table,
    slab_table,
    solid_volume,
)
from roof_plants.plants import assign, load_plants, opening_spec

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==============================================================================
# against shapes worked out by hand
# ==============================================================================


def test_the_grid_tiles_the_box_exactly():
    xs, ys, zs, cell = grid((0, 0, 0, 1000, 700, 330), 50)
    assert len(xs) * len(ys) * len(zs) * cell == pytest.approx(1000 * 700 * 330)
    assert xs[0] == 25 and zs[-1] == pytest.approx(330 - 330 / 7 / 2)


def test_a_box_has_its_own_volume():
    block = roof.box(1000, 2000, 100, 2000, 2500, 400)                       # 1.0 x 0.5 x 0.3 m
    assert solid_volume(block, (0, 0, 0, 3000, 3000, 600), 25.0) == pytest.approx(0.15, rel=1e-9)


def test_a_sphere_converges_on_its_volume():
    from compas_vol import nodes

    ball = nodes.sphere(None, 400.0)
    exact = 4 / 3 * np.pi * 0.4 ** 3
    assert solid_volume(ball, (-500, -500, -500, 500, 500, 500), 50.0) == pytest.approx(exact, rel=0.02)
    assert solid_volume(ball, (-500, -500, -500, 500, 500, 500), 20.0) == pytest.approx(exact, rel=0.005)


def flat_planter(deck_height=550.0, depth=350.0):
    """One square planter, 1 x 1 m, straight walls, under a flat deck: soil 1 x 1 x (deck - floor)."""
    brief = roof.Brief()
    outline = roof.outline([(2000, 2000), (3000, 2000), (3000, 3000), (2000, 3000)])
    floor = brief.thickness - depth
    pocket = roof.box(2000, 2000, floor, 3000, 3000, brief.thickness + 500)
    deck = types.SimpleNamespace(height_at=lambda x, y: np.full(np.broadcast_shapes(np.shape(x), np.shape(y)),
                                                                deck_height))
    built = types.SimpleNamespace(slab=types.SimpleNamespace(deck=deck), voids=types.SimpleNamespace(pockets=[pocket]))
    drawing = types.SimpleNamespace(planters=[outline])
    spec = {"id": "t", "offset": 0.0, "rim": 0.0, "depth": depth, "depth_datum": "nominal", "top": 0.0}
    return brief, drawing, [spec], built


def test_a_square_planter_holds_what_it_should_and_weighs_that():
    brief, drawing, specs, built = flat_planter()
    a = LoadAssumptions(soil_dry=1000.0, soil_saturated=2000.0, plant_kg_m2=50.0, ponding_mm=20.0)
    (row,) = planter_loads(brief, drawing, specs, built, a, step=25.0)
    assert row["soil_m3"] == pytest.approx(0.3, rel=1e-9)                    # 1 x 1 x (550 - 250) mm
    assert row["footprint_m2"] == pytest.approx(1.0, rel=1e-9)
    assert row["soil_dry_kN"] == pytest.approx(0.3 * 1000 * G / 1000)
    assert row["soil_saturated_kN"] == pytest.approx(0.3 * 2000 * G / 1000)
    assert row["plant_kN"] == pytest.approx(50 * G / 1000)
    assert row["ponding_kN"] == pytest.approx(0.02 * 1000 * G / 1000)
    assert row["dry_kN"] == pytest.approx(row["soil_dry_kN"] + row["plant_kN"])
    assert row["saturated_kN"] == pytest.approx(row["soil_saturated_kN"] + row["plant_kN"] + row["ponding_kN"])
    assert row["dry_kN_m2"] == pytest.approx(row["dry_kN"])                  # 1 m2


def test_a_plant_weight_by_id_overrides_the_default():
    brief, drawing, specs, built = flat_planter()
    (row,) = planter_loads(brief, drawing, specs, built, LoadAssumptions(plant_kg_m2=10.0), {"t": 30.0})
    assert row["plant_kN"] == pytest.approx(30 * G / 1000)


def test_the_defaults_are_marked_provisional():
    assert "PROVISIONAL" in LoadAssumptions.__doc__ and "safety" in LoadAssumptions.__doc__


# ==============================================================================
# the real roof: the parts add up
# ==============================================================================


@pytest.fixture(scope="module")
def inventory(v1_plants):
    pytest.importorskip("skfmm", reason="needs the processes extra")
    brief = roof.Brief(voxel=60.0)
    drawing = roof.Drawing.load(os.path.join(HERE, "drawing.json"))
    with open(os.path.join(HERE, "planter_plants.json"), encoding="utf-8") as f:
        chosen = json.load(f)
    specs = [opening_spec(p) for p in assign(v1_plants, chosen,
                                            len(drawing.planters))]
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    return brief, loads(brief, drawing, specs, built, slab_step=100.0)


def test_every_piece_and_every_planter_is_listed(inventory):
    _, result = inventory
    assert len(result["pieces"]) == 53 and len(result["planters"]) == 4
    assert result["slab_step_mm"] == 100.0 and result["soil_step_mm"] == 25.0


def test_the_soil_in_the_pieces_is_the_soil_in_the_planters(inventory):
    _, result = inventory
    in_pieces = sum(p["soil_m3"] for p in result["pieces"])
    assert in_pieces == pytest.approx(sum(p["soil_m3"] for p in result["planters"]), rel=1e-9)
    assert all(0.1 < p["soil_m3"] < 2.0 for p in result["planters"])


def test_the_roof_is_the_sum_of_its_pieces(inventory):
    brief, result = inventory
    total = result["roof"]
    assert total["dry_kN"] == pytest.approx(sum(p["dry_kN"] for p in result["pieces"]))
    assert total["saturated_kN"] >= total["dry_kN"]
    assert total["dry_kN_m2"] == pytest.approx(total["dry_kN"] / (brief.length * brief.width / 1e6))
    # the solid is less than the full 18 x 12 x 0.6 m block: the foam, the openings and the planters are out of it
    assert 0.3 * 129.6 < total["solid_m3"] < 129.6


def test_nothing_is_judged(inventory):
    _, result = inventory
    text = json.dumps(result).lower() + load_table(result["planters"], [("P", "planter"), ("kN", "dry_kN")]).lower()
    assert "safe" not in text and "ok" not in [k.lower() for p in result["pieces"] for k in p]


# ==============================================================================
# scenarios and slab densities: compared, not chosen
# ==============================================================================


def test_the_scenarios_are_the_approved_ones():
    by_name = {s.name: s for s in SCENARIOS}
    assert [s.name for s in SCENARIOS] == ["light_medium", "mineral_soil", "drain_blocked"]
    assert by_name["light_medium"].assumptions.soil_saturated == 1400.0
    assert by_name["mineral_soil"].assumptions.soil_saturated == 1800.0
    assert (by_name["drain_blocked"].assumptions.soil_saturated, by_name["drain_blocked"].assumptions.ponding_mm) \
        == (1800.0, 50.0)
    assert "PROVISIONAL" in by_name["drain_blocked"].source
    assert all(s.assumptions.slab == 2400.0 for s in SCENARIOS)
    assert [d for d, _, _ in SLAB_DENSITIES] == [2000.0, 2100.0, 2350.0, 2400.0, 2500.0]
    assert LoadAssumptions().slab == 2400.0 and "EN 1991-1-1" in LoadAssumptions.__doc__


def test_plant_weights_come_from_the_plant_table():
    weights = plant_weights(load_plants(os.path.join(HERE, "plants.json")))
    assert weights == {"control": 0.0, "group1_creeping": 10.0, "group3_upright": 20.0}


def test_compare_adds_up_and_judges_nothing():
    brief, drawing, specs, built = flat_planter()
    piece = types.SimpleNamespace(bounds=(0.0, 0.0, 0.0, 5000.0, 5000.0, 600.0), name="p", role="panel")
    built.assembly = [piece]
    built.design = types.SimpleNamespace(roof=roof.box(0, 0, 0, 5000, 5000, 100))      # 2.5 m3 of slab
    brief = roof.Brief(length=5000.0, width=5000.0)
    result = compare(brief, drawing, specs, built, plant_weights={"t": 20.0}, slab_step=50.0)
    assert result["solid_m3"] == pytest.approx(2.5)
    light, mineral, blocked = (result["scenarios"][n]["planters"][0] for n in ("light_medium", "mineral_soil",
                                                                                "drain_blocked"))
    assert light["soil_saturated_kN"] == pytest.approx(0.3 * 1400 * G / 1000)
    assert mineral["soil_saturated_kN"] == pytest.approx(0.3 * 1800 * G / 1000)
    assert blocked["ponding_kN"] == pytest.approx(0.05 * 1000 * G / 1000) and mineral["ponding_kN"] == 0.0
    assert light["plant_kN"] == pytest.approx(20 * G / 1000)
    by_density = {row["density"]: row for row in result["slab"]}
    assert by_density[2000.0]["slab_kN"] == pytest.approx(2.5 * 2000 * G / 1000)
    assert by_density[2400.0]["mineral_soil_kN_m2"] == pytest.approx(result["scenarios"]["mineral_soil"]["roof"]
                                                                      ["saturated_kN_m2"])
    text = (scenario_table(result) + slab_table(result) + json.dumps(result)).lower()
    assert "safe" not in text
    assert result["plant_weights"] == {"t": 20.0} and "NOT" not in result["plant_weights_note"]


def test_compare_says_when_the_plants_are_left_out():
    brief, drawing, specs, built = flat_planter()
    built.assembly = [types.SimpleNamespace(bounds=(0.0, 0.0, 0.0, 5000.0, 5000.0, 600.0), name="p", role="panel")]
    built.design = types.SimpleNamespace(roof=roof.box(0, 0, 0, 5000, 5000, 100))
    result = compare(roof.Brief(length=5000.0, width=5000.0), drawing, specs, built, slab_step=100.0)
    assert result["plant_weights"] == {} and "NOT counted" in result["plant_weights_note"]
    assert result["scenarios"]["mineral_soil"]["planters"][0]["plant_kN"] == 0.0
