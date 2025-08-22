# How to add a new subpackage to the ml-nexus monorepo (uv workspace)

This repository is now organized as a uv workspace, similar to the pinjected monorepo pattern.

## Quick steps

1) Decide the distribution name and module path
- Distribution (project.name): e.g. ml-nexus-foo
- Python module path: e.g. src/ml_nexus_foo

2) Create the directory layout
```
packages/
  foo/
    pyproject.toml
    README.md
    src/
      ml_nexus_foo/
        __init__.py
```

3) Add a pyproject.toml for the subpackage
- Use hatchling for build
- Set the wheel packages to the module directory (not just "src")
- Add ml-nexus as a dependency and resolve it via workspace

Example:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ml-nexus-foo"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["ml-nexus"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.hatch.build.targets.wheel]
packages = ["src/ml_nexus_foo"]

[tool.uv.sources]
ml-nexus = { workspace = true }
```

4) Register the subpackage in the workspace
- Edit the root pyproject.toml:
```toml
[tool.uv.workspace]
members = ["packages/gce", "packages/foo"]
```

5) Sync and test locally
- From repo root:
```
uv sync --all-packages
uv run python -c "import ml_nexus_foo"
```

## Notes
- Do not commit uv.lock (ignored in .gitignore)
- Use uv commands (no pip)
- Keep the wheel packages path precise: ["src/ml_nexus_foo"]
