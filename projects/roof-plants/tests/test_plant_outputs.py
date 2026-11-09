"""The drawings and the build: they run on the planted roof and a piece comes out watertight."""

import os

import pytest

import roof_plants as roof
from roof_plants.plant_build import build_pieces, passed
from roof_plants.plant_figures import plan_comparison, section_comparison
from roof_plants.plant_voids import plant_steps
from roof_plants.plants import brief_spec

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def setup():
    brief = roof.Brief(voxel=60.0)
    drawing = roof.Drawing.load(os.path.join(HERE, "drawing.json"))
    specs = [brief_spec(brief)] * len(drawing.planters)
    specs[1] = {"id": "group3_upright", "offset": -300.0, "rim": 80.0, "depth": 300.0, "depth_datum": "local_min",
                "top": -220.0}
    planted = roof.design_roof(brief, drawing, steps=plant_steps(brief, specs))
    return brief, drawing, specs, planted, roof.design_roof(brief, drawing)


def test_the_drawings_are_written(setup, tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    brief, drawing, specs, planted, original = setup
    plan = tmp_path / "plan.png"
    section = tmp_path / "section.png"
    plan_comparison(brief, drawing, original, planted, specs, plan)
    plan_comparison(brief, drawing, planted, planted, specs, before=specs)
    section_comparison(brief, drawing, original, planted, specs, path=section)
    plt.close("all")
    assert plan.stat().st_size > 10000 and section.stat().st_size > 10000


def test_a_piece_builds_watertight_and_is_written(setup, tmp_path):
    brief, _, _, planted, _ = setup
    result = build_pieces(brief, planted, str(tmp_path), pieces=[planted.assembly.find("node_1_1")])
    assert (result["count"], result["watertight"]) == (1, 1)
    assert result["least_beam_depth"] >= brief.beam_depth - brief.voxel
    assert os.path.exists(tmp_path / "pieces" / "node_1_1.stl") and os.path.exists(tmp_path / "roof_plant.stl")


@pytest.mark.parametrize("row_ok, water_ok, watertight, expected", [
    (True, True, 53, True), (False, True, 53, False), (True, False, 53, False), (True, True, 52, False),
])
def test_the_build_passes_only_if_everything_does(row_ok, water_ok, watertight, expected):
    assert passed([{"ok": row_ok}], {"ok": water_ok}, {"watertight": watertight, "count": 53}) is expected
