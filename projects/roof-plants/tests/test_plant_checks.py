"""Every planter rule on the real planted roof, and a deliberate violation of each."""

import json
import os
import types

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.plant_checks import (
    all_ok,
    clearance_check,
    drain_check,
    floor_check,
    light_plan,
    planter_rows,
    table,
    top_opening,
    wall_normal,
    water_check,
)
from roof_plants.plant_voids import plant_steps, planter_floors, pocket
from roof_plants.plants import assign, brief_spec, opening_spec

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def brief():
    return roof.Brief(voxel=60.0)


@pytest.fixture(scope="module")
def drawing():
    return roof.Drawing.load(os.path.join(HERE, "drawing.json"))


@pytest.fixture(scope="module")
def specs(drawing, v1_plants):
    with open(os.path.join(HERE, "planter_plants.json"), encoding="utf-8") as f:
        chosen = json.load(f)
    return [opening_spec(p) for p in assign(v1_plants, chosen,
                                            len(drawing.planters))]


@pytest.fixture(scope="module")
def built(brief, drawing, specs):
    return roof.design_roof(brief, drawing, steps=plant_steps(brief, specs))


@pytest.fixture(scope="module")
def rows(brief, drawing, specs, built):
    return planter_rows(brief, drawing, specs, built)


# ==============================================================================
# the real roof keeps every rule
# ==============================================================================


def test_every_planter_passes(rows):
    assert [row["ok"] for row in rows] == [True] * 4, table(rows)


def test_the_soil_is_as_deep_as_each_datum_promises(rows, specs):
    for row, spec in zip(rows, specs):
        if spec["depth_datum"] == "local_min":
            assert row["soil_min"] >= spec["depth"] - 1e-6
        else:
            assert row["floor_z"] == 600.0 - spec["depth"]


def test_a_wall_really_stands_under_each_floor(brief, rows):
    for row in rows:
        assert row["wall_margin"] >= 0
        assert row["kept_under_floor_min"] >= brief.planter_wall - 10.0


def test_the_water_still_drains(built):
    water = water_check(built.incision)
    assert (water["stranded"], water["reverse_falls"]) == (0, 0) and water["ok"]


def test_a_control_planter_keeps_its_original_pocket(brief, drawing, specs, built):
    original = roof.voids(brief, drawing, built.slab).pockets
    rng = np.random.default_rng(5)
    for n, spec in enumerate(specs):
        if spec["id"] != "control":
            continue
        a = np.array(drawing.planters[n])[:, :2]
        x = rng.uniform(a[:, 0].min() - 600, a[:, 0].max() + 600, 20000)
        y = rng.uniform(a[:, 1].min() - 600, a[:, 1].max() + 600, 20000)
        z = rng.uniform(-50, brief.thickness + 50, 20000)
        assert np.abs(built.voids.pockets[n].get_distance_numpy(x, y, z)
                      - original[n].get_distance_numpy(x, y, z)).max() == 0.0


def test_a_mixed_roof_changes_the_deck_even_over_an_unchanged_planter(brief, drawing, built):
    """Only the pocket of a control planter is sure to stay. Water runs differently once another's offset changes."""
    original = roof.water(brief, drawing, built.beams)
    assert np.abs(built.incision.surface - original.surface).max() > 0.0


def test_the_wall_formula_matches_the_contours_of_the_field(brief):
    """A straight wall away from the corners: the least distance between the field's 0 and planter_wall levels."""
    import contourpy

    square = roof.outline([(2000, 2000), (5000, 2000), (5000, 5000), (2000, 5000)])
    spec = {"id": "t", "offset": 300.0, "rim": 400.0, "depth": 200.0, "top": 700.0}
    floor = 267.0
    xs = np.arange(1000.0, 2400.0, 2.0)
    zs = np.arange(floor + 130.0, brief.thickness, 2.0)    # above the blend into the floor
    field = pocket(brief, square, spec, floor).get_distance_numpy(xs[:, None, None], np.full((1, 1, 1), 3500.0),
                                                                  zs[None, None, :])[:, 0, :]
    contours = contourpy.contour_generator(xs, zs, field.T)
    inner, outer = contours.lines(0.0)[0], contours.lines(brief.planter_wall)[0]
    measured = np.hypot(inner[:, 0, None] - outer[:, 0, None].T, inner[:, 1, None] - outer[:, 1, None].T).min()
    assert wall_normal(brief, spec, floor) == pytest.approx(measured, rel=0.03)
    assert wall_normal(brief, spec, floor) < brief.planter_wall / 2     # far from the 150 the field keeps
    assert wall_normal(brief, dict(spec, rim=0.0), floor) == brief.planter_wall


def test_wall_normal_is_reported_and_does_not_decide_ok(rows):
    thin = [row for row in rows if row["wall_normal_min"] < 100.0]
    assert thin and all(row["ok"] for row in thin)


def test_the_opening_at_the_deck_follows_the_plant(brief, drawing, specs, built, rows):
    by_plant = {row["plant"]: row for row in rows}
    assert by_plant["group3_upright"]["deck_area"] < by_plant["group1_creeping"]["deck_area"]
    opened = top_opening(brief, drawing.planters[2], specs[2], built.design.drawn, built.slab.deck)
    assert opened["deck_area"] <= opened["nominal_area"]     # the deck lies below t, where the rim is narrower


def test_all_ok_and_the_table(rows):
    assert all_ok(rows, {"ok": True}) and not all_ok(rows, {"ok": False})
    assert not all_ok([dict(rows[0], ok=False)], {"ok": True})
    assert "group3_upright" in table(rows) and "soil_min" in table(rows) and "wall_normal" in table(rows)


# ==============================================================================
# deliberate violations
# ==============================================================================


def test_too_little_under_the_floor_fails(brief, drawing, specs, built):
    outline, spec = drawing.planters[1], specs[1]
    result = floor_check(brief, outline, spec, 100.0, built.keep, built.slab.deck)
    assert result["wall_margin"] == -50.0 and not result["ok"]


def test_nothing_kept_under_the_floor_fails(brief, drawing, specs, built):
    nothing = types.SimpleNamespace(get_distance_numpy=lambda x, y, z: np.ones(np.broadcast_shapes(x.shape, z.shape)))
    floor = planter_floors(brief, drawing, specs, built.slab.deck)[1]
    result = floor_check(brief, drawing.planters[1], specs[1], floor, nothing, built.slab.deck)
    assert result["kept_under_floor_min"] == 0.0 and not result["ok"]


def test_soil_depth_is_read_off_a_known_deck(brief, drawing, specs, built):
    flat = types.SimpleNamespace(height_at=lambda x, y: np.full(np.shape(x), 500.0))
    result = floor_check(brief, drawing.planters[1], specs[1], 200.0, built.keep, flat)
    assert (result["soil_min"], result["soil_max"]) == (300.0, 300.0)


def test_a_floor_above_the_deck_fails(brief, drawing, built):
    """Nominal depth 100 puts the floor at z = 500, over the falling deck: there is no soil at all there."""
    solid = types.SimpleNamespace(get_distance_numpy=lambda x, y, z: -np.ones(np.broadcast_shapes(x.shape, z.shape)))
    spec = dict(brief_spec(brief), depth=100.0)
    low = types.SimpleNamespace(height_at=lambda x, y: np.full(np.shape(x), 480.0))
    result = floor_check(brief, drawing.planters[0], spec, 500.0, solid, low)
    assert result["wall_margin"] > 0 and result["kept_under_floor_min"] > brief.planter_wall    # only the soil fails
    assert result["soil_min"] == -20.0 and not result["ok"]


def test_a_floor_too_small_to_measure_inside_still_reports(brief, drawing, built):
    tiny = dict(brief_spec(brief), offset=-300.0)     # planter 3 has under 100 mm left inside this offset
    result = floor_check(brief, drawing.planters[3], tiny, 250.0, built.keep, built.slab.deck)
    assert result["soil_min"] > 0


def test_a_floor_that_vanishes_says_so(brief, drawing, built):
    with pytest.raises(ValueError, match="nothing left"):
        floor_check(brief, drawing.planters[3], dict(brief_spec(brief), offset=-2000.0), 250.0, built.keep,
                    built.slab.deck)


def test_a_top_outline_reaching_a_beam_fails(brief, drawing, built):
    light = np.zeros_like(light_plan(brief, []))
    spec = brief_spec(brief)
    gap = clearance_check(brief, built.beams, drawing.planters[3], spec, light)["gap_to_beam"]
    wide = dict(spec, rim=spec["rim"] + gap + 100.0)
    result = clearance_check(brief, built.beams, drawing.planters[3], wide, light)
    assert result["gap_to_beam"] < 0 and not result["beam_ok"] and not result["ok"]


def test_a_top_outline_over_a_light_opening_fails(brief, drawing, built):
    light = light_plan(brief, built.voids.openings)
    result = clearance_check(brief, built.beams, drawing.openings[0], brief_spec(brief), light)
    assert result["gap_to_light"] < 0 and not result["light_ok"] and not result["ok"]


@pytest.mark.parametrize("wanted, passes", [(100.0, False), (170.0, True)])
def test_a_light_opening_must_leave_room_for_the_wall(brief, drawing, built, wanted, passes):
    """Measured from the opening's real flared shape: a gap the wall does not fit in fails, though it is open."""
    light = light_plan(brief, built.voids.openings)
    points = np.array(drawing.openings[1])[:, :2]
    y = points[np.argmax(points[:, 0]), 1]
    gx = np.arange(0, brief.length + 25.0, 25.0)
    edge = gx[light[:, int(round(y / 25.0))]].max()
    spec = brief_spec(brief)
    left = edge + wanted + spec["top"]
    planter = roof.outline([(left, y - 300), (left + 300, y - 300), (left + 300, y + 300), (left, y + 300)])
    result = clearance_check(brief, built.beams, planter, spec, light)
    assert 0.0 < result["gap_to_light"] <= wanted + 30.0
    assert result["light_ok"] is passes


def beside_the_drain(drawing, gap, spec):
    x, y = drawing.drains[0][0], drawing.drains[0][1]
    left = x + gap + spec["top"]
    return roof.outline([(left, y - 300), (left + 600, y - 300), (left + 600, y + 300), (left, y + 300)])


def test_a_top_outline_near_a_drain_fails_and_the_threshold_is_a_parameter(brief, drawing):
    spec = brief_spec(brief)
    near = beside_the_drain(drawing, 300.0, spec)
    result = drain_check(brief, drawing, near, spec)
    assert result["gap_to_drain"] == pytest.approx(300.0, abs=1.0) and not result["ok"]
    assert drain_check(brief, drawing, near, spec, min_gap=250.0)["ok"]


def test_no_parameter_can_put_a_planter_inside_the_hard_limit(brief, drawing):
    spec = brief_spec(brief)
    close = beside_the_drain(drawing, 100.0, spec)
    result = drain_check(brief, drawing, close, spec, min_gap=50.0)
    assert result["hard_gap"] == brief.planter_wall + brief.outlet
    assert result["gap_to_drain"] > 50.0 and not result["ok"]


@pytest.mark.parametrize("field, value", [("stranded", 3), ("reverse_falls", 1), ("outlets_used", 9)])
def test_the_water_check_reads_each_way_of_failing(field, value):
    """On a made-up summary: this tests the reading of the numbers, not the drainage that makes them."""
    good = {"stranded": 0, "reverse_falls": 0, "outlets": 10, "outlets_used": 10, "channel_length": 1000.0}
    assert water_check(types.SimpleNamespace(summary=lambda: good))["ok"]
    bad = dict(good, **{field: value})
    assert not water_check(types.SimpleNamespace(summary=lambda: bad))["ok"]
