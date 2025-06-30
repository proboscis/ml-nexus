- When implementing a program, always add items before the end of TODO list to run unit tests and verify the implementation works.

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

# Author Update
Use Kento Masui instead of S22625 for username/presentation author

# Pinjected Framework Usage Guide

## Key Concepts and Patterns

### Understanding IProxy: Lazy AST Construction
**Important**: IProxy does NOT execute functions or wrap computed values. Instead, when you call an @injected function with IProxy arguments, it constructs a lazy Abstract Syntax Tree (AST) that represents the computation graph. The actual execution happens later when the graph is evaluated by the pinjected runtime.

```python
# This does NOT execute a_create_merged_cloth_dataset immediately
# It builds an AST representing this computation
merged_result: IProxy[MergedDatasetResult] = a_create_merged_cloth_dataset(dataset_proxy)

# This extends the AST with attribute access
merged_dataset: IProxy[TypedDataset[SegSample]] = merged_result.dataset

# Actual execution happens when you run:
# uv run pinjected run module.path.merged_dataset
```

### 1. IProxy Attribute Access
IProxy objects support direct attribute access using dot notation. You do NOT need to use `.map()` for accessing attributes.

```python
# CORRECT - Direct attribute access
merged_result: IProxy[MergedDatasetResult] = a_create_merged_cloth_dataset(...)
merged_dataset: IProxy[TypedDataset[SegSample]] = merged_result.dataset
label_mapping: IProxy[dict[int, str]] = merged_result.label_mapping

# INCORRECT - Don't use map for attribute access
merged_dataset = merged_result.map(lambda r: r.dataset)  # Don't do this!
```

### 2. IProxy vs @injected Functions
Functions decorated with `@injected` should NOT accept or use IProxy objects directly. IProxy is for composing operations outside of injected functions.

```python
# INCORRECT - Don't pass IProxy to @injected functions
@injected
async def a_process_data(data: IProxy[Dataset]) -> Result:  # Wrong!
    result = await data.some_method()  # This won't work
    return result

# CORRECT - @injected functions work with concrete types
@injected
async def a_process_data(data: Dataset) -> Result:
    result = data.some_method()  # Direct usage
    return result

# CORRECT - Use IProxy for building computation graphs
dataset_proxy: IProxy[Dataset] = load_dataset()
# This creates an AST node, NOT executing a_process_data
result_proxy: IProxy[Result] = a_process_data(dataset_proxy)  # AST construction
```

### 3. Creating Test Entrypoints
Test entrypoints should be created as module-level IProxy instances. These are lazy AST definitions that get evaluated when run with pinjected.

```python
# Create test instances - these are AST nodes, not executed values
test_subset_size = 100

# This builds an AST for selecting a subset, NOT executing the selection
test_dataset: IProxy[TypedDataset[SegSample]] = ucld_dataset.select(
    range(0, test_subset_size)
)

# This builds a complex AST with multiple operations
test_merged_result: IProxy[MergedDatasetResult] = a_create_merged_cloth_dataset(
    dataset=test_dataset,
    label_mapping=label_mapping_artifact
)

# Extends the AST with attribute access
test_merged_dataset: IProxy[TypedDataset[SegSample]] = test_merged_result.dataset

# Builds visualization AST that will show result when evaluated
test_visualize: IProxy = a_visualize_merged_cloth_dataset(
    original_dataset=test_dataset,
    merged_result=test_merged_result,
    sample_index=5
).show()  # .show() is also part of the AST

# The entire AST gets evaluated when you run:
# uv run pinjected run module.path.test_visualize
```

### 4. Common IProxy Patterns

#### Chaining Operations
```python
# Chain multiple operations to build a complex AST
# Each method call adds a node to the computation graph
processed_dataset: IProxy[Dataset] = (
    raw_dataset
    .rename_column("old_name", "new_name")  # AST node 1
    .select_columns(["col1", "col2"])       # AST node 2
    .filter(lambda x: x.value > 0)          # AST node 3
    .select(range(0, 100))                  # AST node 4
)
# No actual data processing happens until evaluation
```

#### Async Function Composition
```python
# Compose async functions - builds AST nodes for async operations
bbox_dataset: IProxy[SegHeadDataset] = a_add_detected_head_bbox(
    dataset=merged_dataset,
    head_detector=head_detector_component
)
# No async execution yet - just AST construction

# Chain another async operation in the AST
pairs: IProxy[list[SegHeadSamplePair]] = a_get_pairs_with_detections(
    dataset=bbox_dataset,
    original_dataset=original_dataset
)
# The async functions will be awaited during AST evaluation
```

### 5. Running Pinjected Commands

```bash
# Evaluate the AST defined by test_visualize
uv run pinjected run sge_hub.datasets.merged_cloth_dataset.test_visualize

# List available IProxy AST definitions in a module
uv run pinjected list sge_hub.datasets.merged_cloth_dataset

# Describe an AST target without evaluating it
uv run pinjected describe sge_hub.datasets.merged_cloth_dataset.test_dataset
```

### 6. Common Mistakes to Avoid

```python
# DON'T: Wrap injected functions with IProxy()
result = IProxy(a_process_data)(dataset)  # Wrong!

# DO: Call directly - this builds AST, not executes
result = a_process_data(dataset)  # Builds AST node

# DON'T: Use IProxy inside @injected functions
@injected
async def a_process(data: Dataset) -> Result:
    proxy = IProxy(data)  # Wrong! Don't create IProxy inside
    return proxy.transform()

# DO: Work with concrete types inside @injected
@injected  
async def a_process(data: Dataset) -> Result:
    return data.transform()  # Direct usage

# DON'T: Pass config dicts to functions expecting individual params
a_visualize_mask_distribution(dataset, config={"num_samples": 10})  # Wrong!

# DO: Pass parameters directly
a_visualize_mask_distribution(dataset, num_samples=10)  # Correct
```

# Tests
Unless instructed, do not try to make a test script.
Instead, make IProxy entrypoints for testing.
Such IProxy objects are to be run with `uv run pinjected run <module.path.variable.name>`.

# Using TODOs
Use TODOs when instructed to perform any refactoring or code changes.
Unless only running a single command, use TODOs.
Always add a TODO to run `uvx ruff check <modified_file>`.
Always add a TODO to run `uv run python -m pinjected list <full.module.path>`. To validate IProxy definitions.

# Using Logger
Never use print statements for logging.
Use loguru.logger for logging.
If inside @injected function, use logger from the dependency.
```python
from loguru import logger
logger.info("This is an info message")
with logger.contextualize(tag='some_tag'):
    logger.info("This is a contextualized info message")
# pinjected 
@injected
async def some_function(logger,/,arg):
    logger.info("This is an info message")
```

# Logging with context
Try logging with context when possible and some long procedure is expected.
```python
with logger.contextualize(tag='some_tag'):
    logger.info("This is a contextualized info message")
```

# No Falling Back
Unless instructed by the user, never implement a logic to fall back to a previous version of the code.
Do not implement `last resort` logic. just let it fail and let the user handle it.

# Raise Error instead of logging
When the code reaches to a state where its behavior was not provided by the user, raise an error instead of logging and ignoring it.

# Running python
use `uv run python <file>` instead of `python <file>`.

# Fixing Linter Issues
When asked to fix linter issues, Gemini should:
- Never bypass linter rules with --no-verify
- Fix the code following the linter rules
- Do not ever ignore linter issue unless instructed to do so
This applies to the case where a commit failed due to linter issues.

# Coding Style:
- Respect SOLID principles.
- Respect linter rules for complexity and readability analysis. THIS IS CRITICAL.

- tests around docker takes a minute so running them all at once will timeout in your shell. run each docker related test one by one in such case
