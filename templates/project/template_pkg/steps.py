"""The workflow: one function per step, each one component on a canvas.

A step takes the brief and what earlier steps made, and returns its own result.
Build steps from ``compas_vol.nodes`` where a component exists, and keep Rhino
out of this package: that is what lets a step become a component later.
"""

import os

import compas

from compas_vol import nodes
from compas_vol.meshing import write_stl

__all__ = ["envelope", "lattice", "porous", "weathered", "export"]


def envelope(brief):
    """The outer form. *Canvas: Volumetric Box.*"""
    return nodes.box(None, brief.size, brief.size, brief.size, 0)


def lattice(brief):
    """The porous pattern, everywhere in space. *Canvas: Volumetric TPMS.*"""
    return nodes.tpms("Gyroid", brief.cell, brief.thickness, "sheet", None)


def porous(envelope, lattice):
    """The pattern inside the form. *Canvas: Volumetric Boolean (intersection).*"""
    return nodes.boolean([envelope, lattice], "intersection", 0)


def weathered(brief, solid):
    """A process shaping the solid: edges wear first. *Canvas: Volumetric Abrasion.*

    Returns a sampled field, which :func:`export` meshes on its own grid.
    """
    field, _ = nodes.abrasion(solid, brief.bounds, brief.resolution, brief.wear, brief.cell / 6, None)
    return field


def export(brief, solid, stem):
    """Write ``<stem>.stl`` (the mesh, for a slicer or CAD) and ``<stem>.json`` (the field).

    Returns ``(vertices, faces)``. *Canvas: Volumetric Mesh.*
    """
    folder = os.path.dirname(stem)
    if folder:
        os.makedirs(folder, exist_ok=True)
    vertices, faces = nodes.mesh(solid, brief.bounds, brief.resolution, 0)
    write_stl(stem + ".stl", vertices, faces)
    compas.json_dump(solid, stem + ".json")
    return vertices, faces
