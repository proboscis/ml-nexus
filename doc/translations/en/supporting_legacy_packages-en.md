# Handling Legacy Packages with Build-time Dependencies

## Overview

This document describes a solution for properly handling legacy libraries like basicsr that require specific dependencies (such as torch) during build time when using UV package manager.

## Problem

Some legacy packages (such as basicsr) require specific dependencies (such as torch) during their build process. The standard approach with UV may encounter installation problems with these packages.

## Solution

### 1. Separate Project Dependencies

Properly separate dependencies in `pyproject.toml`:

```toml
[project.optional-dependencies]
build = [
  "torch==2.3.0",
  "cython",
  "numpy>=1.17"
]
basicsr = [
  "basicsr==1.3.5"
]
[tool.uv]
no-build-isolation-package = ["basicsr"]
```

### 2. Customize schematics init_script

Use the `a_map_scripts` method to dynamically modify scripts:

```python
schematic = schematic_universal(project)
@injected
async def a_hack_uv_sync_with_torch_dep_package(lines: list[str]) -> list[str]:
    # This hack works!
    res = []
    for line in lines:
        if 'uv sync' in line:
            res += [
                "uv sync --extra build",
                "uv sync --extra build --extra basicsr"
            ]
        else:
            res.append(line)
    return res
hacked_schematics = schematic.a_map_scripts(a_hack_uv_sync_with_torch_dep_package).await__()
```

This approach replaces the standard `uv sync` command with multiple commands that include optional dependencies.

## Implementation Status

* `pinjected` dependency has been updated to 0.2.245
* `a_map_scripts` method has been added to the `ContainerSchematic` class
* Test implementation has been added in `test_schematics_for_uv_with_accelerator.py`

## Future Considerations

It is recommended to standardize this approach to automatically apply it to specific package types.