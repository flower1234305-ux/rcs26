"""The walkthrough is code too: it must parse, and call nothing that no longer exists.

Executing them is a few minutes of processes, so it is left to whoever edits
them (see the notebook's own header). This catches the usual way a notebook
rots without running it: an API it calls has moved on.
"""

import ast
import json
import os

import pytest

FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOKS = sorted(f for f in os.listdir(FOLDER) if f.endswith(".ipynb")) if os.path.isdir(FOLDER) else []


def code_of(name):
    with open(os.path.join(FOLDER, name), encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    sources = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    # IPython magics are not Python.
    return "\n".join(line for source in sources for line in source.splitlines() if not line.startswith("%"))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_parses(name):
    ast.parse(code_of(name), feature_version=(3, 9))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_calls_only_nodes_that_exist(name):
    """`nodes.box` in a notebook is the Box component; if it calls one, it has to still be there."""
    from compas_vol import nodes

    used = {
        node.attr for node in ast.walk(ast.parse(code_of(name)))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "nodes"
    }
    assert used <= set(nodes.__all__), "gone from compas_vol.nodes: {}".format(sorted(used - set(nodes.__all__)))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_imports_resolve(name):
    import importlib

    tree = ast.parse(code_of(name))
    for node in ast.walk(tree):
        ours = node.module.split(".")[0] in ("compas_vol", "grid_roof") if isinstance(node, ast.ImportFrom) else False
        if ours:
            module = importlib.import_module(node.module)
            for alias in node.names:
                assert hasattr(module, alias.name), "{}.{} is gone".format(node.module, alias.name)


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_was_saved_without_errors(name):
    with open(os.path.join(FOLDER, name), encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    errors = [o for c in cells for o in c.get("outputs", []) if o.get("output_type") == "error"]
    assert not errors, "saved with an error in its outputs: {}".format(errors[0].get("evalue"))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_uses_only_roof_names_that_exist(name):
    import grid_roof

    used = {
        node.attr for node in ast.walk(ast.parse(code_of(name)))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "roof"
    }
    known = set(grid_roof.__all__)
    assert used <= known, "not in grid_roof: {}".format(sorted(used - known))
