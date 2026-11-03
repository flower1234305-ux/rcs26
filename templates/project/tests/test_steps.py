"""The workflow's steps: they run, and they keep their rules. Add a test for each rule you add."""

import compas
import numpy as np
import pytest

from template_pkg import Brief, steps

pytest.importorskip("skfmm", reason="needs the processes extra")


@pytest.fixture(scope="module")
def brief():
    return Brief(resolution=32)


@pytest.fixture(scope="module")
def solid(brief):
    return steps.porous(steps.envelope(brief), steps.lattice(brief))


def test_a_brief_rejects_unknown_fields():
    with pytest.raises(ValueError, match="Not in the brief"):
        Brief.from_dict({"colour": 3})


def test_the_lattice_stays_inside_the_envelope(brief, solid):
    assert solid.get_distance([brief.size, 0, 0]) > 0


def test_weathering_removes_some_material_and_not_all(brief, solid):
    x, y, z = np.ogrid[-1000:1000:32j, -1000:1000:32j, -1000:1000:32j]
    before = (solid.get_distance_numpy(x, y, z) < 0).sum()
    after = (steps.weathered(brief, solid).get_distance_numpy(x, y, z) < 0).sum()
    assert 0 < after < before


def test_export_writes_the_mesh_and_the_field(tmp_path, brief, solid):
    vertices, faces = steps.export(brief, solid, str(tmp_path / "piece"))
    assert len(faces) > 0
    assert (tmp_path / "piece.stl").stat().st_size > 0
    again = compas.json_load(str(tmp_path / "piece.json"))
    assert again.get_distance([brief.size, 0, 0]) == pytest.approx(solid.get_distance([brief.size, 0, 0]))
