"""Run every project's notebooks from top to bottom, in a throwaway copy.

    uv run python scripts/run_notebooks.py              # every project
    uv run python scripts/run_notebooks.py wall-ana     # one project

A copy, because notebooks write to their own folder (brief.json, out/).
"""

import glob
import os
import shutil
import sys
import tempfile
import time

import nbformat
from nbclient import NotebookClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = shutil.ignore_patterns("tests", "docs", "grasshopper", "scripts", "out", "__pycache__", ".ipynb_checkpoints")


def run(project):
    with tempfile.TemporaryDirectory() as folder:
        copy = os.path.join(folder, "project")
        shutil.copytree(os.path.join(ROOT, "projects", project), copy, ignore=SKIP)
        for path in sorted(glob.glob(os.path.join(copy, "*.ipynb"))):
            started = time.time()
            notebook = nbformat.read(path, as_version=4)
            client = NotebookClient(notebook, timeout=900, kernel_name="python3",
                                    resources={"metadata": {"path": copy}})
            client.execute()
            print("{}/{}: ok in {:.0f}s".format(project, os.path.basename(path), time.time() - started))


def main():
    found = glob.glob(os.path.join(ROOT, "projects", "*", "pyproject.toml"))
    projects = sys.argv[1:] or sorted(os.path.basename(os.path.dirname(p)) for p in found)
    for project in projects:
        run(project)


if __name__ == "__main__":
    main()
