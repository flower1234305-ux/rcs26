"""The planted pockets, read off the fields: no meshing, no build."""

import dataclasses
import os
import sys
import types

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.heightfield import VolHeightField
from roof_plants.plant_voids import deck_min, offset_outline, plant_steps, planter_floors, pocket, water_drawing
from roof_plants.plants import PlanterFitError, brief_spec

pytest.importorskip("skfmm", reason="needs the processes extra")

BRIEF = roof.Brief()          # planter_depth 350, planter_rim 220: the original values
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWING = roof.Drawing.load(os.path.join(HERE, "drawing.json"))


def spec(offset, rim, depth, plant="t"):
    return {"id": plant, "offset": float(offset), "rim": float(rim), "depth": float(depth),
            "top": float(offset + rim), "depth_datum": "nominal"}


def random_points(brief, outline, count, seed):
    rng = np.random.default_rng(seed)
    a = np.array(outline)[:, :2]
    return (rng.uniform(a[:, 0].min() - 600, a[:, 0].max() + 600, count),
            rng.uniform(a[:, 1].min() - 600, a[:, 1].max() + 600, count),
            rng.uniform(-50, brief.thickness + 50, count))


def test_brief_values_give_the_original_pockets():
    slab = types.SimpleNamespace(flat=roof.box(0, 0, 0, BRIEF.length, BRIEF.width, BRIEF.thickness))
    for n, (outline, theirs) in enumerate(zip(DRAWING.planters, roof.voids(BRIEF, DRAWING, slab).pockets)):
        x, y, z = random_points(BRIEF, outline, 20000, n)
        mine = pocket(BRIEF, outline, spec(0, 220, 350)).get_distance_numpy(x, y, z)
        assert np.abs(mine - theirs.get_distance_numpy(x, y, z)).max() == 0.0


@pytest.mark.parametrize("offset, rim, depth, ring, inside", [
    (300, 400, 200, 100, True),     # grown: 100 mm outside the drawn floor outline is cut away
    (-300, 80, 360, -100, False),   # shrunk: 100 mm inside the drawn floor outline is kept
])
def test_offset_moves_the_floor_outline(offset, rim, depth, ring, inside):
    floor = BRIEF.thickness - depth
    z = floor + 40.0                # just above the floor; growth there is offset (+ under 4 % of rim)
    for outline in DRAWING.planters:
        points = np.array(offset_outline(outline, ring))[:, :2]
        d = pocket(BRIEF, outline, spec(offset, rim, depth)).get_distance_numpy(points[:, 0], points[:, 1],
                                                                                np.full(len(points), z))
        if inside:
            assert (d < 0).all(), d.max()
        else:
            assert (d > 0).all(), d.min()


def test_control_planters_through_the_steps_are_the_original_roof():
    brief = roof.Brief(voxel=60.0)
    specs = [brief_spec(brief)] * len(DRAWING.planters)
    original = roof.design_roof(brief, DRAWING)
    planted = roof.design_roof(brief, DRAWING, steps=plant_steps(brief, specs))
    assert np.array_equal(planted.incision.surface, original.incision.surface)
    rng = np.random.default_rng(3)
    x = rng.uniform(-200, brief.length + 200, 100000)
    y = rng.uniform(-200, brief.width + 200, 100000)
    z = rng.uniform(-100, brief.thickness + 100, 100000)
    assert np.abs(planted.design.roof.get_distance_numpy(x, y, z)
                  - original.design.roof.get_distance_numpy(x, y, z)).max() == 0.0


def test_a_control_under_another_brief_stops_at_once():
    brief = roof.Brief(planter_depth=300.0)
    with pytest.raises(ValueError, match="planter 0 is control"):
        plant_steps(brief, [spec(0, 220, 350, "control")])


def test_the_control_of_another_brief_is_that_brief_s_pocket():
    brief = roof.Brief(planter_depth=300.0, planter_rim=180.0)
    slab = types.SimpleNamespace(flat=roof.box(0, 0, 0, brief.length, brief.width, brief.thickness))
    specs = [brief_spec(brief)] * len(DRAWING.planters)
    planted = plant_steps(brief, specs)["voids"](brief, DRAWING, slab).pockets
    for n, (outline, theirs) in enumerate(zip(DRAWING.planters, roof.voids(brief, DRAWING, slab).pockets)):
        x, y, z = random_points(brief, outline, 20000, n)
        assert np.abs(planted[n].get_distance_numpy(x, y, z) - theirs.get_distance_numpy(x, y, z)).max() == 0.0


def test_step_7_keeps_the_openings_and_outlets_of_its_base():
    slab = types.SimpleNamespace(flat=roof.box(0, 0, 0, BRIEF.length, BRIEF.width, BRIEF.thickness))
    specs = [spec(0, 220, 350)] * len(DRAWING.planters)
    marker = roof.voids(BRIEF, DRAWING, slab)
    step = plant_steps(BRIEF, specs, base_voids=lambda *_: marker)["voids"]
    result = step(BRIEF, DRAWING, slab)
    assert result.openings is marker.openings and result.outlets is marker.outlets
    assert result.pockets is not marker.pockets


def test_a_base_step_with_a_pocket_too_many_is_refused():
    slab = types.SimpleNamespace(flat=roof.box(0, 0, 0, BRIEF.length, BRIEF.width, BRIEF.thickness))
    specs = [spec(0, 220, 350)] * len(DRAWING.planters)
    made = roof.voids(BRIEF, DRAWING, slab)
    extra = dataclasses.replace(made, pockets=made.pockets + made.pockets[:1])
    step = plant_steps(BRIEF, specs, base_voids=lambda *_: extra)["voids"]
    with pytest.raises(ValueError, match="made 5 pockets for 4 planters"):
        step(BRIEF, DRAWING, slab)


def test_the_water_step_passes_the_floor_outlines_to_its_base():
    specs = [spec(300, 400, 200)] * len(DRAWING.planters)
    seen = []
    step = plant_steps(BRIEF, specs, base_water=lambda b, d, beams: seen.append(d))["water"]
    step(BRIEF, DRAWING, None)
    assert np.ptp(np.array(seen[0].planters[0])[:, 0]) > np.ptp(np.array(DRAWING.planters[0])[:, 0])


def test_water_drawing_wants_one_spec_per_planter():
    with pytest.raises(ValueError, match="1 specs for 4 planters"):
        water_drawing(DRAWING, [spec(0, 220, 350)])


def test_water_sees_the_floor_outline_and_keeps_the_rest_of_the_drawing():
    specs = [spec(300, 400, 200)] * len(DRAWING.planters)
    seen = water_drawing(DRAWING, specs)
    assert seen.openings is DRAWING.openings and seen.drains is DRAWING.drains
    centre = np.array(DRAWING.planters[0])[:, :2]
    assert np.ptp(np.array(seen.planters[0])[:, 0]) == pytest.approx(np.ptp(centre[:, 0]) + 600, abs=20)


# ==============================================================================
# depth measured from the real deck
# ==============================================================================


def test_deck_min_finds_the_low_point_of_a_known_ramp():
    square = roof.outline([(2000, 2000), (4000, 2000), (4000, 4000), (2000, 4000)])
    ramp = types.SimpleNamespace(height_at=lambda x, y: 500.0 + 0.01 * (x - 2000.0))
    assert deck_min(ramp, square, 0.0, 25.0) == pytest.approx(500.0, abs=0.5)
    assert deck_min(ramp, square, 100.0, 25.0) == pytest.approx(499.0, abs=0.5)
    assert deck_min(ramp, square, -100.0, 25.0) == pytest.approx(501.0, abs=0.5)
    with pytest.raises(ValueError, match="nothing left"):
        deck_min(ramp, square, -2000.0, 25.0)


def test_one_low_grid_point_sets_the_floor_whatever_the_plan_cell():
    """3030 is on a 30 mm grid but on no multiple of 25, the step a fixed sampling would use."""
    square = roof.outline([(2000, 2000), (4000, 2000), (4000, 4000), (2000, 4000)])
    heights = np.full((401, 401), 500.0)
    heights[101, 101] = 400.0
    deck = VolHeightField(heights, (0, 0), (30, 30))
    local = dict(spec(0, 100, 200), depth_datum="local_min")
    drawing = roof.Drawing([], [square], [])
    assert planter_floors(roof.Brief(plan_cell=30.0), drawing, [local], deck) == [200.0]


def test_a_local_min_floor_sits_depth_below_the_lowest_deck():
    square = roof.outline([(2000, 2000), (4000, 2000), (4000, 4000), (2000, 4000)])
    ramp = types.SimpleNamespace(height_at=lambda x, y: 500.0 + 0.01 * (x - 2000.0))
    drawing = roof.Drawing([], [square], [])
    local = dict(spec(0, 100, 200), depth_datum="local_min")
    floor = planter_floors(BRIEF, drawing, [local], ramp)[0]
    assert floor == pytest.approx(299.0, abs=0.5)        # lowest deck 499 inside +100, less 200
    field = pocket(BRIEF, square, local, floor)
    # far from the walls the pocket's zero level is the flat floor: a known distance at a known point
    assert field.get_distance_numpy(np.array([3000.0]), np.array([3000.0]), np.array([floor]))[0] == \
        pytest.approx(0.0, abs=0.5)
    assert field.get_distance_numpy(np.array([3000.0]), np.array([3000.0]), np.array([floor - 50.0]))[0] == \
        pytest.approx(50.0, abs=0.5)


def test_nominal_stays_below_the_slab_top_whatever_the_deck_does():
    ramp = types.SimpleNamespace(height_at=lambda x, y: 0.0 * x + 400.0)
    assert planter_floors(BRIEF, DRAWING, [spec(0, 220, 350)] * 4, ramp) == [250.0] * 4


def test_a_planter_that_cannot_fit_stops_before_any_heavy_step(monkeypatch):
    """Measured from a deck that lies below the slab's top, thickness - planter_wall can never fit."""
    deepest = BRIEF.thickness - BRIEF.planter_wall
    specs = [spec(0, 220, 350) for _ in DRAWING.planters]
    specs[1] = dict(spec(-300, 80, deepest, "group3_upright"), depth_datum="local_min")

    def too_far(*args):
        raise AssertionError("reached Step 8")

    # by name, because roof.design is also the function called design
    monkeypatch.setattr(sys.modules["roof_plants.design"], "keep", too_far)
    with pytest.raises(PlanterFitError, match=r"planter 1 \(group3_upright\).*must be at most \d+ mm"):
        roof.design_roof(BRIEF, DRAWING, steps=plant_steps(BRIEF, specs))


def test_a_planter_deeper_than_the_slab_stops_at_once():
    specs = [spec(0, 220, 350) for _ in DRAWING.planters]
    specs[0] = spec(0, 220, 500)
    with pytest.raises(PlanterFitError, match="planter 0"):
        plant_steps(BRIEF, specs)
