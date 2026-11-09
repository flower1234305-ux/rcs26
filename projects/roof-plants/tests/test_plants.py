"""The plant data and its pure functions: no geometry, so these run in a moment."""

import ast
import json
import os

import pytest

import roof_plants as roof
from roof_plants.plants import (
    REQUIRED,
    PlanterFitError,
    assign,
    brief_spec,
    check_control,
    check_fit,
    floor_height,
    load_plants,
    opening_spec,
    reassign,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTS = os.path.join(HERE, "plants.json")
ASSIGN = os.path.join(HERE, "planter_plants.json")


def plant(**changes):
    record = {"id": "p", "name_zh": "測試", "root_type": "鬚根", "growth": "直立",
              "offset": -300, "rim": 80, "depth": 360, "depth_datum": "local_min", "source": "test"}
    record.update(changes)
    return record


def test_the_pure_module_imports_only_the_standard_library():
    with open(os.path.join(HERE, "roof_plants", "plants.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported == {"json"}


def test_normal():
    spec = opening_spec(plant())
    assert (spec["offset"], spec["rim"], spec["depth"], spec["top"]) == (-300.0, 80.0, 360.0, -220.0)


def test_every_plant_in_the_file_is_valid_and_marked_an_assumption():
    plants = load_plants(PLANTS)
    assert set(plants) == {"control", "group1_creeping", "group3_upright"}
    assert opening_spec(plants["control"])["top"] == 220.0
    assert opening_spec(plants["group1_creeping"])["top"] == 700.0
    for record in plants.values():
        assert record["source"].startswith("假設值")
    assert plants["control"]["depth_datum"] == "nominal"
    assert plants["group1_creeping"]["depth_datum"] == plants["group3_upright"]["depth_datum"] == "local_min"


@pytest.mark.parametrize("field", REQUIRED)
def test_missing_field_is_named(field):
    record = plant()
    del record[field]
    with pytest.raises(KeyError, match=field):
        opening_spec(record)


@pytest.mark.parametrize("changes, word", [
    ({"depth": 0}, "depth"), ({"depth": -10}, "depth"), ({"rim": -1}, "rim"),
    ({"offset": "300"}, "offset"), ({"depth": float("nan")}, "depth"), ({"rim": True}, "rim"),
    ({"depth_datum": "sea level"}, "depth_datum"),
])
def test_unreasonable_values(changes, word):
    with pytest.raises(ValueError, match=word):
        opening_spec(plant(**changes))


def test_not_a_dict():
    with pytest.raises(TypeError):
        opening_spec([1, 2, 3])


def test_every_assigned_id_exists():
    plants = load_plants(PLANTS)
    with open(ASSIGN, encoding="utf-8") as f:
        planter_plants = json.load(f)
    for row in planter_plants["planters"]:
        assert row["plant"] in plants, row
    assert len(assign(plants, planter_plants, 4)) == 4


def test_assign_rejects_unknown_ids_and_gaps():
    plants = load_plants(PLANTS)
    with pytest.raises(KeyError, match="nope"):
        assign(plants, {"planters": [{"index": 0, "plant": "nope"}]}, 1)
    with pytest.raises(ValueError):
        assign(plants, {"planters": [{"index": 0, "plant": "control"}]}, 2)


def test_control_is_the_brief_default():
    brief = roof.Brief()
    control = opening_spec(load_plants(PLANTS)["control"])
    assert {k: control[k] for k in ("offset", "rim", "depth", "top", "depth_datum")} == \
        {k: brief_spec(brief)[k] for k in ("offset", "rim", "depth", "top", "depth_datum")}
    check_control([control], brief)


def test_control_measured_from_the_real_deck_is_refused_though_its_numbers_match():
    control = opening_spec(load_plants(PLANTS)["control"])
    with pytest.raises(ValueError, match="planter 0 is control.*depth_datum local_min.*depth_datum nominal"):
        check_control([dict(control, depth_datum="local_min")], roof.Brief())


def test_control_under_another_brief_is_refused_and_says_what_differs():
    control = opening_spec(load_plants(PLANTS)["control"])
    brief = roof.Brief(planter_depth=300.0)
    with pytest.raises(ValueError, match="planter 0 is control.*depth 350.0.*depth 300.0"):
        check_control([control], brief)
    check_control([brief_spec(brief)], brief)                     # the brief's own numbers are fine
    check_control([dict(control, id="another plant")], brief)     # and only control is held to them


def test_a_missing_datum_says_which_field():
    record = plant()
    del record["depth_datum"]
    with pytest.raises(KeyError, match="depth_datum"):
        opening_spec(record)


def test_floor_height_by_datum():
    assert floor_height({"depth": 350.0, "depth_datum": "nominal"}, 600.0, 400.0) == 250.0
    assert floor_height({"depth": 200.0, "depth_datum": "local_min"}, 600.0, 500.0) == 300.0
    with pytest.raises(ValueError, match="needs the deck"):
        floor_height({"depth": 200.0, "depth_datum": "local_min"}, 600.0)


def test_check_fit_names_every_planter_that_does_not_fit():
    specs = [{"id": "a", "depth": 400.0}, {"id": "b", "depth": 200.0}, {"id": "c", "depth": 500.0}]
    check_fit(specs[1:2], [150.0], 150.0)       # exactly the wall is enough
    with pytest.raises(PlanterFitError) as error:
        check_fit(specs, [116.3, 300.0, 20.0], 150.0)
    message = str(error.value)
    assert "planter 0 (a)" in message and "at most 366 mm" in message
    assert "planter 2 (c)" in message and "planter 1" not in message


def test_reassign_changes_one_planter_and_leaves_the_original():
    chosen = {"note": "n", "planters": [{"index": 0, "plant": "a"}, {"index": 1, "plant": "b"}]}
    swapped = reassign(chosen, 1, "c")
    assert [row["plant"] for row in swapped["planters"]] == ["a", "c"]
    assert [row["plant"] for row in chosen["planters"]] == ["a", "b"]


def test_reassign_refuses_a_planter_that_is_not_there():
    with pytest.raises(ValueError, match="no planter 9"):
        reassign({"planters": [{"index": 0, "plant": "a"}]}, 9, "b")
