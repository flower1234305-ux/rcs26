"""The brief: every number the roof depends on, in one place."""

import dataclasses
import json
from dataclasses import dataclass, field

__all__ = ["Brief"]


@dataclass
class Brief:
    """Every number the roof depends on, with defaults, in millimetres.

    Saves to and loads from JSON, so ``build.py`` builds exactly what the
    walkthrough designed. Each step's docstring lists the fields it reads.

    Examples
    --------
    >>> brief = Brief(beam=500.0)
    >>> brief.bounds
    (0.0, 0.0, 0.0, 18000.0, 12000.0, 600.0)
    >>> Brief.from_dict(brief.to_dict()) == brief
    True
    """

    # the brief
    length: float = 18000.0
    width: float = 12000.0
    thickness: float = 600.0
    grid_x: list = field(default_factory=lambda: [0.0, 6000.0, 12000.0, 18000.0])
    grid_y: list = field(default_factory=lambda: [0.0, 6000.0, 12000.0])
    beam: float = 600.0                 # beam width
    beam_depth: float = 500.0           # depth every beam keeps, from the soffit

    # water
    fall: float = 1 / 60                # deck falls to the drains
    relief: float = 25.0                # undulation, so water meanders
    relief_seed: int = 11
    plan_cell: float = 50.0             # drainage grid
    upstand: float = 150.0              # how far water is kept off a light opening
    channel_onset: float = 1.5e6        # catchment where a channel starts, mm2
    channel_width: float = 220.0        # at 10 m2 of catchment
    channel_depth: float = 80.0         # at 10 m2 of catchment
    channel_limit: float = 170.0        # deepest any channel may be
    channel_reach: float = 260.0        # lowest a channel bed may go below the top, off the beams

    # the soffit
    skin: float = 120.0                 # solid deck over the pores
    pore: float = 700.0                 # pore to pore
    fraction_deck: float = 0.95         # solid share just under the deck
    fraction_soffit: float = 0.42       # solid share at the soffit
    beam_haunch: float = 900.0          # how far from a beam the foam closes up
    foam_seed: int = 8

    # light and planters
    opening_flare: float = 260.0        # wider at the faces than at mid-depth
    planter_depth: float = 350.0
    planter_rim: float = 220.0
    planter_wall: float = 150.0
    outlet: float = 80.0                # rainwater outlet bore radius

    # fabrication
    panel: float = 3000.0               # largest panel
    cut_shift: float = 450.0            # how far a panel joint may move off an even split
    clearance: float = 10.0             # joint gap
    dowel: float = 60.0                 # dowel diameter
    dowel_fit: float = 2.0              # radial clearance of a dowel in its socket
    min_feature: float = 80.0           # thinnest wall that may survive
    pit_depth: float = 60.0
    wear: float = 20.0
    erosion_margin: float = 150.0       # erosion fades out over this distance from what is kept
    hardness_seed: int = 3
    halo: float = 320.0                 # margin each piece is weathered with
    voxel: float = 40.0                 # 40 to look, 10 - 15 to make

    @property
    def bounds(self):
        """tuple: ``(xmin, ymin, zmin, xmax, ymax, zmax)`` of the slab."""
        return (0.0, 0.0, 0.0, float(self.length), float(self.width), float(self.thickness))

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in dataclasses.fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError("Not in the brief: {}".format(", ".join(sorted(unknown))))
        return cls(**data)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=1)
        return path

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
