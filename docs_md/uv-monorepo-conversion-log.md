# UV Monorepo Conversion Log

This document records the structural changes converting ml-nexus into a uv workspace monorepo and adding the first subpackage.

## Summary of changes
- Added `[tool.uv.workspace]` to root pyproject.toml:
  ```
  [tool.uv.workspace]
  members = ["packages/gce"]
  ```
- Created `packages/gce` (distribution: `ml-nexus-gce`, module: `ml_nexus_gce`) with:
  - `pyproject.toml` using hatchling and `[tool.hatch.build.targets.wheel].packages = ["src/ml_nexus_gce"]`
  - `[tool.uv.sources] ml-nexus = { workspace = true }` to resolve the core package locally
  - Minimal module scaffold with `__version__ = "0.1.0"`
- Updated `.gitignore` to ignore `uv.lock`.

## Local verification done
- `uv sync --all-packages` from repo root
- Import smoke test:
  - `uv run python -c "import ml_nexus_gce"`
  - Verified version printed `0.1.0`

## Rationale
- Align ml-nexus with pinjected’s multi-package uv workspace pattern
- Allow related extensions (like GCE support) to live in the same repository with clear boundaries
- Enable consistent local development and dependency resolution across packages

## Future steps
- Add more subpackages as needed by:
  - Creating `packages/<name>` with its own `pyproject.toml`
  - Registering it under `[tool.uv.workspace].members`
- Implement real functionality in `ml-nexus-gce` (e.g., credential and GCE helpers) once API is decided.
