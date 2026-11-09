"""The brief: every number the workflow depends on, in one place."""

import dataclasses
import json
from dataclasses import dataclass

__all__ = ["Brief"]


@dataclass
class Brief:
    """Every number the workflow depends on, with defaults, in millimetres.

    Examples
    --------
    >>> brief = Brief(cell=600.0)
    >>> Brief.from_dict(brief.to_dict()) == brief
    True
    >>> Brief(size=1000.0).bounds
    (-600.0, -600.0, -600.0, 600.0, 600.0, 600.0)
    """

    size: float = 3000.0        # side of the block
    cell: float = 900.0         # lattice period
    thickness: float = 120.0    # lattice wall
    wear: float = 30.0          # removed from a flat face
    margin: float = 100.0       # room around the block to sample
    resolution: int = 64        # samples per axis: 64 to look, more to make

    @property
    def bounds(self):
        """tuple: the sampled box, ``(xmin, ymin, zmin, xmax, ymax, zmax)``."""
        r = self.size / 2 + self.margin
        return (-r, -r, -r, r, r, r)

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
