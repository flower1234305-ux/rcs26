"""Drainage in plan: where water goes, and the channels it cuts.

Checked against what has an exact answer -- all the rain on a closed roof
reaches its drains, a channel is as wide as its catchment says -- and against
the properties the channels exist for: they drain, they never undercut what
they are told to keep, and they pass over it instead of ponding behind it.
"""

import numpy as np
import pytest

from grid_roof import Drainage

CELL = 50.0


def grid(nx=41, ny=41):
    return np.meshgrid(np.arange(nx) * CELL, np.arange(ny) * CELL, indexing="ij")


def cone(drain=(1000.0, 1000.0), fall=0.02, nx=41, ny=41):
    x, y = grid(nx, ny)
    return 600.0 + fall * np.hypot(x - drain[0], y - drain[1])


def test_all_the_rain_reaches_the_drain():
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    assert drainage.area[drainage.cell_of((1000, 1000))] == pytest.approx(41 * 41 * CELL * CELL)
    assert not drainage.stranded.any()


def test_rain_is_shared_between_drains():
    x, y = grid(81, 41)
    heights = 600.0 + 0.02 * np.minimum(np.hypot(x - 1000, y - 1000), np.hypot(x - 3000, y - 1000))
    drainage = Drainage(heights, (0, 0), (CELL, CELL), drains=[(1000, 1000), (3000, 1000)])
    left, right = (drainage.area[drainage.cell_of(p)] for p in ((1000, 1000), (3000, 1000)))
    assert left + right == pytest.approx(81 * 41 * CELL * CELL)
    assert left == pytest.approx(right, rel=0.1)


def test_a_hollow_fills_and_overflows_instead_of_swallowing_the_water():
    heights = cone()
    heights[30:33, 30:33] -= 50.0          # a pit on the way down
    drainage = Drainage(heights, (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    assert drainage.area[drainage.cell_of((1000, 1000))] == pytest.approx(41 * 41 * CELL * CELL)


def test_a_basin_with_no_drain_is_reported_not_hidden():
    heights = cone()
    mask = np.ones(heights.shape, dtype=bool)
    mask[25:36, 25] = mask[25:36, 35] = mask[25, 25:36] = mask[35, 25:36] = False   # a walled-off courtyard
    drainage = Drainage(heights, (0, 0), (CELL, CELL), drains=[(1000, 1000)], mask=mask)
    assert drainage.stranded[30, 30]
    assert drainage.stranded.sum() == 9 * 9


def test_water_is_routed_around_a_hole():
    heights = cone()
    mask = np.ones(heights.shape, dtype=bool)
    mask[26:30, 18:23] = False             # an opening between the corner and the drain
    drainage = Drainage(heights, (0, 0), (CELL, CELL), drains=[(1000, 1000)], mask=mask)
    assert drainage.area[drainage.cell_of((1000, 1000))] == pytest.approx(mask.sum() * CELL * CELL)
    assert (drainage.area[~mask] == 0).all()


def test_needs_somewhere_for_the_water_to_go():
    with pytest.raises(ValueError):
        Drainage(cone(), (0, 0), (CELL, CELL))
    Drainage(cone(), (0, 0), (CELL, CELL), outfall=True)


def test_channels_begin_at_their_onset_and_grow_downstream():
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    incision = drainage.incise(onset=0.5e6, width=200.0, depth=60.0)
    assert (drainage.area[incision.channel] >= 0.5e6).all()
    assert not incision.channel[drainage.area < 0.5e6].any()
    i, j = drainage.cell_of((1000, 1000))
    assert incision.width[i, j] == incision.width.max()


def test_width_and_depth_follow_hydraulic_geometry():
    """Width grows as catchment to the 0.5, depth to the 0.4 (Leopold and Maddock)."""
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    incision = drainage.incise(onset=0.2e6, width=200.0, depth=60.0, reference=1.0e6)
    cells = incision.channel
    assert np.allclose(incision.width[cells], 200.0 * (drainage.area[cells] / 1e6) ** 0.5)
    assert np.allclose(incision.depth[cells], 60.0 * (drainage.area[cells] / 1e6) ** 0.4)


def test_channel_beds_drain():
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    incision = drainage.incise(onset=0.3e6, width=200.0, depth=60.0, fall=0.005)
    assert incision.reverse_falls() == 0
    assert incision.cut.max() > 0


def test_a_floor_is_never_cut_below_and_the_bed_grades_over_it():
    """A beam across the fall: the channel passes over it, and does not pond behind it."""
    x, y = grid(81, 21)
    heights = 600.0 + 0.02 * x                     # one fall, towards x = 0
    beam = (x > 1900) & (x < 2500)
    floor = np.where(beam, 620.0, -np.inf)          # the beam keeps its top at 620 mm
    drains = np.zeros(heights.shape, dtype=bool)
    drains[0, 10] = True
    drainage = Drainage(heights, (0, 0), (CELL, CELL), drains=drains)
    incision = drainage.incise(onset=0.1e6, width=150.0, depth=60.0, floor=floor, fall=0.001)
    assert (incision.surface[beam] >= 620.0 - 1e-9).all()
    assert incision.reverse_falls() == 0
    # upstream of the beam the bed rose to meet it, rather than cutting a trough
    upstream = incision.channel & (x >= 2500) & (x < 2700)
    assert (incision.surface[upstream] >= 620.0).all()


def test_the_cut_surface_becomes_a_solid():
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=[(1000, 1000)])
    incision = drainage.incise(onset=0.3e6, width=200.0, depth=60.0)
    solid = incision.to_volume()
    i, j = drainage.cell_of((1000, 1000))
    assert solid.get_distance((1000, 1000, incision.surface[i, j] - 1.0)) < 0
    assert solid.get_distance((1000, 1000, 600.0)) > 0


def test_summary_counts_an_outlet_drawn_as_a_region_once():
    x, y = grid()
    planter = np.hypot(x - 1000, y - 1000) < 200
    drainage = Drainage(cone(), (0, 0), (CELL, CELL), drains=planter)
    summary = drainage.incise(onset=0.3e6).summary()
    assert (summary["outlets"], summary["outlets_used"]) == (1, 1)
    assert summary["stranded"] == 0
