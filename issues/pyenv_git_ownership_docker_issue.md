# Pyenv Git Ownership Issue in Docker Containers

## Issue Summary

When running tests with `PersistentDockerEnvFromSchematics` using projects that require pyenv (e.g., requirements.txt with auto detection), the pyenv setup fails due to Git ownership issues in the Docker container. This causes the system to fall back to the base Python installation instead of creating isolated virtual environments.

## Problem Description

### Error Messages
```
[2025-06-06 14:37:58] PYENV_ROOT exists but is not a git repository.
Reinitialized existing Git repository in /root/.pyenv/.git/
fatal: detected dubious ownership in repository at '/root/.pyenv'
To add an exception for this directory, call:
    git config --global --add safe.directory /root/.pyenv
[2025-06-06 14:37:58] Failed to initialize pyenv repository
[2025-06-06 14:37:58] Failed to set up pyenv
```

### Root Cause
The issue occurs because:
1. The pyenv directory (`/root/.pyenv`) is mounted or created with different ownership than the container user
2. Git's security features (introduced in Git 2.35.2) prevent operations on repositories owned by different users
3. The `ensure_pyenv_virtualenv.sh` script fails to handle this Git security check

### Impact
- Virtual environments are not created properly
- Python packages get installed to the system Python instead of isolated environments
- Tests may pass with false positives if packages are pre-installed in the base image
- The intended isolation between different Python projects is lost

## Current Behavior

1. Container starts with pyenv directory from cache or previous runs
2. Git detects ownership mismatch when trying to update pyenv
3. Pyenv setup fails
4. Script continues but uses system Python
5. Virtual environment activation fails (directory exists but is empty)
6. Packages install to system Python

## Expected Behavior

1. Pyenv should initialize successfully regardless of directory ownership
2. Virtual environments should be created in the specified paths
3. Python packages should be isolated in project-specific virtual environments
4. No fallback to system Python should occur

## Reproduction Steps

1. Run any test that uses `PersistentDockerEnvFromSchematics` with a requirements.txt project:
```bash
uv run pytest test/test_persistent_docker_env_from_schematics.py::test_python_execution_requirements_auto -xvs
```

2. Observe the Docker container logs during the pyenv setup phase

## Proposed Solutions

### Solution 1: Add Git Safe Directory Configuration
Modify `ensure_pyenv_virtualenv.sh` to add the pyenv directory as a Git safe directory:

```bash
# Add after detecting PYENV_ROOT exists
if [ -d "$PYENV_ROOT/.git" ]; then
    git config --global --add safe.directory "$PYENV_ROOT"
fi
```

### Solution 2: Fix Ownership Before Git Operations
Ensure proper ownership of the pyenv directory:

```bash
# Fix ownership if running as root
if [ "$(id -u)" = "0" ] && [ -d "$PYENV_ROOT" ]; then
    chown -R root:root "$PYENV_ROOT"
fi
```

### Solution 3: Skip Git Operations for Existing Installations
Check if pyenv is already functional before attempting Git operations:

```bash
# Check if pyenv command works
if command -v pyenv >/dev/null 2>&1; then
    log_message "Pyenv already installed and functional"
    # Skip git operations
fi
```

### Solution 4: Use Docker Build-time Installation
Instead of installing pyenv at runtime, include it in the Docker image during build:
- Modify the Docker build process to pre-install pyenv
- Cache the pyenv installation in the image layers
- Avoid runtime Git operations entirely

## Workarounds

### Current Workaround
The system currently falls back to system Python, which works if all required packages are pre-installed in the base image. However, this defeats the purpose of virtual environment isolation.

### Temporary Workaround
Users can manually fix the issue in running containers:
```bash
docker exec <container> git config --global --add safe.directory /root/.pyenv
```

## Related Issues

- Similar issue seen in MLPlatform environments with mounted volumes
- Git 2.35.2+ security updates affecting many Docker-based workflows
- Symlink preservation issue (already fixed) was preventing proper NFS usage

## Test Results

Despite the pyenv failure, tests are passing because:
- Base images often have Python pre-installed
- System-wide pip installations succeed
- Import statements work with system packages

Example from test run:
```
[415fb7b1a0b8]    Requirement already satisfied: requests==2.31.0 in /usr/local/lib/python3.11/site-packages (2.31.0)
```

## Priority

**Medium-High**: While tests are passing, the lack of proper virtual environment isolation could lead to:
- Dependency conflicts between projects
- Inconsistent test results
- Hidden bugs that only appear in production
- Violation of Python best practices

## Action Items

1. [ ] Implement Git safe directory fix in `ensure_pyenv_virtualenv.sh`
2. [ ] Add proper error handling for Git ownership issues
3. [ ] Consider pre-installing pyenv in Docker base images
4. [ ] Add tests specifically for virtual environment isolation
5. [ ] Document the expected behavior and requirements
6. [ ] Consider using alternative Python version managers (e.g., uv, mise) that don't rely on Git

## Additional Notes

- This issue affects all auto-detected projects that fall back to pyenv (requirements.txt, setup.py)
- UV and Rye projects are not affected as they use their own Python management
- The issue is more prominent in persistent containers that reuse cached directories
- The problem may not appear in fresh containers without cached pyenv directories