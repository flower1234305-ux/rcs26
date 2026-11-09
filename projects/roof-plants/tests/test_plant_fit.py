"""group3_upright at depth 400 (2026-11-09, Wei): where it fits on this roof, and the stand-in planting.

Pins down the numbers in docs/roof-plants.md (v2, item 5), so a change that alters them is noticed.
"""

import json
import os

import pytest

import roof_plants as roof
from roof_plants.plant_checks import water_check
from roof_plants.plant_drains import all_ok_drained, drain_rows, drained_planter_rows, plant_steps_drained
from roof_plants.plant_voids import deck_min, plant_steps
from roof_plants.plants import PlanterFitError, assign, load_plants, opening_spec, reassign

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def brief():
    return roof.Brief(voxel=60.0)


@pytest.fixture(scope="module")
def drawing():
    return roof.Drawing.load(os.path.join(HERE, "drawing.json"))


@pytest.fixture(scope="module")
def plants():
    return load_plants(os.path.join(HERE, "plants.json"))


def chosen(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def test_the_plant_data_says_400_and_where_it_comes_from(plants):
    record = plants["group3_upright"]
    assert record["depth"] == 400
    assert "建築基地綠化設計技術規範" in record["source"] and "Wei 核准" in record["source"]


def test_the_intended_planting_stops_at_p1(brief, drawing, plants):
    specs = [opening_spec(p) for p in assign(plants, chosen("planter_plants.json"), 4)]
    assert specs[1]["id"] == "group3_upright"
    with pytest.raises(PlanterFitError, match=r"planter 1 \(group3_upright\): floor at z = 116.3 .*at most 366 mm"):
        roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))


def test_it_fits_no_planter_where_it_is_drawn(brief, drawing, plants):
    """The deepest depth each planter takes for it, with the others as in the stand-in: 306, 366, 332, 391."""
    base = chosen("planter_plants_fallback.json")
    deepest = []
    for n in range(4):
        specs = [opening_spec(p) for p in assign(plants, reassign(base, n, "group3_upright"), 4)]
        beams = roof.beams(brief)
        slab = roof.slab(brief, plant_steps(brief, specs)["water"](brief, drawing, beams))
        low = deck_min(slab.deck, drawing.planters[n], specs[n]["top"], brief.plan_cell / 2)
        deepest.append(int(low - brief.planter_wall))
    assert deepest == [306, 366, 332, 391]
    assert max(deepest) < 400


def test_the_stand_in_planting_runs_and_says_it_is_one(brief, drawing, plants):
    fallback = chosen("planter_plants_fallback.json")
    assert "STAND-IN" in fallback["note"]
    assert [r["plant"] for r in fallback["planters"]] == ["control", "control", "group1_creeping", "control"]
    specs = [opening_spec(p) for p in assign(plants, fallback, 4)]
    built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
    assert all_ok_drained(drained_planter_rows(brief, drawing, specs, built), water_check(built.incision),
                          drain_rows(brief, drawing, specs, built))


def test_the_build_knows_a_stand_in_from_the_design():
    from roof_plants.plant_build import stand_in

    assert stand_in(chosen("planter_plants_fallback.json"))
    assert not stand_in(chosen("planter_plants.json"))
