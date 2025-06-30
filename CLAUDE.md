# ML-Nexus Project Specific Instructions

This file contains project-specific instructions for the ml-nexus repository.
General instructions and guidelines have been moved to ~/.claude/CLAUDE.md

## Project Context
This is the ml-nexus project repository with Docker, pinjected, and machine learning components.

## Project-Specific Notes
- When working with Docker-related tests in this project, run them one by one as they take time and may timeout if run all at once
- This project uses UV (not Rye or Poetry) for Python dependency management
- Use pinjected framework for dependency injection - see global CLAUDE.md for detailed pinjected usage guide