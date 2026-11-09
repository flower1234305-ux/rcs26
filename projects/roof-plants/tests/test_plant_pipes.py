"""Under-slab pipes from the planter bores to the drains: a record, never cut into the roof."""

import json
import os

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.plant_drains import plant_steps_drained, planter_drains
from roof_plants.plant_pipes import SLOPE, pipe_mesh, pipe_overlaps, pipe_rows, pipe_table, planter_pipes, route
from roof_plants.plants import assign, load_plants, opening_spec

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def case():
    pytest.importorskip("skfmm", reason="needs the processes extra")
    brief = roof.Brief(voxel=60.0)
    drawing = roof.Drawing.load(os.path.join(HERE, "drawing.json"))
    with open(os.path.join(HERE, "planter_plants_fallback.json"), encoding="utf-8") as f:
        chosen = json.load(f)
    specs = [opening_spec(p) for p in assign(load_plants(os.path.join(HERE, "plants.json")), chosen, 4)]
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    return brief, drawing, specs, built


def test_every_bore_is_piped_to_its_nearest_drain(case):
    brief, drawing, specs, built = case
    pipes = planter_pipes(brief, drawing, specs, built)
    bores = [b for planter in planter_drains(brief, drawing, specs, built.slab.deck) for b in planter]
    assert len(pipes) == len(bores) == 4
    drains = np.array([[p[0], p[1]] for p in drawing.drains])
    for pipe, bore in zip(pipes, bores):
        nearest = int(np.argmin(np.hypot(drains[:, 0] - bore.x, drains[:, 1] - bore.y)))
        assert pipe.drain == nearest
        assert pipe.start == (bore.x, bore.y, 0.0)
        assert pipe.end[:2] == pytest.approx(tuple(drains[nearest]))
        assert pipe.clear, pipe_table(pipes)


def test_the_pipe_falls_at_its_slope_all_the_way(case):
    brief, drawing, specs, built = case
    for slope in (SLOPE, 0.02):
        for pipe in planter_pipes(brief, drawing, specs, built, slope=slope):
            z = np.array(pipe.points)[1:, 2]
            assert (np.diff(z) < 0).all()
            assert pipe.drop == pytest.approx(slope * pipe.length)
            assert -pipe.end[2] + pipe.radius == pytest.approx(pipe.depth_below_soffit)
            assert pipe.depth_below_soffit == pytest.approx(pipe.drop + 2 * pipe.radius)
    assert SLOPE == 0.01


def test_the_roof_is_not_touched(case):
    brief, drawing, specs, built = case
    x = np.random.default_rng(1).uniform(0, brief.length, 5000)
    y = np.random.default_rng(2).uniform(0, brief.width, 5000)
    z = np.random.default_rng(3).uniform(-300, brief.thickness, 5000)
    before = built.design.roof.get_distance_numpy(x, y, z)
    planter_pipes(brief, drawing, specs, built)
    assert np.array_equal(before, built.design.roof.get_distance_numpy(x, y, z))


def test_rows_table_and_mesh(case):
    brief, drawing, specs, built = case
    pipes = planter_pipes(brief, drawing, specs, built)
    rows = pipe_rows(pipes)
    assert {"length_mm", "slope", "drop_mm", "depth_below_soffit_mm", "clear"} <= set(rows[0])
    assert "safe" not in pipe_table(pipes).lower()
    vertices, faces = pipe_mesh(pipes[0], sides=8)
    assert faces.shape == ((len(pipes[0].points) - 1) * 16, 3) and faces.max() < len(vertices)


# ==============================================================================
# routing around what is in the way
# ==============================================================================


def test_a_bore_in_the_way_turns_the_route_the_other_way():
    blocker = [("bore of P9", (3000.0, 0.0, 80.0))]          # on the x-then-y corner's first leg
    kind, corners, length, crossings = route((0.0, 0.0), (5000.0, 4000.0), 80.0, blocker)
    assert kind == "y-then-x" and not crossings and length == pytest.approx(9000.0)


def test_both_turns_blocked_goes_straight_and_all_blocked_says_why():
    blockers = [("drain 7", (3000.0, 0.0, 80.0)), ("drain 8", (0.0, 3000.0, 80.0))]
    kind, _, length, crossings = route((0.0, 0.0), (5000.0, 4000.0), 80.0, blockers)
    assert kind == "straight" and not crossings and length == pytest.approx(np.hypot(5000, 4000))
    blockers.append(("bore of P2", (2500.0, 2000.0, 80.0)))
    kind, _, _, crossings = route((0.0, 0.0), (5000.0, 4000.0), 80.0, blockers)
    assert kind == "straight" and crossings == ["bore of P2"]


def test_a_light_opening_counts_as_a_crossing():
    step = 25.0
    gx, gy = np.arange(0, 6000 + step, step), np.arange(0, 5000 + step, step)
    light = np.zeros((gx.size, gy.size), dtype=bool)
    light[(gx > 2000) & (gx < 2600)] = True                    # a strip across the whole width
    kind, _, _, crossings = route((0.0, 1000.0), (5000.0, 4000.0), 80.0, [], light, (gx, gy, step))
    assert crossings == ["light opening"]
    kind, _, _, crossings = route((0.0, 1000.0), (1800.0, 4000.0), 80.0, [], light, (gx, gy, step))
    assert not crossings


def test_two_pipes_to_one_drain_are_reported_where_they_meet(case):
    """P1 and P3 both go to drain 4: the overlap is reported as numbers, not judged."""
    brief, drawing, specs, built = case
    pipes = planter_pipes(brief, drawing, specs, built)
    found = pipe_overlaps(pipes)
    pairs = {f["planters"]: f for f in found}
    assert (1, 3) in pairs and pairs[(1, 3)]["same_drain"]
    assert pairs[(1, 3)]["overlap_length_mm"] > 0
    assert all("ok" not in f and "safe" not in str(f).lower() for f in found)


def test_parallel_pipes_apart_do_not_overlap():
    from roof_plants.plant_pipes import Pipe

    a = Pipe(0, (0, 0), 0, "straight", 80.0, 0.01, [(0, 0, 0), (0, 0, -80), (3000, 0, -110)], 3000.0, [])
    b = Pipe(1, (0, 500), 1, "straight", 80.0, 0.01, [(0, 500, 0), (0, 500, -80), (3000, 500, -110)], 3000.0, [])
    assert pipe_overlaps([a, b]) == []
    c = Pipe(2, (0, 100), 1, "straight", 80.0, 0.01, [(0, 100, 0), (0, 100, -80), (3000, 100, -110)], 3000.0, [])
    (hit,) = pipe_overlaps([a, c])
    assert hit["closest_plan_mm"] == pytest.approx(100.0) and hit["overlap_length_mm"] == pytest.approx(3025.0)
