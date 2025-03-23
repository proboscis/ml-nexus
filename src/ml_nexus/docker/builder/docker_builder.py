import asyncio
from dataclasses import replace, dataclass, field
from typing import Callable, Awaitable, Optional, Annotated

from ml_nexus.assertions import is_async_context_manager

from beartype import beartype
from beartype.vale import Is

from ml_nexus.docker.builder.builder_utils.building import BuildImageWithMacro
from ml_nexus.docker.builder.macros.macro_defs import Macro, Block, RCopy
from ml_nexus.rsync_util import RsyncArgs


@dataclass
class DockerBuilderComponent:
    macros: list[Macro] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)

    def add_macro(self, macro: Macro) -> "DockerBuilderComponent":
        return replace(self, macros=self.macros + [macro])

    def add_script(self, script: str) -> "DockerBuilderComponent":
        return replace(self, scripts=self.scripts + [script])

    def __add__(self, other: "DockerBuilderComponent") -> "DockerBuilderComponent":
        return replace(self, macros=self.macros + other.macros, scripts=self.scripts + other.scripts)


@dataclass
class DockerBuilder:
    """
    TODO make it possible to declare cache mounts for optimization.
    """
    _logger: object
    _build_image_with_macro: BuildImageWithMacro
    _build_entrypoint_script: Callable[[list[str]], Awaitable[str]]
    _get_macro_entrypoint_installation: Callable[[str], Awaitable[Macro]]

    base_image: str
    base_stage_name: str = "base"
    macros: list[Macro] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    name: Optional[str] = None
    metadata: dict = None
    platform: str = "linux/amd64"


    def __post_init__(self):
        """
        Docker builder is stateful, due to its macro being ContextManager
        :return:
        """
        self.assert_macros_not_acontextmanager(self.macros)
        self.build_lock = asyncio.Lock()
        self.built = asyncio.Event()
        if self.name is None:
            self.name = self.base_image.replace("/", "_").replace(":", "_")
            self._logger.warning(f"Name not provided for DockerBuilder, using base_image as name: {self.name}")
        if self.metadata is None:
            self.metadata = {}


    def assert_macros_not_acontextmanager(self,macro):
        def dfs(macro):
            match macro:
                case acon if is_async_context_manager(acon):
                    raise ValueError(f"Macro {acon} is an async context manager, which is not supported in DockerBuilder")
                case [*macros]:
                    for m in macros:
                        dfs(m)
                case str() | Block() | RsyncArgs() | RCopy():
                    pass
                case f if callable(f):
                    pass
                case unknown:
                    raise ValueError(f"Unknown type {type(unknown)} in macro {unknown}")
        dfs(macro)

    async def a_build(self, tag: str, use_cache=True) -> str:
        async with self.build_lock:
            if self.built.is_set():
                self._logger.warning(f"Image already built, skipping build for {self.name}")
                return tag
            script = await self._build_entrypoint_script(
                self.scripts
            )
            self._logger.info(f"Generated Entrypoint script: \n{script}")
            macros = [
                f"FROM {self.base_image} as {self.base_stage_name}",
                *self.macros,
                await self._get_macro_entrypoint_installation(script)
            ]

            res = await self._build_image_with_macro(
                macros,
                tag,
                use_cache=use_cache,
                build_id=self.name,
                options=" --platform " + self.platform
            )
            self.built.set()
            return res


    def add_macro(self, macro: Macro) -> "DockerBuilder":
        return replace(self, macros=self.macros + [macro])

    @beartype
    def add_script(self, script: str) -> "DockerBuilder":
        return replace(self, scripts=self.scripts + [script])

    @beartype
    def add_name(self, name: str) -> "DockerBuilder":
        return replace(self, name=name)

    async def a_entrypoint_script(self):
        return await self._build_entrypoint_script(self.scripts)

    def __add__(self, other: DockerBuilderComponent) -> "DockerBuilder":
        return replace(self, macros=self.macros + other.macros, scripts=self.scripts + other.scripts)

    def add_metadata(self, **kwargs):
        return replace(self, metadata={**self.metadata, **kwargs})


VenvDockerBuilder = Annotated[
    DockerBuilder,
    Is[lambda x: 'venv_path' in x.metadata]
]


@dataclass
class DockerService:
    builder: DockerBuilder
    tag_name_provider: Callable[[], str]
    docker_tag_pusher: Callable[[str], Awaitable]
    use_cache: bool = True

    async def a_build_and_push(self):
        image = await self.builder.a_build(self.tag_name_provider(), use_cache=self.use_cache)
        await self.docker_tag_pusher(image)
        return image
