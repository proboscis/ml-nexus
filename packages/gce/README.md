# ml-nexus-gce

GCE support for ml-nexus with Vertex AI Custom Job.

Quick start:

- Add as workspace dependency; run:
  - uv sync --all-packages

Usage sketch:

```python
from pathlib import Path
from ml_nexus_gce import VertexAICustomJobFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import ContainerSchematic
from google.oauth2 import service_account

def gcp_credentials_from_json() -> "Credentials|None":
    path = Path("path/to/sa.json")
    if path.exists():
        return service_account.Credentials.from_service_account_file(str(path))
    return None  # falls back to ADC if None

project = ProjectDef(dirs=[ProjectDir(id="example")])
schem = ContainerSchematic()
runner = VertexAICustomJobFromSchematics(
    _macro_install_base64_runner=...,   # inject from ml_nexus macros
    _a_docker_push=...,                 # inject docker push callable
    project=project,
    schematics=schem,
    machine_config={
        "image_registry": "us-central1-docker.pkg.dev",
        "image_repo": "vertex-built",
        "job_name": "example-job",
        "machine_type": "n1-standard-4",
        # "accelerator_type": "NVIDIA_TESLA_T4",
        # "accelerator_count": 1,
        # "staging_bucket": "gs://your-bucket",
        # "network": "projects/xxx/global/networks/yyy",
        # "labels": {"env": "dev"},
    },
    project_id="your-gcp-project",
    location="us-central1",
    service_account="sa-name@your-gcp-project.iam.gserviceaccount.com",  # runtime identity for the job
    credentials_provider=gcp_credentials_from_json,  # optional; if None, ADC is used
)

# await runner.run_script("echo hello")
```

Notes:
- Authentication: provide a single `credentials_provider: () -> Optional[Credentials]`. If it returns None, Application Default Credentials (ADC) are used. The `service_account` field controls the runtime identity on the Vertex job.
- Container image is built from schematics and pushed to Artifact Registry using `_a_docker_push`.
- This runner executes the prepared script via a base64 runner inside the container on Vertex AI Custom Job.
