"""design_roof's steps table: unused, it changes nothing; used, it replaces what it names, and only that."""

import dataclasses
import os

import numpy as np
import pytest

import roof_plants as roof

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def brief():
    return roof.Brief(voxel=60.0)


@pytest.fixture(scope="module")
def drawing():
    return roof.Drawing.load(os.path.join(HERE, "drawing.json"))


def steps_in_their_original_order(brief, drawing):
    """The body of design_roof as it was before the steps table: the reference it must not disturb."""
    b = roof.beams(brief)
    incision = roof.water(brief, drawing, b)
    s = roof.slab(brief, incision)
    f = roof.soffit(brief, s, b)
    v = roof.voids(brief, drawing, s)
    k = roof.keep(brief, b, s, f, v)
    d = roof.design(s, f, v, k)
    return roof.Roof(b, incision, s, f, v, k, d, roof.kit(brief, d), roof.weathering(brief, k, s))


def worst_difference(field_a, field_b, brief, seed=0, count=100000):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-200, brief.length + 200, count)
    y = rng.uniform(-200, brief.width + 200, count)
    z = rng.uniform(-100, brief.thickness + 100, count)
    return float(np.abs(field_a.get_distance_numpy(x, y, z) - field_b.get_distance_numpy(x, y, z)).max())


def test_without_steps_the_roof_is_the_original_at_every_sample(brief, drawing):
    original = steps_in_their_original_order(brief, drawing)
    hooked = roof.design_roof(brief, drawing)
    assert np.array_equal(hooked.incision.surface, original.incision.surface)
    assert worst_difference(hooked.design.roof, original.design.roof, brief) == 0.0
    assert worst_difference(hooked.design.drawn, original.design.drawn, brief) == 0.0
    assert worst_difference(hooked.keep, original.keep, brief) == 0.0
    assert [p.name for p in hooked.assembly] == [p.name for p in original.assembly]


def test_a_water_step_changes_step_4_only(brief, drawing):
    def no_planters(brief_, drawing_, beams_):
        return roof.water(brief_, dataclasses.replace(drawing_, planters=[]), beams_)

    original = roof.water(brief, drawing, roof.beams(brief))
    hooked = roof.design_roof(brief, drawing, steps={"water": no_planters})
    assert not np.array_equal(hooked.incision.surface, original.surface)
    assert len(hooked.voids.pockets) == len(drawing.planters)   # Step 7 still reads the real drawing


def test_a_voids_step_replaces_step_7(brief, drawing):
    calls = []

    def no_pockets(brief_, drawing_, slab_):
        calls.append((brief_, drawing_))
        return dataclasses.replace(roof.voids(brief_, drawing_, slab_), pockets=[])

    built = roof.design_roof(brief, drawing, steps={"voids": no_pockets})
    assert calls == [(brief, drawing)]
    assert built.voids.pockets == []


def test_an_unknown_step_is_refused_before_anything_runs(brief, drawing):
    with pytest.raises(ValueError, match="soffit.*these can be: voids, water"):
        roof.design_roof(brief, drawing, steps={"soffit": print})


def test_steps_can_only_be_passed_by_name(brief, drawing):
    with pytest.raises(TypeError):
        roof.design_roof(brief, drawing, {})
