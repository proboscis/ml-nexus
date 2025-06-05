# Running IProxy Tests with Pytest

This guide explains how to write and run IProxy test objects with pytest in the ml-nexus project.

## Background

IProxy objects are pinjected dependency injection proxies that cannot be executed directly by pytest. They need to be converted to regular Python functions that pytest can discover and run.

## Quick Start

### Method 1: Simple Conversion (Recommended)

1. **Import the conversion utility:**
```python
from test.iproxy_test_utils import to_pytest
```

2. **Write your test as an injected function:**
```python
@injected
async def a_test_something(dependency1, dependency2):
    """Your test logic here"""
    result = await dependency1.do_something()
    assert result is not None
    return True
```

3. **Create IProxy and convert to pytest:**
```python
# Create IProxy object
test_something_iproxy: IProxy = a_test_something(dependency1, dependency2)

# Convert to pytest function
test_something = to_pytest(test_something_iproxy)
```

4. **Run with pytest normally:**
```bash
pytest test_your_file.py -v
```

### Method 2: Batch Conversion

For files with many IProxy tests, you can convert them all at once:

```bash
# List IProxy tests in a file
python test/convert_iproxy_tests.py test_all_schematics_kinds.py --list

# Convert to pytest-compatible module
python test/convert_iproxy_tests.py test_all_schematics_kinds.py -o test_all_schematics_pytest.py

# Run the converted tests
pytest test_all_schematics_pytest.py -v
```

## Complete Example

Here's a complete example from `test/test_iproxy_example.py`:

```python
from pathlib import Path
from pinjected import IProxy, injected, design
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
from test.iproxy_test_utils import to_pytest

# Setup test environment
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
})

__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)

# Define test as injected function
@injected
async def a_test_uv_project(schematics_universal, logger):
    """Test UV project configuration"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Verify UV configuration
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'uv sync' in scripts_str, "UV sync command not found"
    
    logger.info("✅ UV project test passed")
    return True

# Create IProxy and convert to pytest
test_uv_project_iproxy: IProxy = a_test_uv_project(schematics_universal, logger)
test_uv_project = to_pytest(test_uv_project_iproxy)
```

## Running IProxy Tests Directly

If you want to run IProxy tests without pytest conversion, use pinjected's run command:

```bash
# Run a single IProxy test
uv run python -m pinjected run test.test_schematics_working_kinds.test_working
```

## Design Configuration

When writing IProxy tests, ensure your module has proper design configuration:

```python
__meta_design__ = design(
    overrides=load_env_design + design(
        # Add any custom bindings needed for tests
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)
```

## Best Practices

1. **Name Convention**: Keep the IProxy object with `_iproxy` suffix and the pytest function without it:
   ```python
   test_something_iproxy: IProxy = ...  # IProxy object
   test_something = to_pytest(test_something_iproxy)  # Pytest function
   ```

2. **Return Values**: Tests can return values, but pytest will warn about non-None returns. Use assertions instead of returns for test validation.

3. **Async Tests**: The conversion handles both sync and async tests automatically.

4. **Dependencies**: Declare all dependencies as parameters in your injected function. They will be resolved automatically.

## Troubleshooting

### Import Errors
If you get import errors, ensure:
- The test directory is in your Python path
- You're running from the project root
- Dependencies are properly installed

### Dependency Resolution Errors
If tests fail with dependency injection errors:
- Check your `__meta_design__` configuration
- Ensure all required dependencies are bound
- Verify the dependency names match exactly

### Test Discovery Issues
If pytest doesn't find your tests:
- Ensure test functions start with `test_`
- Check that the conversion is happening (the `to_pytest` call)
- Verify the file name starts with `test_` or ends with `_test.py`

## Advanced Usage

### Custom Design per Test
```python
# Create custom design for specific test
custom_design = design(
    overrides=load_env_design + design(
        special_config="test_value"
    )
)

test_special = to_pytest(test_special_iproxy, module_design=custom_design)
```

### Plugin Approach (Automatic Discovery)
The pytest plugin in `test/pytest_iproxy_plugin.py` automatically discovers and converts IProxy tests. When enabled, you don't need any manual conversion!

#### How to Enable the Plugin

1. **In conftest.py** (recommended for project-wide use):
```python
# test/conftest.py
pytest_plugins = ['test.pytest_iproxy_plugin']
```

2. **Command line** (for one-time use):
```bash
pytest -p test.pytest_iproxy_plugin test_file.py
```

#### How It Works

The plugin:
- Replaces pytest's default module collector with an IProxy-aware version
- Automatically finds all `test_*` IProxy objects in test modules
- Converts them to pytest functions using pinjected's `_to_pytest`
- Marks converted tests with `pytest.mark.iproxy`
- Reports "IProxy plugin: enabled" in the test header

#### Example with Plugin

```python
# No imports needed for conversion!
from pinjected import IProxy, injected, design
from loguru import logger

__meta_design__ = design(logger=logger)

@injected
async def test_something(logger):
    logger.info("This test runs automatically!")
    assert True

# Just create the IProxy - no conversion needed!
test_my_test: IProxy = test_something(logger)
```

**Choice**: Use the plugin for automatic discovery or `to_pytest()` for explicit control.

## Summary

Converting IProxy tests to pytest is straightforward:
1. Write injected test functions
2. Create IProxy objects
3. Convert with `to_pytest()`
4. Run with pytest normally

This approach maintains the benefits of dependency injection while integrating seamlessly with pytest's test discovery and reporting.