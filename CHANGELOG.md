# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
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

### Added
- `test/PINJECTED_USAGE_ANALYSIS.md` - Comprehensive analysis of Pinjected usage issues across test files
- `test/PINJECTED_MIGRATION_PLAN.md` - Systematic migration plan for converting tests to best practices

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