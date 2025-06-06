"""Test that docker context is loaded from environment variable"""

import os
import sys
from pathlib import Path

# Set environment variable before importing
os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"] = "env-test-context"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ml_nexus import load_env_design

print("Testing docker context loading from environment...")

# Get the design
design = load_env_design()

# Convert to graph and check the context value
graph = design.to_graph()

# Get the context value
context = graph.get('ml_nexus_docker_build_context')

print(f"Environment variable ML_NEXUS_DOCKER_BUILD_CONTEXT: {os.environ.get('ML_NEXUS_DOCKER_BUILD_CONTEXT')}")
print(f"Loaded context value: {context}")

# Verify it matches
assert context == "env-test-context", f"Expected 'env-test-context', got {context}"

print("✅ Docker context is correctly loaded from environment variable!")

# Clean up
del os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"]