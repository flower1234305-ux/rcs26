"""The roof's steps: they run, they keep their rules, and the brief and drawing round-trip."""

import pytest

import grid_roof as roof
from compas_vol import nodes
from compas_vol.assembly import Seams
from compas_vol.meshing import is_watertight

pytest.importorskip("skfmm", reason="needs the processes extra")


@pytest.fixture(scope="module")
def brief():
    return roof.Brief(voxel=60.0)


@pytest.fixture(scope="module")
def drawing():
    return roof.Drawing.sample()


@pytest.fixture(scope="module")
def built(brief, drawing):
    return roof.design_roof(brief, drawing)


def test_brief_and_drawing_round_trip(tmp_path, brief, drawing):
    assert roof.Brief.load(brief.save(tmp_path / "brief.json")) == brief
    again = roof.Drawing.load(drawing.save(str(tmp_path / "drawing.json")))
    assert [list(p) for p in again.drains] == [list(p) for p in drawing.drains]
    assert len(again.openings[0]) == len(drawing.openings[0])


def test_a_brief_rejects_unknown_fields():
    with pytest.raises(ValueError, match="Not in the brief"):
        roof.Brief.from_dict({"beams": 600})


def test_the_water_drains(built):
    summary = built.incision.summary()
    assert summary["stranded"] == 0 and summary["reverse_falls"] == 0
    assert summary["outlets_used"] == summary["outlets"]


def test_channels_never_cut_a_beam_below_its_depth(brief, built):
    import numpy as np

    surface = built.incision.surface
    x = np.arange(surface.shape[0]) * brief.plan_cell
    on_beam = np.zeros(surface.shape, dtype=bool)
    for lo, hi in built.beams.xbands:
        on_beam |= ((x >= lo) & (x <= hi))[:, None]
    assert surface[on_beam].min() >= brief.beam_depth - 1e-6


def test_light_goes_through(brief, drawing, built):
    for aperture in roof.clear_apertures(brief, drawing, built.design.roof):
        assert aperture["clear"] >= 0.9 * aperture["drawn"]


def test_the_kit_follows_the_beam_grid(built):
    roles = [piece.role for piece in built.assembly]
    assert (roles.count("node"), roles.count("beam"), roles.count("panel")) == (12, 17, 24)


def test_a_weathered_beam_keeps_its_depth_and_meets_its_neighbour(brief, built):
    pieces = [built.assembly.find(name) for name in ("node_1_1", "beam_x1_1_0")]
    seams = Seams(built.assembly, brief.voxel)
    for piece, field, raw in built.assembly.build(built.weathering, brief.voxel, brief.halo, pieces=pieces,
                                                  seams=seams):
        assert raw.violation()["keep"] < brief.voxel
        assert roof.beam_depth(raw, built.beams, piece.bounds) >= brief.beam_depth - brief.voxel
        vertices, faces = nodes.mesh(field.to_volume(), None, None, 0)
        assert is_watertight(vertices, faces)
    assert seams.summary()["faces"] == 1 and seams.summary()["disagreement"] < 0.01
