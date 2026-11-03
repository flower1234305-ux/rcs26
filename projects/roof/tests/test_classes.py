"""The roof's own volumetric classes: analytic checks, plus the checks every compas_vol class gets.

compas_vol runs scalar-against-numpy, no-mutation and JSON round-trip checks over
every class it ships (tests/conftest.py there). These classes left it for this
project, so the same checks are repeated here.
"""

import copy
import math

import compas
import numpy as np
import pytest
from compas.geometry import Plane

from compas_vol.modifications import Remap
from compas_vol.primitives import VolPlane

from grid_roof import Spinodoid, VolHeightField

OBJECTS = {
    "VolHeightField": VolHeightField(
        4.0 + 0.02 * (np.linspace(-20, 20, 21)[:, None] ** 2 - np.linspace(-20, 20, 17)[None, :] ** 2),
        (-20, -16),
        (2.0, 2.0),
    ),
    "Spinodoid": Spinodoid(8.0, 0.4, waves=24, seed=2),
    "Spinodoid-graded": Spinodoid(8.0, Remap(VolPlane(Plane((0, 0, 0), (0.2, 0.3, 1))), (-10.0, 10.0), (0.2, 0.8)),
                                  waves=16, seed=5),
}
POINTS = [(0.0, 0.0, 0.0), (3.5, -2.0, 1.0), (-7.0, 4.0, -2.5), (12.0, 9.0, 6.0)]


@pytest.mark.parametrize("name", sorted(OBJECTS))
def test_scalar_and_numpy_agree(name):
    obj = OBJECTS[name]
    x, y, z = np.ogrid[-10:10:9j, -8:8:7j, -5:5:5j]
    grid = obj.get_distance_numpy(x, y, z)
    for i, j, k in ((0, 0, 0), (4, 3, 2), (8, 6, 4)):
        point = [float(x[i, 0, 0]), float(y[0, j, 0]), float(z[0, 0, k])]
        assert obj.get_distance(point) == pytest.approx(float(np.broadcast_to(grid, (9, 7, 5))[i, j, k]), abs=1e-9)


@pytest.mark.parametrize("name", sorted(OBJECTS))
def test_queries_do_not_mutate_their_input(name):
    for point in POINTS:
        before = copy.deepcopy(point)
        OBJECTS[name].get_distance(point)
        assert point == before


@pytest.mark.parametrize("name", sorted(OBJECTS))
def test_json_round_trip(name):
    obj = OBJECTS[name]
    again = compas.json_loads(compas.json_dumps(obj))
    for point in POINTS:
        assert again.get_distance(point) == pytest.approx(obj.get_distance(point))


class TestHeightField:
    def test_flat_surface_is_a_plane(self):
        flat = VolHeightField(np.full((4, 4), 600.0), (0, 0), (100, 100))
        assert flat.get_distance((150, 150, 450)) == pytest.approx(-150.0)
        assert flat.get_distance((150, 150, 610)) == pytest.approx(10.0)

    def test_sloped_plane_is_measured_square_to_it(self):
        """A 1:10 fall: vertical offset divided by sqrt(1 + 0.01) is the true distance."""
        x = np.linspace(0, 1000, 11)[:, None] + np.zeros((1, 3))
        ramp = VolHeightField(0.1 * x, (0, 0), (100, 100))
        assert ramp.get_distance((500, 100, 60)) == pytest.approx(10.0 / math.sqrt(1.01))

    def test_heights_interpolate_between_samples(self):
        field = VolHeightField([[0.0, 0.0], [10.0, 10.0]], (0, 0), (1, 1))
        assert field.height_at(0.25, 0.5) == pytest.approx(2.5)

    def test_surface_continues_flat_beyond_the_grid(self):
        field = VolHeightField([[0.0, 0.0], [10.0, 10.0]], (0, 0), (1, 1))
        assert field.height_at(5.0, 0.5) == pytest.approx(10.0)

    def test_rejects_a_one_dimensional_grid(self):
        with pytest.raises(ValueError):
            VolHeightField([1.0, 2.0, 3.0])


class TestSpinodoid:
    def test_solid_fraction_is_close_to_the_one_asked_for(self):
        x, y, z = np.ogrid[0:200:81j, 0:200:81j, 0:200:81j]
        for fraction in (0.3, 0.5, 0.7):
            foam = Spinodoid(20.0, fraction, waves=48, seed=1)
            assert (foam.get_distance_numpy(x, y, z) < 0).mean() == pytest.approx(fraction, abs=0.05)

    def test_the_same_foam_everywhere_whatever_the_box(self):
        """What makes it usable piece by piece: overlapping boxes agree exactly."""
        foam = Spinodoid(15.0, 0.45, seed=4)
        a = foam.get_distance_numpy(*np.ogrid[0:40:21j, 0:40:21j, 0:40:21j])
        b = foam.get_distance_numpy(*np.ogrid[20:60:21j, 20:60:21j, 20:60:21j])
        assert np.array_equal(a[10:, 10:, 10:], b[:11, :11, :11])

    def test_approximately_metric_near_the_surface(self):
        foam = Spinodoid(20.0, 0.5, waves=48, seed=2)
        x, y, z = np.ogrid[0:100:101j, 0:100:101j, 0:100:101j]
        values = foam.get_distance_numpy(x, y, z)
        slope = np.sqrt(sum(g * g for g in np.gradient(values, 1.0)))
        near = np.abs(values) < 1.0
        assert np.median(slope[near]) == pytest.approx(1.0, abs=0.25)

    def test_graded_fraction_follows_its_driver(self):
        ramp = Remap(VolPlane(Plane((0, 0, 0), (0, 0, 1))), (0.0, 200.0), (0.2, 0.8))
        foam = Spinodoid(15.0, ramp, waves=48, seed=3)
        x, y = np.ogrid[0:300:61j, 0:300:61j]

        def solid(z0, z1):
            z = np.linspace(z0, z1, 5)[None, None, :]
            return (foam.get_distance_numpy(x[:, :, None], y[:, :, None], z) < 0).mean()

        low, high = solid(0, 20), solid(180, 200)
        assert low < 0.35 < 0.65 < high

    def test_rejects_a_bad_wavelength(self):
        with pytest.raises(ValueError):
            Spinodoid(0.0, 0.5)
