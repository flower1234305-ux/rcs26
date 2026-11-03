# Install

Everything runs in Jupyter, on macOS or Windows. Commands go in *Terminal* on macOS,
*PowerShell* on Windows.

## 1 · git and uv

| | macOS | Windows |
|---|---|---|
| git | `xcode-select --install` (also the compiler one package needs) | [Git for Windows](https://git-scm.com/download/win), default options |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

Open a new terminal afterwards: `git --version` and `uv --version` should both answer.
You do not need to install Python; uv fetches the version this repository asks for (3.13).

## 2 · The two repositories

Clone compas_vol and this repository into one folder. This repository finds compas_vol at
`../compas_vol`, so keep that folder name:

```bash
mkdir workshop
cd workshop
git clone https://github.com/rccn-dev/compas_vol
git clone https://github.com/rccn-dev/grid-roof
```

Working on your own copy? Clone that in place of `grid-roof` ([your design](your-design.md)).

## 3 · Install and open the walkthrough

```bash
cd grid-roof
uv sync --extra notebook
uv run jupyter lab walkthrough.ipynb
```

The first `uv sync` takes a few minutes; on macOS it compiles one package. Jupyter opens in
your browser. Next time, only the last line is needed, from the `grid-roof` folder.

## 4 · Check

1. Run Step 0: click it, then Shift+Enter. `skimage` and `skfmm` should say *yes*.
2. *Run › Run All Cells*. It ends without a red error, in about a minute.

Then read [notebook](notebook.md).

## Trouble

| Symptom | Fix |
|---|---|
| `git` or `uv`: command not found | open a new terminal; on Windows, sign out and in again |
| `uv sync` cannot find `compas-vol` | clone compas_vol next to this folder, named `compas_vol` |
| `uv sync` fails building scikit-fmm on macOS | `xcode-select --install`, then `uv sync --extra notebook` again |
| Jupyter: `ModuleNotFoundError: grid_roof` | start Jupyter with `uv run`, from the `grid-roof` folder |
| a cell runs for minutes, or the computer stalls | Step 1's `voxel` is too fine for this laptop: back to 40 |
| `MemoryError` building a piece | close other programs; or a coarser `--voxel` ([build](build.md)) |
