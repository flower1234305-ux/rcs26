"""The functions behind the Grasshopper components, called the way the components call them."""

import pytest

from grid_roof import nodes

pytest.importorskip("skfmm", reason="needs the processes extra")


class RhinoPoint:
    """Stands in for Rhino.Geometry.Point3d."""

    def __init__(self, x, y, z=0.0):
        self.X, self.Y, self.Z = x, y, z


@pytest.fixture(scope="module")
def brief():
    return nodes.brief(voxel=60)


@pytest.fixture(scope="module")
def drawing():
    return nodes.drawing()


@pytest.fixture(scope="module")
def built(brief, drawing):
    return nodes.design(brief, drawing)


def test_a_drawing_from_rhino_points_replaces_only_what_is_given():
    outline = [RhinoPoint(4000, 4000), RhinoPoint(5000, 4000), RhinoPoint(5000, 5000), RhinoPoint(4000, 5000)]
    result = nodes.drawing(openings=[outline], drains=[RhinoPoint(1000, 1000)])
    assert len(result.openings) == 1 and len(result.openings[0]) == 5
    assert len(result.planters) == len(nodes.drawing().planters)
    assert list(result.drains[0]) == [1000.0, 1000.0, 0.0]


def test_the_report_states_each_check(built, brief, drawing):
    text = nodes.report(built, brief, drawing)
    assert "0 puddles" in text
    assert text.count("opening") == len(drawing.openings)
    assert "kit: 53 pieces: 12 nodes, 17 beams, 24 panels" in text


def test_pieces_lie_inside_the_roof(built, brief):
    listed = nodes.pieces(built)
    assert len(listed) == 53
    x0, y0, z0, x1, y1, z1 = brief.bounds
    assert all(b[0] >= x0 - 1 and b[3] <= x1 + 1 and b[1] >= y0 - 1 and b[4] <= y1 + 1 for _, b in listed)


def test_a_piece_is_built_watertight(built, brief):
    vertices, faces, text = nodes.piece(built, brief, "beam_x0_0_0")
    assert len(faces) > 0
    assert "watertight True" in text and "least beam depth" in text


def test_an_unknown_piece_names_the_ones_there_are(built, brief):
    with pytest.raises(ValueError, match="panel_0_1_00"):
        nodes.piece(built, brief, "panel_9")
