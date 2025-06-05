# Pinjected Test Migration Plan

## Overview
This plan outlines the systematic migration of test files from custom `to_pytest` patterns to the recommended `@injected_pytest` decorator, along with fixing other Pinjected usage issues.

## Phase 1: HIGH Priority Files (7 files)
These files use `to_pytest` conversion and need full migration.

### 1.1 test_schematics_for_uv_with_accelerator.py
**Tasks:**
- [ ] Replace wildcard import with explicit imports
- [ ] Remove custom `to_pytest` function definition
- [ ] Convert `@injected` test functions to `@injected_pytest`
- [ ] Remove return statements from test functions
- [ ] Add proper test design configuration

### 1.2 test_docker_build_context_verification.py
**Tasks:**
- [ ] Import `injected_pytest` from `pinjected.test`
- [ ] Convert `a_test_verify_build_context` to use `@injected_pytest`
- [ ] Remove `return True` statements
- [ ] Remove `to_pytest` conversion

### 1.3 test_docker_env_host_with_schematics.py
**Tasks:**
- [ ] Convert all test functions to `@injected_pytest`
- [ ] Change return dict statements to assertions
- [ ] Remove `to_pytest` imports and conversions

### 1.4 test_plugin_example.py
**Tasks:**
- [ ] Migrate `a_test_plugin` to `@injected_pytest`
- [ ] Convert dict return to assertions
- [ ] Clean up IProxy conversions

### 1.5 test_schematics_docker_run.py
**Tasks:**
- [ ] Convert `a_test_docker_run` to `@injected_pytest`
- [ ] Remove return True statements
- [ ] Add proper assertions

### 1.6 test_schematics_universal_macros.py
**Tasks:**
- [ ] Convert `a_test_verify_macros` to `@injected_pytest`
- [ ] Replace list return with assertions
- [ ] Simplify test logic

### 1.7 test_schematics_uv_only.py
**Tasks:**
- [ ] Fix wildcard import
- [ ] Convert to `@injected_pytest`
- [ ] Replace dict return with assertions

## Phase 2: MEDIUM Priority Files (2 files)

### 2.1 test_docker_context_simple.py
**Tasks:**
- [ ] Remove return statement from `test_docker_context_is_zeus`
- [ ] Keep `@injected_pytest` (already correct)

### 2.2 test_schematics_dockerfile_preview.py
**Tasks:**
- [ ] Fix wildcard import
- [ ] Add `@injected_pytest` decorator to functions
- [ ] Rename functions to follow `test_` convention

## Phase 3: LOW Priority Files (4 files)
These are demo/runner files that may need different treatment.

### 3.1 test_best_practice_example.py
- Consider moving to examples/ directory

### 3.2 test_schematics_universal_kinds_runner.py
- Consider moving to examples/ or scripts/ directory

### 3.3 test_zeus_demo.py
- Consider moving to examples/ directory

### 3.4 test_docker_env_zeus_context.py
- Already follows best practices - use as reference

## Common Migration Pattern

### Before:
```python
from pinjected import *  # or from pinjected import injected, IProxy, design
from test.iproxy_test_utils import to_pytest

@injected
async def a_test_something(dependency1, dependency2):
    # test logic
    assert something
    return True  # or return dict/list

test_something_iproxy: IProxy = a_test_something(dependency1, dependency2)
test_something = to_pytest(test_something_iproxy)
```

### After:
```python
from pinjected import design
from pinjected.test import injected_pytest

test_design = design(
    # test-specific overrides if needed
)

@injected_pytest(test_design)
async def test_something(dependency1, dependency2):
    # test logic
    assert something
    # No return statement

# No IProxy conversion needed
```

## Implementation Steps

1. **Create TODO tracker**
   - Use TODO tool to track migration progress
   - Process files in priority order

2. **For each file:**
   - Read current implementation
   - Apply migration pattern
   - Fix imports
   - Remove returns
   - Run ruff check
   - Validate with pinjected list

3. **Testing:**
   - Run individual tests with pytest
   - Ensure all assertions pass
   - Verify no return values

4. **Documentation:**
   - Update test documentation
   - Add migration notes

## Success Criteria

- All HIGH priority files use `@injected_pytest`
- No test functions return values
- All imports are explicit (no wildcards)
- All tests pass with pytest
- Code passes ruff linting