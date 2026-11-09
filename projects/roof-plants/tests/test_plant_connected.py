"""The connected-planter demonstration (drawing_connected.json, neck 800 mm), run on the unchanged program.

These tests pin down what the demonstration found, so a change that alters it is noticed:

* neck 800 mm, the dumbbell growing group3_upright at its v1 depth (360 mm): every check passes;
* the same at depth 400 (plants.json since 2026-11-09): it does not fit, as P1 alone does not;
* neck 500 mm (made here with the script, not committed): Step 4 stops, the floor splits in two.
"""

import importlib.util
import json
import os

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.plant_checks import water_check
from roof_plants.plant_drains import all_ok_drained, drain_rows, drained_planter_rows, plant_steps_drained
from roof_plants.plants import PlanterFitError, assign, load_plants, opening_spec, reassign

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def script():
    spec = importlib.util.spec_from_file_location("make_connected_drawing",
                                                  os.path.join(HERE, "scripts", "make_connected_drawing.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def brief():
    return roof.Brief(voxel=60.0)


@pytest.fixture(scope="module")
def drawing():
    return roof.Drawing.load(os.path.join(HERE, "drawing_connected.json"))


@pytest.fixture(scope="module")
def original():
    return roof.Drawing.load(os.path.join(HERE, "drawing.json"))


@pytest.fixture(scope="module")
def chosen():
    with open(os.path.join(HERE, "planter_plants_connected.json"), encoding="utf-8") as f:
        return json.load(f)


def specs_for(chosen, count, depth=None):
    plants = load_plants(os.path.join(HERE, "plants.json"))
    if depth is not None:
        plants = dict(plants, group3_upright=dict(plants["group3_upright"], depth=depth))
    return [opening_spec(p) for p in assign(plants, chosen, count)]


def test_only_the_two_planters_changed_and_the_neck_is_800(drawing, original):
    assert len(drawing.planters) == 3
    assert [list(p) for p in drawing.openings] == [list(p) for p in original.openings]
    assert [list(p) for p in drawing.drains] == [list(p) for p in original.drains]
    assert list(drawing.planters[0]) == list(original.planters[0])
    assert list(drawing.planters[2]) == list(original.planters[2])
    joined = np.array(drawing.planters[1])[:, :2]
    for n in (1, 3):     # the dumbbell covers both centres
        centre = np.array(original.planters[n])[:-1, :2].mean(axis=0)
        assert joined[:, 0].min() < centre[0] < joined[:, 0].max()
    again = script().dumbbell(original.planters[1], original.planters[3], neck=800.0)
    assert np.allclose(np.array(again), np.array(drawing.planters[1]))


def test_at_800_the_upright_plant_passes_every_check(brief, drawing, chosen):
    specs = specs_for(chosen, 3, depth=360)
    assert specs[1]["id"] == "group3_upright"
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    rows = drained_planter_rows(brief, drawing, specs, built)
    drains = drain_rows(brief, drawing, specs, built)
    assert all_ok_drained(rows, water_check(built.incision), drains)


def test_at_depth_400_it_does_not_fit_as_p1_does_not(brief, drawing, chosen):
    with pytest.raises(PlanterFitError, match=r"planter 1 \(group3_upright\).*depth 400.0 must be at most 366 mm"):
        roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs_for(chosen, 3)))


def test_as_a_control_planter_it_passes_every_check(brief, drawing, chosen):
    specs = specs_for(reassign(chosen, 1, "control"), 3)
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    assert all_ok_drained(drained_planter_rows(brief, drawing, specs, built), water_check(built.incision),
                          drain_rows(brief, drawing, specs, built))


def test_regression_a_500_neck_stops_in_step_4(brief, original, chosen):
    """offset -300 splits a 500 mm neck: Step 4's floor outline is two loops, and offset_outline wants one."""
    joined = script().dumbbell(original.planters[1], original.planters[3], neck=500.0)
    narrow = roof.Drawing(original.openings, [original.planters[0], joined, original.planters[2]], original.drains)
    with pytest.raises(ValueError, match="gives 2 loops, expected 1"):
        roof.design_roof(brief, narrow, steps=plant_steps_drained(brief, specs_for(chosen, 3, depth=360)))
