"""Create a student's project from templates/project.

    uv run python scripts/new_project.py wall-ana --owner ana-github-name
    uv run python scripts/new_project.py wall-ana roof-ben --owner ana-github-name ben-github-name

Each project becomes projects/<name>, with its own package <name_with_underscores>.
Run this for everyone in one go when you can: each new project changes uv.lock.
"""

import argparse
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "templates", "project")
NAME = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
RESERVED = {"compas", "compas-vol", "numpy", "scipy", "tests", "template-pkg"}
TEXT = (".py", ".md", ".toml", ".ipynb")


def create(name, owner, root=ROOT):
    """Create ``projects/<name>`` under ``root`` and return its path.

    Examples
    --------
    >>> create("Not A Name", "someone")
    Traceback (most recent call last):
    ...
    ValueError: 'Not A Name': use lowercase letters, digits and hyphens, like wall-ana
    """
    if not NAME.match(name) or name in RESERVED:
        raise ValueError("{!r}: use lowercase letters, digits and hyphens, like wall-ana".format(name))
    target = os.path.join(root, "projects", name)
    if os.path.exists(target):
        raise ValueError("projects/{} already exists".format(name))
    package = name.replace("-", "_")
    shutil.copytree(TEMPLATE, target, ignore=shutil.ignore_patterns("__pycache__", ".ipynb_checkpoints"))
    os.rename(os.path.join(target, "template_pkg"), os.path.join(target, package))
    for folder, _, files in os.walk(target):
        for file in files:
            if file.endswith(TEXT):
                path = os.path.join(folder, file)
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                text = (text.replace("template_pkg", package).replace("template-pkg", name)
                        .replace("TEMPLATE_OWNER", owner))
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="+", help="project names, such as wall-ana")
    parser.add_argument("--owner", nargs="+", required=True, help="each project's GitHub name, in the same order")
    args = parser.parse_args()
    if len(args.owner) != len(args.names):
        parser.error("give one --owner per project")
    try:
        for name, owner in zip(args.names, args.owner):
            print("created", os.path.relpath(create(name, owner), ROOT))
    except ValueError as error:
        parser.error(str(error))
    subprocess.run(["uv", "sync", "--all-packages"], cwd=ROOT, check=True)
    print("Next: uv run python -m pytest projects/{}".format(args.names[0]))


if __name__ == "__main__":
    main()
