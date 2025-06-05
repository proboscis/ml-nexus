# Progress: Testing schematics_universal for Different ProjectDir Kinds

## Overview
This document tracks the progress of creating comprehensive tests for the `schematics_universal` function with different ProjectDir kinds.

## Key Challenges Identified

1. **StorageResolver Dependency**: ProjectDir requires project IDs that must be resolvable via StorageResolver
2. **Dynamic Dockerfile Generation**: DockerBuilder doesn't have a dockerfile attribute; it generates dockerfiles dynamically during `a_build()`
3. **Project Structure Requirements**: Each kind requires specific file structures to be detected properly

## Architecture Analysis

### ProjectDir Kinds and Their Requirements

1. **'source'** - Pure source code, no Python environment
   - No specific files required
   - Should not trigger any Python environment setup

2. **'resource'** - Resource files only
   - No specific files required
   - Mounted as resources, not sources

3. **'auto'** - Auto-detection based on files
   - Detects based on presence of:
     - pyproject.toml → checks for poetry/rye/uv
     - setup.py → setup.py kind
     - requirements.txt → requirements.txt kind
     - README.md only → README kind

4. **'uv'** - UV project management
   - Requires: pyproject.toml (ideally with [tool.uv] section)
   - Components: rust, cargo, uv installation, uv sync

5. **'rye'** - Rye project management
   - Requires: pyproject.toml
   - Components: rye installation, rye sync

6. **'setup.py'** - Traditional Python project
   - Requires: setup.py file
   - Components: pyenv, pip install -e .

7. **'poetry'** - Poetry project (NOT IMPLEMENTED)
   - Would require: pyproject.toml with poetry configuration

### Storage Resolution Strategy

The default storage resolver expects:
- Sources at: `ml_nexus_source_root` (default: /Users/{user}/repos)
- Resources at: `ml_nexus_resource_root` (default: /Users/{user}/resources)

For testing, we need to:
1. Create a test directory structure
2. Override storage_resolver to point to our test directories

## Implementation Plan

### Phase 1: Test Infrastructure Setup

1. Create test directory structure:
   ```
   test/dummy_projects/
   ├── test_uv_project/
   │   └── pyproject.toml
   ├── test_rye_project/
   │   └── pyproject.toml
   ├── test_setuppy_project/
   │   └── setup.py
   ├── test_requirements_project/
   │   └── requirements.txt
   ├── test_source_project/
   │   └── main.py
   └── test_resource_project/
       └── data.json
   ```

2. Create custom storage resolver for tests

### Phase 2: Dummy Project Creation

For each kind, create minimal but valid project files.

### Phase 3: Test Implementation

1. Create iproxy objects for each kind
2. Use `a_build()` to trigger dockerfile generation
3. Find way to capture or log dockerfile content
4. Verify correct components are included for each kind

### Phase 4: Validation

1. Run tests
2. Verify each kind generates appropriate dockerfile
3. Document results

## Current Status

- [x] Identified challenges and requirements
- [x] Analyzed DockerBuilder implementation
- [x] Created test directory structure
- [x] Implemented dummy projects
- [x] Created custom storage resolver
- [x] Implemented test cases
- [ ] Captured dockerfile content
- [x] Validated results (partially - found logger injection issue)

## Key Findings from DockerBuilder Analysis

1. **No dockerfile property**: DockerBuilder doesn't have a `dockerfile` property. The dockerfile is generated dynamically during `a_build()`.
2. **Dockerfile generation flow**:
   - `a_build()` calls `prepare_build_context_with_macro()`
   - The dockerfile is constructed by processing macros
   - It's written to a temporary directory and used immediately for building
3. **Macros contain the instructions**: The `macros` field in DockerBuilder contains the list of dockerfile instructions

## Revised Testing Strategy

Since we can't directly access the dockerfile, we have several options:

1. **Examine macros**: Test by inspecting the `macros` list in DockerBuilder
2. **Mock docker build**: Override `a_build_docker` to capture the generated dockerfile
3. **Test with actual builds**: Create minimal test projects and build actual images
4. **Use build_entrypoint_script**: The scripts are accessible via `builder.scripts`

## Next Steps

1. Create test directory structure with dummy projects
2. Override storage resolver to point to test directories
3. Create tests that examine the macros and scripts in DockerBuilder
4. Optionally mock the docker build to capture dockerfiles

## Notes

- The macros list contains the dockerfile instructions before processing
- The scripts list contains the entrypoint scripts that will be run
- We can validate the correct components are included by examining these lists

## Test Results

### Summary

Successfully created test infrastructure for testing `schematics_universal` with different ProjectDir kinds:

1. **Test Directory Structure**: Created `test/dummy_projects/` with subdirectories for each kind
2. **Dummy Projects Created**:
   - `test_uv/` - Contains pyproject.toml with [tool.uv] section
   - `test_rye/` - Contains pyproject.toml with [tool.rye] section
   - `test_setuppy/` - Contains setup.py file
   - `test_requirements/` - Contains requirements.txt (for auto detection)
   - `test_source/` - Contains only Python source files
   - `test_resource/` - Contains only resource files (JSON, YAML)

3. **Storage Resolver**: Successfully overridden with StaticStorageResolver pointing to test projects
4. **Test Files Created**:
   - `test_schematics_universal_macros.py` - Comprehensive test with macro analysis
   - `test_schematics_simple.py` - Simplified test runner
   - `test_schematics_uv_only.py` - Single UV kind test

### Issue Discovered

During test execution, discovered a logger dependency injection issue:
- Error: `'function' object has no attribute 'warning'`
- The logger is being injected as a function instead of a logger instance
- This occurs in DockerBuilder.__post_init__ at line 59

### Test Results Summary

Successfully tested all implemented ProjectDir kinds with the following results:

| Kind | Status | Macros | Scripts | Mounts | Key Features |
|------|--------|--------|---------|--------|--------------|
| UV | ✓ PASSED | 8 | 13 | 4 | Found 'uv sync' command |
| RYE | ✓ PASSED | 7 | 9 | 4 | Found 'rye sync' command |
| SOURCE | ✓ PASSED | 5 | 0 | 2 | No Python environment (as expected) |
| SETUP.PY (via auto) | ✓ PASSED | 7 | 4 | 5 | Found 'pip install -e .' |
| REQUIREMENTS.TXT (via auto) | ✓ PASSED | 7 | 3 | 5 | Found pip install for requirements.txt |

**Total: 5/5 passed**

### Key Findings

1. **Logger Issue Resolved**: Added `logger=logger` to `__meta_design__` in test/__init__.py
2. **Supported Kinds**: 
   - Direct: `uv`, `rye`, `source`
   - Via auto-detection: `setup.py`, `requirements.txt`
   - Not implemented: `resource`, `poetry`, direct `setup.py`
3. **Component Analysis**:
   - UV projects get the most scripts (13) for comprehensive UV setup
   - Source projects have no scripts (0) as they don't need Python environment
   - All Python projects get appropriate package managers and sync commands

### Test Files Created

1. `test_schematics_working_kinds.py` - Final working test for all implemented kinds
2. `test_schematics_universal_macros.py` - Comprehensive test with @injected_pytest
3. `test_schematics_uv_only.py` - Single UV kind test for debugging
4. `test/__init__.py` - Updated with logger configuration

## Code References

- schematics_universal: src/ml_nexus/schematics_util/universal.py:320
- ProjectDir definition: src/ml_nexus/project_structure.py:12
- StorageResolver: src/ml_nexus/storage_resolver.py
- DockerBuilder: src/ml_nexus/docker/builder/docker_builder.py