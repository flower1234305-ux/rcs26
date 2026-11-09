"""Fixtures the planter tests share."""

import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def at_v1_depth(plants):
    """The plants with group3_upright at its v1 depth, 360 mm.

    The mechanism tests run on the v1 planting, which fits. Since 2026-11-09
    plants.json has depth 400 (Wei's decision), and that fits no planter where it
    is drawn: tests/test_plant_fit.py, and docs/roof-plants.md, v2, item 5.
    """
    return dict(plants, group3_upright=dict(plants["group3_upright"], depth=360))


@pytest.fixture(scope="session")
def v1_plants():
    """plants.json with group3_upright at its v1 depth (see :func:`at_v1_depth`)."""
    from roof_plants.plants import load_plants

    return at_v1_depth(load_plants(os.path.join(HERE, "plants.json")))
