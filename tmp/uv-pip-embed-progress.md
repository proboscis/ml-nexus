# uv-pip-embed Implementation Progress

## Overview
Successfully implemented `uv-pip-embed` functionality that uses uv to install Python and manages dependencies with `uv pip install` instead of `uv add` and pyproject.toml.

## Completed Tasks

### 1. Added uv-pip-embed case to env_identification.py
- Added handling for "uv-pip-embed" project kind in `a_prepare_setup_script_with_deps`
- Returns appropriate env_deps: ["uv-pip-embedded", "requirements.txt"] or ["uv-pip-embedded", "setup.py"]

### 2. Created a_uv_pip_component_embedded function in universal.py
- Similar structure to `a_pyenv_component_embedded` but uses uv
- Key features:
  - Uses `uv python install` to install Python version
  - Creates virtualenv with `uv venv --python`
  - Installs dependencies with `uv pip install`
  - No cache mounts (embedded)
  - Proper activation script for runtime

### 3. Added uv-pip-embedded case in schematics_universal
- Added handling for "uv-pip-embedded" env_dep
- Calls the new `a_uv_pip_component_embedded` function
- Added function to injected parameters

### 4. Created test IProxy instances
- `test_uv_pip_embed_project` - for requirements.txt projects
- `test_uv_pip_embed_setuppy_project` - for setup.py projects
- Both include Docker environment setup and run scripts

### 5. Validation
- Linter: No new errors introduced (existing complexity warnings remain)
- Pinjected list: All new test IProxy instances properly registered

## Benefits of uv-pip-embed
1. **Faster Python installation** - Uses uv's pre-built binaries instead of building from source
2. **Simpler dependencies** - No need for pyenv build dependencies
3. **pip compatibility** - Works with existing requirements.txt workflows
4. **Embedded dependencies** - Everything baked into Docker image for reproducibility
5. **No pyproject.toml required** - Suitable for legacy projects

## Usage
Projects can now use `kind="uv-pip-embed"` in their ProjectDir definition to use this new component.