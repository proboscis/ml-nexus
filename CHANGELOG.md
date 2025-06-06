# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Fixed critical symlink destruction issue in `ensure_pyenv_virtualenv.sh`
  - Script was destroying symlinks created by MLPlatform, causing virtualenvs to be stored on limited job volume
  - Added symlink detection and preservation logic to create virtualenvs at symlink targets
  - Changed from `readlink -f` to `readlink` to avoid resolving all symlinks in path
  - Ensures MLPlatform mount validation passes and virtualenvs are stored on NFS volumes
  - Preserves existing behavior for non-symlink directories (backward compatible)
- Fixed `PersistentDockerEnvFromSchematics` to properly use `ml_nexus_docker_build_context`
  - Added `_ml_nexus_docker_build_context` as injected dependency
  - All Docker operations (exec, stop, cp, rsync) now respect the configured Docker context
  - Updated `a_docker_ps` function to support Docker context for consistency
  - Ensures persistent containers work correctly with different Docker endpoints (e.g., zeus, colima)

### Added
- `doc/storage_resolver_architecture.md` - Comprehensive documentation for StorageResolver system
  - Architecture diagrams and class hierarchy using Mermaid
  - Design philosophy and implementation details
  - Integration patterns with Docker environments and dependency injection
  - Best practices and troubleshooting guide
  - Examples using actual patterns from the codebase and configuration files
- `test/PYTEST_CONVERSION_PLAN.md` - Test conversion planning documentation
- `doc/schematics_universal_philosophy_and_usage.md` - Comprehensive documentation for schematics_universal
  - Philosophy behind unified interface for Docker container configurations
  - Architecture overview with component system and project types
  - Usage patterns and examples for different Python project structures
  - Integration with pinjected framework using IProxy
  - Best practices for creating custom components
- Docker context support for all Docker operations
  - Added `ml_nexus_docker_build_context` configuration to specify Docker daemon context
  - Supports named contexts like 'zeus', 'default', 'colima' for different Docker environments
  - Environment variable `ML_NEXUS_DOCKER_BUILD_CONTEXT` for global configuration

### Changed
- Updated Pinjected usage to follow latest best practices (v0.2.115+)
  - Replaced deprecated `__meta_design__` with `__design__` throughout codebase
  - Removed `overrides=` pattern in favor of direct design assignment
  - Updated all async `@injected` functions to use `a_` prefix convention
  - Fixed logger injection to be passed as dependency parameter instead of global import
  - Added proper import statements for all pinjected decorators
  - Clarified distinction between `__pinjected__.py` (module config) and `.pinjected.py` (user config)
- Updated `doc/how_to_use_pinjected.md` with latest framework patterns
  - Marked `__meta_design__` as deprecated
  - Updated examples to show proper `__design__` usage
  - Fixed async function naming conventions
  - Updated test examples to use `@injected_pytest` decorator
- Refactored test suite to use `@injected_pytest` decorator for Pinjected tests
  - Migrated 9 test files from custom `to_pytest` pattern to recommended `@injected_pytest`
  - Removed return statements from test functions, replaced with proper assertions
  - Fixed wildcard imports to use explicit imports
  - Added proper test design configurations for each test module
  - Maintained backward compatibility with IProxy definitions for direct execution
- Improved test maintainability and compliance with Pinjected framework best practices
- Updated all test files to use 'zeus' Docker host exclusively
  - Changed all `docker_host="localhost"` and `docker_host='local'` to `docker_host="zeus"`
  - Added `ml_nexus_docker_build_context="zeus"` to test design configurations
  - Ensures tests work correctly with the required Docker infrastructure
- Fixed test assertions to use `PsResult.stdout` attribute correctly
  - Updated all test files that were asserting against the PsResult object directly
  - Changed assertions from `assert "text" in result` to `assert "text" in result.stdout`
  - Ensures proper handling of script execution results in tests
- Enhanced Docker client implementation to support context configuration
  - Updated `LocalDockerClient` to accept `_ml_nexus_docker_build_context` as injected dependency
  - All Docker commands now properly use `--context` flag when context is specified
  - Modified Docker build functions (`a_build_docker`, `build_image_with_copy`, `build_image_with_rsync`)
  - Updated `a_docker_push__local` to use Docker context for push operations
  - Added constructor injections for `LocalDockerClient` and `RemoteDockerClient`
  - Removed Optional type for injected dependencies following pinjected conventions

### Fixed
- Docker operations now consistently use the configured Docker context
  - Fixed issue where only build commands were using context, not other operations
  - Ensured push, exec, run, and other Docker commands respect the context setting
  - Added comprehensive test coverage for Docker context usage

### Deprecated
- `__meta_design__` - Use `__design__` instead in `__pinjected__.py` files
- `design(overrides=...)` pattern - Use direct `design(key=value)` assignment

### Documentation
- Created StorageResolver architecture documentation with comprehensive examples
- Updated Pinjected usage guide to reflect current best practices
- Added test conversion planning documents

### Internal
- `test/PINJECTED_USAGE_ANALYSIS.md` - Comprehensive analysis of Pinjected usage issues across test files
- `test/PINJECTED_MIGRATION_PLAN.md` - Systematic migration plan for converting tests to best practices
- `test/test_auto_pyvenv_docker_env.py` - Test suite for auto-detection of pyvenv projects
  - Verifies that projects with `kind='auto'` correctly use pyvenv setup
  - Tests auto-detection for both `requirements.txt` and `setup.py` projects
  - Confirms pyenv installation is included in Docker build macros
  - Validates that pyvenv setup differs from direct UV/Rye configurations

### Removed
- `test/test_all_schematics_kinds.py` - Redundant test file that duplicated functionality
  - Used deprecated IProxy patterns at module level
  - Functionality is already covered by `test_schematics_universal_macros.py`
  - Removal improves test suite maintainability

## [0.0.8]

### Added
- Docker context support for building images on different Docker endpoints (e.g., zeus, colima)
  - New `ml_nexus_docker_build_context` configuration parameter
  - Configurable via environment variable `ML_NEXUS_DOCKER_BUILD_CONTEXT`
  - Can be overridden in project design configuration
- SSH-based remote Docker build function `a_build_docker_ssh_remote` for backward compatibility
- Comprehensive documentation for DockerHostEnv workflow in `doc/docker_host_env_workflow.md`
  - Architecture diagrams and workflow sequences
  - Building, syncing, and running process explanations
  - Docker context configuration examples

### Changed
- Updated `a_build_docker` and `a_build_docker_no_buildkit` to support Docker contexts
  - When context is specified, uses `docker --context <name>` format
  - Maintains backward compatibility when no context is specified

### Documentation
- Created detailed workflow documentation explaining:
  - How Docker host is set during `DockerHostEnv.run_script()`
  - Building process with macro system
  - Syncing process using rsync
  - Volume mounting strategy
  - Performance optimizations