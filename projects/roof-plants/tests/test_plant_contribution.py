"""The planters as a Contribution: the same cut and wall the drained Step 7 and Step 8 make."""

import dataclasses
import json
import os

import numpy as np
import pytest

import roof_plants as roof
from roof_plants.design import Voids, box, carve
from roof_plants.plant_contribution import Contribution, combine, plant_contribution
from roof_plants.plant_drains import bore_field, plant_steps_drained, planter_drains
from roof_plants.plants import assign, opening_spec

pytest.importorskip("skfmm", reason="needs the processes extra")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def at(field, points):
    """The field's distance at each of ``points`` (n x 3)."""
    p = np.asarray(points, dtype=float)
    return field.get_distance_numpy(p[:, 0], p[:, 1], p[:, 2])


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
    return [opening_spec(p) for p in assign(v1_plants, chosen, len(drawing.planters))]


@pytest.fixture(scope="module")
def drained(brief, drawing, specs):
    return roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))


@pytest.fixture(scope="module")
def contribution(brief, drawing, specs, drained):
    return plant_contribution(brief, drawing, specs, drained.slab)


@pytest.fixture(scope="module")
def bores(brief, drawing, specs, drained):
    return [b for planter in planter_drains(brief, drawing, specs, drained.slab.deck) for b in planter]


@pytest.fixture(scope="module")
def samples(brief):
    """A coarse grid over the whole roof, from below the soffit to above the deck."""
    x0, y0, z0, x1, y1, z1 = brief.bounds
    gx, gy, gz = np.arange(x0 + 75, x1, 150.0), np.arange(y0 + 75, y1, 150.0), np.arange(z0 - 75, z1 + 150, 100.0)
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    return np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])


# ==============================================================================
# combine
# ==============================================================================


def test_combine_adds_then_cuts():
    host = box(0, 0, 0, 100, 100, 100)
    added = Contribution(add=box(100, 0, 0, 200, 100, 100))
    cut = Contribution(cut=box(40, 40, 40, 60, 60, 200))
    solid = combine(host, [added, cut])
    d = at(solid, [[150, 50, 50], [50, 50, 50], [20, 20, 20], [250, 50, 50]])
    assert d[0] < 0       # in the add
    assert d[1] > 0       # in the cut
    assert d[2] < 0       # in the host, clear of the cut
    assert d[3] > 0       # outside everything


def test_combine_takes_a_none_add():
    host = box(0, 0, 0, 100, 100, 100)
    solid = combine(host, [Contribution(add=None, cut=box(40, 40, 40, 60, 60, 200)), Contribution()])
    d = at(solid, [[50, 50, 50], [20, 20, 20]])
    assert d[0] > 0 and d[1] < 0


def test_combine_with_nothing_is_the_host():
    host = box(0, 0, 0, 100, 100, 100)
    assert combine(host, []) is host
    assert combine(host, [Contribution()]) is host


# ==============================================================================
# the planters
# ==============================================================================


def test_the_planters_add_nothing(contribution):
    assert contribution.add is None
    assert contribution.cut is not None and contribution.keep is not None


def test_the_pocket_and_its_bore_are_cut(brief, drawing, specs, drained, contribution, bores):
    """30 mm above the floor and clear of the bore is in the pocket; 100 mm below the floor on the axis is in the bore.

    The bore reaches 50 mm above the floor, so a point above the floor on its
    axis would be cut by the bore alone; the pocket point is beside it, where
    the floor is flat (``inset`` leaves room), and checked to lie outside the bore.
    """
    assert len(bores) == len(drawing.planters)
    assert all(b.inset >= b.radius + 60.0 for b in bores)
    above = [[b.x + b.radius + 60.0, b.y, b.top + 30.0] for b in bores]
    below = [[b.x, b.y, b.top - 100.0] for b in bores]
    assert all(at(bore_field(b), [p])[0] > 0 for b, p in zip(bores, above))
    assert np.all(at(contribution.cut, above) < 0)
    assert np.all(at(contribution.cut, below) < 0)
    planted = combine(drained.slab.solid, [contribution])
    assert np.all(at(planted, above) > 0)
    assert np.all(at(planted, below) > 0)


def test_the_wall_under_the_floor_is_kept(brief, contribution, bores):
    """Half a wall below the floor, beside the bore (the floor is flat there): in ``keep``, out of ``cut``."""
    beside = [[b.x + b.radius + 60.0, b.y, b.top - brief.planter_wall / 2] for b in bores]
    assert all(b.inset >= b.radius + 60.0 for b in bores)
    assert np.all(at(contribution.keep, beside) < 0)
    assert np.all(at(contribution.cut, beside) > 0)


def test_the_cut_is_the_drained_step_7(drained, contribution, samples):
    """Exactly the union of the pockets the drained Step 7 made, bores included."""
    pockets = np.min([at(p, samples) for p in drained.voids.pockets], axis=0)
    assert np.allclose(at(contribution.cut, samples), pockets)
    assert (pockets < 0).sum() > 100


def test_the_walls_are_in_step_8(drained, contribution, samples):
    """``design.keep`` is a union of the beams, the deck and these walls, so it holds every wall point."""
    walls = at(contribution.keep, samples)
    assert (walls < 0).sum() > 100
    assert np.all(at(drained.keep, samples) <= walls + 1e-6)


def test_no_planters_contribute_nothing(brief, drawing, drained):
    """A drawing with no planters: nothing added, cut or kept, and ``combine`` hands the host back."""
    bare = dataclasses.replace(drawing, planters=[])
    c = plant_contribution(brief, bare, [], drained.slab)
    assert c == Contribution(None, None, None)
    host = drained.slab.solid
    assert combine(host, [c]) is host


def test_combine_agrees_with_the_drained_roof(drained, contribution, samples, bores):
    """``combine`` of the slab carved without its pockets matches Step 7's carve, away from the seams.

    The two cannot agree everywhere: ``carve`` cuts each pocket with an 80 mm
    blend and ``combine`` cuts with none, so within about 80 mm of a pocket's
    edge they differ. Away from it -- where the original is more than 100 mm
    inside or outside -- the signs must match. The grid is too coarse to hit
    an 80 mm bore, so each bore's axis is checked on its own: open in both.
    """
    v = drained.voids
    host = carve(drained.slab.solid, Voids(v.openings, [], v.outlets))
    planted = combine(host, [contribution])
    original = carve(drained.slab.solid, v)
    ours, theirs = at(planted, samples), at(original, samples)
    clear = np.abs(theirs) > 100.0
    under_deck = samples[:, 2] < drained.slab.deck.height_at(samples[:, 0], samples[:, 1])
    in_pocket_in_slab = clear & under_deck & (at(contribution.cut, samples) < 0)
    assert in_pocket_in_slab.sum() > 50 and (clear & (theirs < 0)).sum() > 1000
    assert np.array_equal(ours[clear] < 0, theirs[clear] < 0)
    axes = [[b.x, b.y, z] for b in bores for z in np.arange(20.0, b.top, 40.0)]
    assert np.all(at(planted, axes) > 0) and np.all(at(original, axes) > 0)
