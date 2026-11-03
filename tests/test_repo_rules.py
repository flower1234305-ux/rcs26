"""The rules that let six people work in one repository, checked rather than remembered."""

import ast
import glob
import json
import os
import re
import runpy
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOUND = glob.glob(os.path.join(ROOT, "projects", "*", "pyproject.toml"))
PROJECTS = sorted(os.path.basename(os.path.dirname(p)) for p in FOUND)
CAD = {"Rhino", "rhinoscriptsyntax", "scriptcontext", "ghpythonlib", "System", "clr"}


def package_of(project):
    """A project's package: the folder named in its pyproject.toml."""
    text = open(os.path.join(ROOT, "projects", project, "pyproject.toml"), encoding="utf-8").read()
    return re.search(r'module-name\s*=\s*"(\w+)"', text).group(1)


PACKAGES = {project: package_of(project) for project in PROJECTS}
NOTEBOOKS = sorted(glob.glob(os.path.join(ROOT, "projects", "*", "*.ipynb")))


def names_imported(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module.split(".")[0]


def notebook_code(path):
    with open(path, encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    sources = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    return "\n".join(line for s in sources for line in s.splitlines() if not line.lstrip().startswith(("%", "!")))


def python_files(project):
    """The project's code, except Grasshopper components, which are allowed to import Rhino."""
    for path in glob.glob(os.path.join(ROOT, "projects", project, "**", "*.py"), recursive=True):
        if "grasshopper" not in path.split(os.sep):
            yield path


@pytest.mark.parametrize("project", PROJECTS)
def test_every_project_names_its_owner(project):
    text = open(os.path.join(ROOT, "projects", project, "pyproject.toml"), encoding="utf-8").read()
    assert re.search(r'^\[tool\.rcs26\]\s*\nowner\s*=\s*"[^"]+"', text, re.M), "add [tool.rcs26] owner = \"...\""


@pytest.mark.parametrize("project", PROJECTS)
def test_projects_do_not_import_each_other(project):
    """Code two projects need belongs in compas_vol. See CONTRIBUTING.md."""
    others = set(PACKAGES.values()) - {PACKAGES[project]}
    sources = [open(p, encoding="utf-8").read() for p in python_files(project)]
    sources += [notebook_code(p) for p in NOTEBOOKS if os.sep + project + os.sep in p]
    for source in sources:
        assert not set(names_imported(ast.parse(source))) & others


@pytest.mark.parametrize("project", PROJECTS)
def test_workflows_are_cad_agnostic(project):
    """Rhino belongs only in grasshopper/."""
    for path in python_files(project):
        with open(path, encoding="utf-8") as f:
            found = set(names_imported(ast.parse(f.read()))) & CAD
        assert not found, "{} imports {}".format(os.path.relpath(path, ROOT), sorted(found))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: os.path.relpath(p, ROOT))
def test_notebooks_are_committed_without_outputs(path):
    """Outputs make every diff unreadable and every merge a conflict."""
    with open(path, encoding="utf-8") as f:
        cells = json.load(f)["cells"]
    dirty = [c for c in cells if c["cell_type"] == "code" and (c.get("outputs") or c.get("execution_count"))]
    assert not dirty, "run: uv run nbstripout {}".format(os.path.relpath(path, ROOT))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: os.path.relpath(p, ROOT))
def test_notebooks_hold_no_logic_of_their_own(path):
    """A cell calls steps, as a canvas wires components. Functions and classes go in the package."""
    tree = ast.parse(notebook_code(path), feature_version=(3, 9))
    defined = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    assert not defined, "move these into the project's package: {}".format(defined)


def test_no_large_or_generated_files_are_committed():
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    for name in tracked.splitlines():
        path = os.path.join(ROOT, name)
        assert not name.lower().endswith((".stl", ".3dm", ".npz")), "generated file committed: {}".format(name)
        if os.path.exists(path):
            assert os.path.getsize(path) < 5_000_000, "over 5 MB: {}".format(name)


def test_new_project_makes_a_project_that_keeps_the_rules(tmp_path):
    tool = runpy.run_path(os.path.join(ROOT, "scripts", "new_project.py"))
    target = tool["create"]("wall-ana", "ana", root=str(tmp_path))
    assert os.path.isdir(os.path.join(target, "wall_ana"))
    for path in glob.glob(os.path.join(target, "**", "*"), recursive=True):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert not re.search(r"template[_-]pkg|TEMPLATE_OWNER", text), path
    with pytest.raises(ValueError, match="already exists"):
        tool["create"]("wall-ana", "ana", root=str(tmp_path))
