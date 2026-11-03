# Install

Commands go in *Terminal* on macOS, *PowerShell* on Windows.

## 1 · git and uv

| | macOS | Windows |
|---|---|---|
| git | `xcode-select --install` (also the compiler one package needs) | [Git for Windows](https://git-scm.com/download/win), default options |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |

Open a new terminal afterwards: `git --version` and `uv --version` should both answer.
You do not need to install Python; uv fetches the version this repository asks for.

Tell git who you are, with the email on your GitHub account:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## 2 · Clone and install

```bash
git clone https://github.com/rccn-dev/studio
cd studio
uv sync --all-packages
uv run pre-commit install
```

The first `uv sync` takes a few minutes. Run every later command from this `studio` folder.
`pre-commit` strips notebook outputs and runs the linter each time you commit.

## 3 · Check

```bash
uv run python -m pytest
uv run jupyter lab projects/roof/walkthrough.ipynb
```

The tests pass in under a minute. In Jupyter, choose *Run › Run All Cells*: it ends
without a red error, in about a minute.

## Trouble

| Symptom | Fix |
|---|---|
| `git` or `uv`: command not found | open a new terminal; on Windows, sign out and in again |
| `uv sync` fails building scikit-fmm on macOS | `xcode-select --install`, then `uv sync --all-packages` again |
| Jupyter: `ModuleNotFoundError` for your package | `uv sync --all-packages`, then start Jupyter with `uv run`, from the `studio` folder |
| a cell runs for minutes, or the computer stalls | the brief's voxel or resolution is too fine for this laptop |
| `MemoryError` building a piece | close other programs; or a coarser voxel |
