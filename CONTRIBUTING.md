# Working together

Six people, one repository, no merge disasters. It rests on three habits: you edit your
own folder, you change one thing at a time, and nothing reaches `main` without a pull
request that passes CI and another person has read.

## Your project

Your work lives in `projects/<your-project>/`, which the maintainer creates for you from
`templates/project`. Inside it, arrange things as you need. Outside it, propose changes
by pull request.

Projects don't import each other. If you want something from another project:

1. **Once:** copy it into your project. That is fine, and costs little.
2. **A second project needs it:** move it to [compas_vol](https://github.com/rccn-dev/compas_vol),
   made general, with tests. Then both projects use it from there.

## The daily loop

```bash
git switch main
git pull
uv sync --all-packages
git switch -c ana/wind-erosion        # your name, then the one thing this branch does
```

Work, and commit whenever something works:

```bash
uv run ruff check .
uv run python -m pytest projects/wall-ana
git add projects/wall-ana
git commit -m "Erode the wall where wind concentrates"
git push -u origin ana/wind-erosion
```

If `git commit` says notebook outputs were stripped, that is expected. Run `git add` on the
notebook and commit again.

Open a pull request on GitHub. CI runs the tests and every notebook. Ask one other student
to review, and merge with **Squash and merge** once it is approved and green.

Try to open a pull request within a few days of starting a branch. A small pull request gets
read properly, and a branch that lives for weeks is where merge disasters come from.

## If main moved

```bash
git fetch origin
git merge origin/main
```

Git marks anything it can't combine: edit the file, `git add` it, and `git commit`. If
`uv.lock` conflicts, don't edit it by hand:

```bash
git checkout origin/main -- uv.lock
uv lock
git add uv.lock
git commit
```

Never force-push to a branch someone else is using, and ask if you're unsure before resolving
a conflict in a file you didn't write.

## Reviewing

Reviewing is how bugs get found and how you learn what the others are doing. Answer a request
within a day, by checking out the branch if you can:

- Can you tell what it does and why from the description?
- Is there a test for the new rule or the fixed bug?
- Does anything here belong in `compas_vol`? Is it duplicating something already there?

Files everyone depends on (`.github/`, `scripts/`, `tests/`, `pyproject.toml`, `uv.lock`) need
the maintainer's review, and GitHub asks for it automatically.

## Bugs and features

Open an issue, on whichever repository has the bug, with the smallest code that shows it. Then
whoever fixes it writes a test that fails first and passes after. Anyone can pick up any issue:
assign yourself so two people don't do the same work.

## Changing compas_vol

Clone it next to this repository, and run your project against your copy:

```bash
git clone https://github.com/rccn-dev/compas_vol ../compas_vol
uv run --with-editable ../compas_vol python -m pytest projects/wall-ana
uv run --with-editable ../compas_vol jupyter lab projects/wall-ana/workflow.ipynb
```

Then follow its [CONTRIBUTING](https://github.com/rccn-dev/compas_vol/blob/main/CONTRIBUTING.md):
branch, test, add a file to `changes/`, open a pull request. Its CI also runs every project here
against your change. This repository moves to the new version at the next tagged release, so
your project can rely on it from then on.

`compas_vol` stays general. A brief, a drawing, or anything with a building type in its name
stays in a project.

## Writing workflows

- **Every number goes in the brief**, with a default, in millimetres.
- **One function per step.** It takes the brief and earlier results, and returns its own.
- **Build from `compas_vol.nodes`** wherever a component exists.
- **Notebook cells call steps and show results.** They don't define functions or classes.
- **No Rhino in your package.** It stays CAD-agnostic, and Python 3.9 compatible.
- **Every rule gets a check and a test**, so "beams keep 500 mm" stays true.
- **Fields are defined in world coordinates**, so pieces built apart still meet.

CI checks most of these. Geometry you generate goes in `out/`, which git ignores.

## Using AI

Use Claude, Codex or anything else as much as you like. `AGENTS.md` and `CLAUDE.md` give them
these rules, so they start out knowing how this repository works. Three things stay yours:

- **You are the author.** Read every line before you commit, and be able to explain it in review.
  If you can't, ask the tool to explain it, or don't commit it.
- **Check the geometry yourself.** Passing tests don't mean the field is right. Look at the
  section, and test known distances at known points.
- **Say what you used** in the pull request. It helps reviewers know what to look at, and nobody
  will mark you down for it.

Good uses: explaining an unfamiliar part of the code, writing a failing test from a bug report, a
first review before you ask a person. AI review doesn't replace the human one. Don't paste keys or
anything private into a tool, and keep what you ask it to change small enough to review.
