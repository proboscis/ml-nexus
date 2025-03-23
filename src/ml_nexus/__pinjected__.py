from pinjected import DesignSpec, SimpleBindSpec
from pinjected.di.design_spec.protocols import BindSpec

def type_validator(t):
    def validator(value):
        if not isinstance(value, t):
            return f"Expected type {t}, got {type(value)}"
    return validator

__design_spec__ = DesignSpec.new(
    ml_nexus_default_docker_host_upload_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory on the host where files are uploaded to the docker container."""
    ),
    ml_nexus_default_docker_host_resource_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory on the host where resources are stored."""
    ),
    ml_nexus_default_docker_host_cache_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory on the host where cache is stored."""
    ),
    ml_nexus_default_docker_host_source_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory on the host where source files are stored."""
    ),
    ml_nexus_source_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory where source files are stored."""
    ),
    ml_nexus_resource_root = SimpleBindSpec(
        validator=type_validator(Path),
        documentation="""The default root directory where resources are stored."""
    ),
    storage_resolver = SimpleBindSpec(
        validator=type_validator(IStorageResolver),
        documentation="""The default storage resolver."""
    )
)

