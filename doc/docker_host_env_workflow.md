# DockerHostEnv Workflow: Building, Syncing, and Running

## Overview

The `DockerHostEnvironment` class provides a comprehensive solution for executing scripts and managing Docker containers on remote hosts. This document explains how the Docker host is set and used during the `run_script()` process, with a focus on building, syncing, and running operations.

> **Note**: Docker build commands can now be executed using different Docker contexts (like `zeus`, `colima`, etc.) via the `ml_nexus_docker_build_context` injection point.

## Architecture Overview

```mermaid
graph TB
    subgraph "Local Machine"
        DHE[DockerHostEnvironment]
        DB[DockerBuilder]
        DHM[DockerHostMounter]
        SR[IStorageResolver]
    end
    
    subgraph "Remote Docker Host"
        SSH[SSH Server]
        Docker[Docker Engine]
        RFS[Remote Filesystem]
        DC[Docker Container]
    end
    
    DHE --> |"1. prepare()"|DB
    DHE --> |"2. prepare()"|DHM
    DHE --> |"3. run_script()"|SSH
    
    DB --> |"Build Image"|Docker
    DHM --> |"rsync files"|RFS
    SR --> |"Resolve paths"|DHM
    
    SSH --> |"docker run"|Docker
    Docker --> |"Mount volumes"|RFS
    Docker --> |"Execute"|DC
    
    style DHE fill:#f9f,stroke:#333,stroke-width:4px
    style Docker fill:#bbf,stroke:#333,stroke-width:4px
```

## Key Components

### 1. DockerHostEnvironment

The main orchestrator that coordinates all Docker operations on a remote host.

**Key Attributes:**
- `docker_host`: The hostname or IP address of the remote Docker host
- `docker_builder`: Handles Docker image building
- `mounter`: Handles file synchronization to the remote host
- `sync_lock`: Ensures synchronization happens only once
- `image_tag`: The Docker image tag to use

### 2. DockerHostMounter

Responsible for synchronizing project files to the remote Docker host using rsync.

**Key Methods:**
- `rsync_ids_to_root()`: Syncs project directories to the host
- `prepare_resource()`: Prepares resources for a specific project

### 3. DockerBuilder

Builds Docker images using a macro-based system that supports various operations.

**Key Features:**
- Macro-based Dockerfile generation
- BuildKit support for efficient builds
- File staging with hardlink optimization

## Workflow Sequence

```mermaid
sequenceDiagram
    participant User
    participant DHE as DockerHostEnvironment
    participant DB as DockerBuilder
    participant DHM as DockerHostMounter
    participant RH as Remote Host
    
    User->>DHE: run_script(script)
    
    activate DHE
    DHE->>DHE: prepare()
    
    Note over DHE: Check if already synced
    
    alt Not synced
        DHE->>DB: a_build(image_tag)
        activate DB
        DB->>DB: Generate Dockerfile
        DB->>DB: Stage build context
        DB->>RH: docker build
        RH-->>DB: Image built
        DB-->>DHE: image_tag
        deactivate DB
        
        DHE->>DHM: prepare_resource()
        activate DHM
        DHM->>DHM: resolve_project_dirs()
        
        loop For each project directory
            DHM->>RH: mkdir -p directory
            DHM->>RH: rsync files
        end
        
        DHM-->>DHE: Resources synced
        deactivate DHM
    end
    
    DHE->>DHE: base64_encode(script)
    DHE->>DHE: build_docker_cmd()
    DHE->>RH: ssh docker_host "docker run ..."
    RH-->>DHE: Execution result
    DHE-->>User: Result
    deactivate DHE
```

## Detailed Process Flow

### 1. Docker Host Setting

The Docker host is set during the initialization of `DockerHostEnvironment`:

```python
@dataclass
class DockerHostEnvironment:
    docker_host: str  # Hostname or IP of the remote Docker host
    # ... other attributes
```

The `docker_host` parameter determines:
- Where SSH commands are sent
- Where Docker commands are executed
- Where files are synchronized

### 2. Building Process

```mermaid
graph LR
    subgraph "Build Process"
        A[Start Build] --> B[Process Macros]
        B --> C[Generate Dockerfile]
        C --> D[Stage Build Context]
        D --> E[Execute docker build]
        E --> F[Tag Image]
    end
    
    subgraph "Macro Types"
        M1[RCopy - Copy files]
        M2[RsyncArgs - Rsync directories]
        M3[Script - Add scripts]
        M4[PackageBlock - Install packages]
    end
    
    B --> M1
    B --> M2
    B --> M3
    B --> M4
```

**Key Steps:**
1. **Macro Processing**: Converts high-level operations into Dockerfile instructions
2. **Context Staging**: Creates a temporary directory with all required files
3. **Image Building**: Executes `docker build` on the remote host
4. **Caching**: Uses Docker's build cache for efficiency

### 3. Syncing Process

```mermaid
graph TD
    subgraph "Sync Process"
        S1[Identify Project Dirs] --> S2[Resolve Local Paths]
        S2 --> S3[Create Remote Dirs]
        S3 --> S4[Rsync Files]
        S4 --> S5[Set Permissions]
    end
    
    subgraph "Rsync Options"
        O1["-avH" - Archive, verbose, hardlinks]
        O2["--delete" - Remove extra files]
        O3["--exclude" - Skip patterns]
    end
    
    S4 --> O1
    S4 --> O2
    S4 --> O3
```

**Rsync Command Example:**
```bash
rsync -avH --delete \
  --exclude="*.pyc" \
  --exclude="__pycache__" \
  /local/project/path/ \
  remote_host:/resources/project_id/
```

### 4. Running Process

```mermaid
graph LR
    subgraph "Script Execution"
        R1[Encode Script] --> R2[Build Docker Command]
        R2 --> R3[SSH to Host]
        R3 --> R4[Run Container]
        R4 --> R5[Execute Script]
        R5 --> R6[Return Result]
    end
    
    subgraph "Docker Options"
        D1[Volume Mounts]
        D2[Environment Vars]
        D3[Working Directory]
        D4[User/Group]
    end
    
    R2 --> D1
    R2 --> D2
    R2 --> D3
    R2 --> D4
```

**Docker Run Command Structure:**
```bash
ssh docker_host "docker run \
  -v /resources:/placement/resources \
  -w /placement/workdir \
  -e ENV_VAR=value \
  --rm \
  image_tag \
  python -c 'base64_decoded_script'"
```

## Key Methods Explained

### prepare()

The `prepare()` method orchestrates both building and syncing:

```python
async def prepare(self):
    async with self.sync_lock:
        if self.synced.is_set():
            return self.image_tag
        else:
            # Build Docker image
            image = await self.docker_builder.a_build(self.image_tag, use_cache=True)
            
            # Sync files to remote host
            await self.mounter.prepare_resource(self.docker_host, self.project)
            
            self.synced.set()
            return image
```

### run_script()

Executes a Python script inside a Docker container on the remote host:

```python
async def run_script(self, py_script: str, **kw):
    # Ensure resources are prepared
    await self.prepare()
    
    # Encode script for safe transmission
    py_script_b64 = self.base64_encode_script(py_script)
    
    # Build Docker command with all options
    cmd = self.build_docker_cmd(py_script_b64, **kw)
    
    # Execute via SSH on remote host
    await self._a_system_parallel(f'ssh {self.docker_host} {cmd}')
```

## Volume Mounting Strategy

```mermaid
graph TD
    subgraph "Host Filesystem"
        HR[/resources/]
        HP1[/resources/project1/]
        HP2[/resources/project2/]
    end
    
    subgraph "Container Filesystem"
        CR[/placement/resources/]
        CP1[/placement/resources/project1/]
        CP2[/placement/resources/project2/]
        WD[/placement/workdir/]
    end
    
    HR --> |"Mount"|CR
    HP1 --> |"Available as"|CP1
    HP2 --> |"Available as"|CP2
    
    style HR fill:#ffa,stroke:#333,stroke-width:2px
    style CR fill:#aff,stroke:#333,stroke-width:2px
```

## Performance Optimizations

1. **Sync Lock**: Prevents redundant synchronization operations
2. **Hardlinking**: Uses hardlinks for file staging when possible
3. **Parallel Rsync**: Synchronizes multiple directories concurrently
4. **Build Cache**: Leverages Docker's build cache
5. **Selective Sync**: Only syncs required project directories

## Security Considerations

1. **SSH Authentication**: Requires proper SSH key configuration
2. **Docker Permissions**: Remote user must have Docker access
3. **File Permissions**: Maintains proper file ownership during sync
4. **Network Security**: All communication happens over SSH

## Example Usage

```python
# Initialize DockerHostEnvironment
env = DockerHostEnvironment(
    docker_host="remote-server.example.com",
    docker_builder=docker_builder,
    project=project_definition,
    placement=placement_config,
    mounter=docker_host_mounter,
    image_tag="myapp:latest"
)

# Run a script (handles building, syncing, and execution)
await env.run_script("""
import pandas as pd
df = pd.read_csv('/placement/resources/data.csv')
print(df.head())
""")
```

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Verify SSH key configuration
   - Check network connectivity
   - Ensure remote host is accessible

2. **Docker Build Failed**
   - Check Dockerfile syntax
   - Verify base image availability
   - Review build context size

3. **Rsync Failed**
   - Ensure rsync is installed on both hosts
   - Check file permissions
   - Verify disk space availability

4. **Container Execution Failed**
   - Check Docker daemon status
   - Verify image exists
   - Review container logs

## Docker Build Context Support

### Docker Contexts

Docker contexts allow you to switch between different Docker endpoints without modifying your commands. The `a_build_docker` function now supports building images using any configured Docker context.

### Available Docker Contexts

To list available Docker contexts:
```bash
docker context ls
```

Example output:
```
NAME              DESCRIPTION                               DOCKER ENDPOINT
colima *          colima                                    unix:///Users/user/.colima/default/docker.sock
default           Current DOCKER_HOST based configuration   unix:///var/run/docker.sock
zeus                                                        tcp://zeus:2375
```

### Implementation

The `a_build_docker` function now accepts a `ml_nexus_docker_build_context` parameter:

```python
@injected
async def a_build_docker(
        a_system,
        ml_nexus_debug_docker_build,
        ml_nexus_docker_build_context,  # Docker context name
        logger,
        /,
        tag,
        context_dir,
        options: str,
        push: bool = False,
        build_id=None
):
    # Build docker command with context if specified
    docker_cmd = "docker"
    if ml_nexus_docker_build_context:
        logger.info(f"Using Docker context: {ml_nexus_docker_build_context}")
        docker_cmd = f"docker --context {ml_nexus_docker_build_context}"
    
    # Execute docker build
    build_cmd = f"{docker_cmd} build {options} -t {tag} {context_dir}"
    await a_system(build_cmd)
```

### Configuration

The Docker build context can be configured in two ways:

1. **Environment Variable** (default approach):
   ```bash
   export ML_NEXUS_DOCKER_BUILD_CONTEXT=zeus
   ```

2. **Design Override** (for project-specific configuration):
   ```python
   __meta_design__ = design(
       # Override the default to use a specific Docker context
       ml_nexus_docker_build_context="zeus",
   )
   ```

The design override takes precedence over the environment variable.

### Usage Example

When you build Docker images with ml-nexus, they will automatically use the configured context:

```python
# With ML_NEXUS_DOCKER_BUILD_CONTEXT=zeus set in environment
# All Docker builds will use: docker --context zeus build ...

# Or override in your project:
from ml_nexus import design

__meta_design__ = design(
    ml_nexus_docker_build_context="colima",  # Use colima instead of zeus
)

# Now builds will use: docker --context colima build ...
```

### SSH-based Remote Builds

For scenarios where Docker contexts are not configured, a separate function `a_build_docker_ssh_remote` is available for SSH-based remote builds:

```python
await a_build_docker_ssh_remote(
    tag="myimage:latest",
    context_dir="/path/to/context",
    options="--no-cache",
    remote_host="build-server.example.com"
)
```

### Build Context Synchronization

For remote builds, the build context needs to be synchronized efficiently:

```mermaid
sequenceDiagram
    participant Local as Local Machine
    participant BH as Build Host
    participant RH as Runtime Host
    
    Local->>Local: Prepare build context
    Local->>BH: rsync build context
    BH->>BH: docker build
    
    alt Push to Registry
        BH->>Registry: docker push
        RH->>Registry: docker pull
    else Direct Transfer
        BH->>RH: docker save/load
    end
    
    RH->>RH: docker run
```

## Conclusion

The DockerHostEnvironment provides a robust solution for remote Docker execution with:
- Efficient file synchronization using rsync
- Flexible Docker image building with macros
- Secure remote execution via SSH
- Performance optimizations for large projects
- **Implemented**: Docker context support via `ml_nexus_docker_build_context` (supports `zeus`, `colima`, etc.)
- **Implemented**: SSH-based remote Docker builds via `a_build_docker_ssh_remote`

This architecture enables seamless development and deployment workflows across distributed computing resources.