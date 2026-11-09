"""Every planter drains: a bore from its floor out through the soffit, open in the design and in what is kept."""

import json
import os

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.plant_checks import planter_rows, water_check
from roof_plants.plant_drains import (
    all_ok_drained,
    bore_check,
    drain_points,
    drain_rows,
    drain_table,
    drained_planter_rows,
    gap_to_beams,
    plant_steps_drained,
    planter_drains,
)
from roof_plants.plant_voids import plant_steps
from roof_plants.plants import assign, opening_spec, reassign

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
def drained(brief, drawing, specs):
    return roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))


@pytest.fixture(scope="module")
def blind(brief, drawing, specs):
    return roof.design_roof(brief, drawing, steps=plant_steps(brief, specs))


# ==============================================================================
# the real roof
# ==============================================================================


def test_every_planter_drains(brief, drawing, specs, drained):
    rows = drain_rows(brief, drawing, specs, drained)
    assert [r["ok"] for r in rows] == [True] * 4, drain_table(rows)
    assert all(r["flat"] for r in rows)
    assert all(r["bores"] == 1 and r["open_fraction_min"] == 1.0 for r in rows)
    assert all(r["radius"] == brief.outlet for r in rows)


def test_the_blind_pockets_of_v1_fail_the_drain_check(brief, drawing, specs, blind):
    """The deliberate violation: without the bores the same check finds them shut."""
    rows = drain_rows(brief, drawing, specs, blind)
    assert not any(r["ok"] for r in rows)
    assert all(r["open_fraction_min"] < 0.2 for r in rows)


def test_the_rest_of_the_checks_still_pass(brief, drawing, specs, drained):
    rows = drained_planter_rows(brief, drawing, specs, drained)
    water = water_check(drained.incision)
    drains = drain_rows(brief, drawing, specs, drained)
    assert all(r["ok"] for r in rows) and all_ok_drained(rows, water, drains)
    assert not all_ok_drained(rows, water, [dict(drains[0], ok=False)])


def test_the_floor_check_sees_the_bore_without_the_patch(brief, drawing, specs, drained):
    """Why drained_planter_rows fills the bores into keep: the plain check reads a bore as a missing wall."""
    rows = planter_rows(brief, drawing, specs, drained)
    assert all(r["kept_under_floor_min"] < brief.planter_wall / 2 for r in rows)


def test_the_bores_do_not_change_the_deck(drained, blind):
    assert np.array_equal(drained.incision.surface, blind.incision.surface)


def test_a_sleeve_of_kept_wall_wraps_each_bore(brief, drawing, specs, drained):
    """The shell of the pocket wraps the bore, so the foam cannot take water in sideways."""
    angles = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    for bores in planter_drains(brief, drawing, specs, drained.slab.deck):
        for b in bores:
            reach = b.radius + brief.planter_wall / 2
            zs = np.arange(20.0, b.top - 40.0, 20.0)
            x = (b.x + reach * np.cos(angles))[:, None] + 0 * zs
            y = (b.y + reach * np.sin(angles))[:, None] + 0 * zs
            assert (drained.keep.get_distance_numpy(x, y, zs[None, :] + 0 * x) < 0).all()


def test_the_bores_keep_off_the_beams_and_the_beams_keep_their_depth(brief, drawing, specs, drained):
    for bores in planter_drains(brief, drawing, specs, drained.slab.deck):
        for b in bores:
            assert bore_check(brief, b, drained)["gap_to_beam"] > 0
    zs = np.arange(10.0, 500.0, 20.0)[None, None, :]
    ys = np.arange(50.0, brief.width, 100.0)
    for lo, hi in drained.beams.xbands:
        x = np.full((1, 1, 1), (lo + hi) / 2)
        assert (drained.keep.get_distance_numpy(x, ys[None, :, None], zs) < 0).all()
    xs = np.arange(50.0, brief.length, 100.0)
    for lo, hi in drained.beams.ybands:
        y = np.full((1, 1, 1), (lo + hi) / 2)
        assert (drained.keep.get_distance_numpy(xs[:, None, None], y, zs) < 0).all()


# ==============================================================================
# where a bore goes
# ==============================================================================


def square(x0, y0, x1, y1):
    return roof.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def spec(offset=0.0):
    return {"id": "t", "offset": offset, "rim": 0.0, "depth": 300.0, "depth_datum": "nominal", "top": offset}


def test_a_bore_goes_where_the_floor_is_widest(brief):
    (x, y, inset), = drain_points(brief, square(2000, 2000, 4000, 3000), spec())
    assert (x, y, inset) == (pytest.approx(3000, abs=25), pytest.approx(2500, abs=25), pytest.approx(500, abs=25))


def test_a_bore_moves_off_a_beam(brief):
    """A planter centred on the beam at x = 6000: the bore lands beside the beam, not in it."""
    (x, y, _), = drain_points(brief, square(5000, 2000, 7000, 3000), spec())
    assert abs(x - 6000) >= brief.beam / 2 + brief.outlet


def test_a_bore_placed_at_the_beam_limit_passes_its_own_check(brief):
    """Placing and checking use one rule. With radius 100 the grid has a point at x = 6400, exactly 100 mm
    off the beam at 5700-6300: a gap of 0, which the check fails, so placing must skip it too."""
    floor = square(6300, 2000, 6450, 2400)
    (x, y, _), = drain_points(brief, floor, spec(), radius=100.0)
    assert x == 6425.0
    assert gap_to_beams(brief, np.array(6400.0), np.array(y), 100.0) == 0.0
    assert gap_to_beams(brief, np.array(x), np.array(y), 100.0) > 0


def test_a_floor_in_two_pieces_gets_two_bores(brief):
    """Two squares joined by a 200 mm neck, floor shrunk by 150: the neck closes and each square drains alone."""
    dumbbell = roof.outline([(2000, 2000), (3000, 2000), (3000, 2400), (3500, 2400), (3500, 2000), (4500, 2000),
                             (4500, 3000), (3500, 3000), (3500, 2600), (3000, 2600), (3000, 3000), (2000, 3000)])
    assert len(drain_points(brief, dumbbell, spec())) == 1
    assert len(drain_points(brief, dumbbell, spec(-150.0))) == 2


def test_a_floor_all_on_a_beam_says_so(brief):
    on_beam = square(5800, 2000, 6200, 2400)
    with pytest.raises(ValueError, match="clear of the beams"):
        drain_points(brief, on_beam, spec())


def test_a_floor_that_is_all_blend_still_drains(brief, drawing, v1_plants):
    """P3 growing group3_upright: the floor is 97 mm deep at most, so the bore takes out the whole dimple."""
    with open(os.path.join(HERE, "planter_plants.json"), encoding="utf-8") as f:
        chosen = reassign(json.load(f), 3, "group3_upright")
    swapped = [opening_spec(p) for p in assign(v1_plants, chosen, 4)]
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, swapped))
    rows = drain_rows(brief, drawing, swapped, built)
    assert all(r["ok"] for r in rows), drain_table(rows)
    assert not rows[3]["flat"] and rows[1]["flat"]
    assert all(r["ok"] for r in drained_planter_rows(brief, drawing, swapped, built))
