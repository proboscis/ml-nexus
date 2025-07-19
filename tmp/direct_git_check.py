import subprocess
import sys
import os

# Change to the git repo directory
os.chdir("/Users/s22625/repos/ml-nexus")

# Run git status
try:
    result = subprocess.run(
        ["git", "status"], capture_output=True, text=True, check=True
    )
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"Error running git status: {e}")
    print(f"stderr: {e.stderr}")
    sys.exit(1)
