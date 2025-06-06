# Test Suite Conversion Plan: to_pytest → @injected_pytest

## Overview
This plan outlines the systematic conversion of remaining test files from old IProxy patterns to the standardized `@injected_pytest` decorator pattern.

## Files Requiring Conversion

### Priority 1: Files with `to_pytest` Pattern (High Impact)
These files use the deprecated `to_pytest()` conversion utility and need to be migrated to `@injected_pytest`.

#### 1. test_best_practice_example.py
- **Current**: Uses `to_pytest(IProxy)` pattern
- **Tests**: 3 test functions
- **Actions**:
  1. Remove `from test.iproxy_test_utils import to_pytest`
  2. Import `from pinjected.test import injected_pytest`
  3. Convert each test from `@injected` to `@injected_pytest(test_design)`
  4. Remove IProxy creation and to_pytest conversion lines
  5. Update docstring to reflect new pattern

#### 2. test_iproxy_example.py
- **Current**: Uses `to_pytest(IProxy)` pattern
- **Tests**: 2 test functions
- **Actions**:
  1. Remove `from test.iproxy_test_utils import to_pytest`
  2. Import `from pinjected.test import injected_pytest`
  3. Convert test functions to use `@injected_pytest(test_design)`
  4. Remove IProxy variable assignments

### Priority 2: Files with Raw IProxy Objects (Medium Impact)
These files have module-level IProxy objects that rely on plugin discovery.

#### 3. test_iproxy_plugin_demo.py
- **Current**: Module-level IProxy objects without conversion
- **Tests**: 3 test objects
- **Actions**:
  1. Import `from pinjected.test import injected_pytest`
  2. Convert IProxy object definitions to proper test functions
  3. Add `@injected_pytest` decorator to each test
  4. Remove module-level IProxy assignments

#### 4. test_schematics_simple.py
- **Current**: 5 module-level IProxy test objects
- **Tests**: test_working, test_working_uv, test_working_rye, test_working_setuppy, test_working_requirements
- **Actions**:
  1. Import `from pinjected.test import injected_pytest`
  2. Convert each IProxy assignment to a proper test function
  3. Add test design configuration if missing
  4. Apply `@injected_pytest` decorator

#### 5. test_schematics_working_kinds.py
- **Current**: 1 module-level IProxy test object
- **Tests**: test_working
- **Actions**:
  1. Import `from pinjected.test import injected_pytest`
  2. Convert IProxy to proper test function
  3. Apply decorator pattern

### Priority 3: Special Cases (Low Impact)
These files have unique patterns or issues.

#### 6. test_schematics_pytest_compatible.py
- **Current**: Uses `as_pytest_test` and `convert_module_iproxy_tests`
- **Issue**: Missing design import causing NameError
- **Actions**:
  1. Fix missing imports
  2. Convert to standard `@injected_pytest` pattern
  3. Remove conversion utilities

#### 7. test_schematics_universal_kinds_runner.py
- **Current**: Runner script with IProxy objects
- **Note**: May not be actual tests - investigate purpose
- **Actions**:
  1. Determine if these are meant to be tests or utilities
  2. If tests, convert to `@injected_pytest`
  3. If utilities, move to appropriate location

### Priority 4: Mixed Pattern Files
#### 8. test_schematics_uv_only.py
- **Current**: Has `@injected_pytest` but also 1 residual IProxy object
- **Actions**:
  1. Remove the module-level IProxy object
  2. Ensure all tests use consistent pattern

## Conversion Pattern Reference

### Before (Old Pattern):
```python
from test.iproxy_test_utils import to_pytest
from pinjected import IProxy, injected

@injected
async def a_test_something(dependency):
    # test logic
    return True

test_something_iproxy: IProxy = a_test_something(dependency)
test_something = to_pytest(test_something_iproxy)
```

### After (New Pattern):
```python
from pinjected.test import injected_pytest
from pinjected import design

test_design = design(
    # test-specific bindings
)

@injected_pytest(test_design)
async def test_something(dependency):
    # test logic
    # No return needed, use assertions
```

## Execution Steps

1. **Backup**: Create git commit before starting conversions
2. **Convert Priority 1**: Files with `to_pytest` pattern (most straightforward)
3. **Convert Priority 2**: Files with raw IProxy objects
4. **Handle Special Cases**: Fix import errors and mixed patterns
5. **Validate**: Run pytest on each converted file
6. **Cleanup**: Remove any unused imports or utility files
7. **Final Test**: Run full test suite

## Success Criteria

- All test files use consistent `@injected_pytest` pattern
- No module-level IProxy objects remain
- No `to_pytest` imports or usage
- All tests pass when run with pytest
- No wrapper loop errors during test collection

## Risks and Mitigations

1. **Risk**: Tests may behave differently after conversion
   - **Mitigation**: Test each file individually after conversion
   
2. **Risk**: Dependencies may not resolve correctly
   - **Mitigation**: Ensure proper test_design configuration for each file

3. **Risk**: Some IProxy objects may be used for non-test purposes
   - **Mitigation**: Investigate each case before conversion