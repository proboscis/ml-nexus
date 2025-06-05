# Pinjected Usage Analysis - Test Files

## Summary Table

| File | Uses @injected_pytest | IProxy Type Annotations | Returns Values | Import Issues | Naming Issues | Priority |
|------|----------------------|------------------------|----------------|---------------|---------------|----------|
| test_schematics_for_uv_with_accelerator.py | ❌ (to_pytest) | ✅ | ✅ (Returns True) | ❌ (wildcard) | ✅ | HIGH |
| test_best_practice_example.py | ❌ (IProxy only) | ✅ | ❌ (No tests) | ✅ | ⚠️ (demo file) | LOW |
| test_docker_build_context_verification.py | ❌ (to_pytest) | ✅ | ✅ (Returns True) | ✅ | ✅ | HIGH |
| test_docker_context_simple.py | ✅ | ✅ | ✅ (Returns string) | ✅ | ✅ | MEDIUM |
| test_docker_env_host_with_schematics.py | ❌ (to_pytest) | ✅ | ✅ (Returns dict) | ✅ | ✅ | HIGH |
| test_docker_env_zeus_context.py | ✅ | ✅ | ❌ | ✅ | ✅ | LOW |
| test_plugin_example.py | ❌ (to_pytest) | ✅ | ✅ (Returns dict) | ✅ | ✅ | HIGH |
| test_schematics_docker_run.py | ❌ (to_pytest) | ✅ | ✅ (Returns True) | ✅ | ✅ | HIGH |
| test_schematics_dockerfile_preview.py | ❌ (IProxy only) | ✅ | ❌ (No returns) | ❌ (wildcard) | ⚠️ (not test_) | MEDIUM |
| test_schematics_universal_kinds_runner.py | ❌ (IProxy only) | ✅ | ❌ (No returns) | ❌ (wildcard) | ⚠️ (runner) | LOW |
| test_schematics_universal_macros.py | ❌ (to_pytest) | ✅ | ✅ (Returns list) | ✅ | ✅ | HIGH |
| test_schematics_uv_only.py | ❌ (to_pytest) | ✅ | ✅ (Returns dict) | ❌ (wildcard) | ✅ | HIGH |
| test_zeus_demo.py | ❌ (IProxy only) | ✅ | ❌ (Demo) | ✅ | ⚠️ (demo file) | LOW |

## Detailed Issues by File

### 1. test_schematics_for_uv_with_accelerator.py
```python
# Issues:
- Uses custom to_pytest instead of @injected_pytest
- Returns True from test functions
- Uses wildcard import: from pinjected import *
- Has custom to_pytest implementation

# Current pattern:
test_run_schematics_uv_accelerator = to_pytest(test_run_schematics_uv_accelerator_iproxy)
```

### 2. test_docker_build_context_verification.py
```python
# Issues:
- Uses to_pytest conversion
- Returns True from test functions
- Test functions use assertions but also return values

# Pattern:
test_verify_build_context = to_pytest(test_verify_iproxy)
```

### 3. test_docker_context_simple.py
```python
# Good:
- Uses @injected_pytest correctly

# Issues:
- Returns string from test function
- Should only use assertions
```

### 4. test_docker_env_host_with_schematics.py
```python
# Issues:
- Uses to_pytest conversion
- Returns dict from test functions
- Complex return values instead of assertions
```

### 5. test_docker_env_zeus_context.py
```python
# BEST PRACTICE EXAMPLE ✅
- Uses @injected_pytest decorator
- No return values from tests
- Proper imports
- Good naming conventions
```

### 6. test_schematics_docker_run.py
```python
# Issues:
- Uses to_pytest conversion
- Returns True from test functions
- Should migrate to @injected_pytest
```

### 7. test_schematics_dockerfile_preview.py
```python
# Issues:
- Uses wildcard import
- No test conversion (IProxy only)
- Functions don't follow test_ naming convention
- Appears to be more of a utility than test file
```

### 8. test_schematics_universal_macros.py
```python
# Issues:
- Uses to_pytest conversion
- Returns list from test function
- Complex logic in test functions
```

### 9. test_schematics_uv_only.py
```python
# Issues:
- Uses to_pytest conversion
- Uses wildcard import
- Returns dict from test function
```

## Common Patterns Found

### 1. Custom to_pytest Pattern (Most Common)
```python
from test.iproxy_test_utils import to_pytest

@injected
async def a_test_something(...):
    # test logic
    return True  # Should not return

test_something_iproxy: IProxy = a_test_something(...)
test_something = to_pytest(test_something_iproxy)
```

### 2. IProxy Only Pattern
```python
run_preview: IProxy = preview_schematics_dockerfile(...)
# No pytest conversion
```

### 3. @injected_pytest Pattern (Recommended)
```python
@injected_pytest(test_design)
async def test_something(...):
    # test logic with assertions only
    # No return statement
```

## Migration Priority

### HIGH Priority (7 files)
Files using to_pytest that should migrate to @injected_pytest:
- test_schematics_for_uv_with_accelerator.py
- test_docker_build_context_verification.py
- test_docker_env_host_with_schematics.py
- test_plugin_example.py
- test_schematics_docker_run.py
- test_schematics_universal_macros.py
- test_schematics_uv_only.py

### MEDIUM Priority (2 files)
Files needing import fixes and minor adjustments:
- test_docker_context_simple.py (remove return values)
- test_schematics_dockerfile_preview.py (fix imports, add test conversion)

### LOW Priority (4 files)
Demo/runner files that may not need full test conversion:
- test_best_practice_example.py
- test_docker_env_zeus_context.py (already follows best practices)
- test_schematics_universal_kinds_runner.py
- test_zeus_demo.py