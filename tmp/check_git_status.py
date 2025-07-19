#!/usr/bin/env python3
import subprocess
import os

os.chdir("/Users/s22625/repos/ml-nexus")
result = subprocess.run(
    ["git", "status", "--porcelain"], capture_output=True, text=True
)
print("Git status output:")
print(result.stdout)
if result.stderr:
    print("Errors:")
    print(result.stderr)
