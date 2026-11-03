"""The kit of parts: a slab on a beam grid cut into nodes, whole beams and panels."""

import numpy as np
import pytest
from compas.geometry import Box, Frame

from compas_vol.assembly import segment
from compas_vol.combinations import Subtraction
from compas_vol.primitives import VolBox, VolCylinder

from grid_roof import beam_bands, grid_kit


def _frame(point):
    return Frame(point, (1, 0, 0), (0, 1, 0))


def test_beam_bands_hold_edge_beams_inboard():
    assert beam_bands([0, 6000, 12000], 600, 0, 12000) == [(0.0, 600.0), (5700.0, 6300.0), (11400.0, 12000.0)]
    with pytest.raises(ValueError):
        beam_bands([0, 400], 600, 0, 6000)


def test_grid_kit_makes_nodes_beams_and_panels_that_tile_the_slab():
    bounds = (0, 0, 0, 18000, 12000, 600)
    cells = grid_kit(bounds, [0, 6000, 12000, 18000], [0, 6000, 12000], 600, 3000)
    volume = sum(np.prod([c["bounds"][i + 3] - c["bounds"][i] for i in range(3)]) for c in cells)
    assert volume == pytest.approx(18000 * 12000 * 600)
    beams = [c for c in cells if c["role"] == "beam"]
    # every beam spans its whole bay: no joint at mid-span
    assert all(max(c["bounds"][3] - c["bounds"][0], c["bounds"][4] - c["bounds"][1]) >= 5100 for c in beams)
    panels = [c for c in cells if c["role"] == "panel"]
    assert all(max(c["bounds"][3] - c["bounds"][0], c["bounds"][4] - c["bounds"][1]) <= 3000 for c in panels)
    assembly = segment(VolBox(Box(18000, 12000, 600, frame=_frame((9000, 6000, 300))), 0.0), bounds, cells=cells)
    assert len(assembly) == 53


def test_grid_kit_moves_panel_joints_off_an_opening():
    """A hole where the even split would cut: the joint moves beside it."""
    from compas.geometry import Cylinder

    slab = VolBox(Box(6000, 6000, 600, frame=_frame((3000, 3000, 300))), 0.0)
    hole = VolCylinder(Cylinder(500, 2000, frame=_frame((3000, 3000, 300))))
    model = Subtraction(slab, hole)
    bounds = (0, 0, 0, 6000, 6000, 600)
    even = grid_kit(bounds, [0, 6000], [0, 6000], 600, 3000)
    moved = grid_kit(bounds, [0, 6000], [0, 6000], 600, 3000, model=model, shift=600.0, step=50.0)

    def cuts(cells):
        return sorted({c["bounds"][3] for c in cells if c["role"] == "panel"} - {5400.0})

    assert cuts(even) == [3000.0]
    assert abs(cuts(moved)[0] - 3000.0) >= 500.0
