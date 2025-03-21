from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Callable

from pinjected import *
from pydantic import BaseModel
from returns.result import ResultE, safe
from beartype import beartype

@injected
@safe
def safe_read_file(p: Path) -> str:
    return p.read_text()


class RyeSchema(BaseModel):
    type: Literal["rye"]


class PoetrySchema(BaseModel):
    type: Literal["poetry"]


class UVSchema(BaseModel):
    type: Literal["uv"]


class RequirementsTxtSchema(BaseModel):
    type: Literal["requirements.txt"]


class SetupPySchema(BaseModel):
    type: Literal["setup.py"]


class ReadmeSchema(BaseModel):
    type: Literal["README.md"]


class IdentifiedSchema(BaseModel):
    schema: RyeSchema | PoetrySchema | UVSchema | RequirementsTxtSchema | SetupPySchema | ReadmeSchema
    justification: str

@dataclass
class Test:
    a:int
    x:int = field(kw_only=True) # this marks x to be not a member of constructor.


@injected
@dataclass
class ProjectContext:
    _safe_read_file: Callable[[Path], ResultE[str]]
    repo: Path

    def __post_init__(self):
        self.setup_py = self._safe_read_file(self.repo / "setup.py")
        self.requirements_txt = self._safe_read_file(self.repo / "requirements.txt")
        self.pyproject = self._safe_read_file(self.repo / "pyproject.toml")
        self.readme = self._safe_read_file(self.repo / "README.md")


@dataclass
class SetupScriptWithDeps:
    cxt: ProjectContext
    script: str
    env_deps: list[str]

f"""
Using this dependency injection system, the problem is that 
1. we cant express the constructor signature easily
2. we can't express the function signature easily.

2 can be mitigated by using a class for the function.
but 1 is a bit tricky.
we need to have something like this to enable full type hinting...

class SomeClass:
    pass

@dataclass
class SomeClassConstructor:
    dep1:int
    dep2:int
    def __call__(self, *args, **kwargs):
        return SomeClass(dep1,dep2,,,)
        
What can i do? Maybe i develop a plugin for pycharm to support type hinting for injected functions.
Yeah someday I could do that...

"""


@injected
@beartype
async def a_identify_project_schema(new_ProjectContext, logger, a_cached_llm_for_ml_nexus, /, repo: Path)->IdentifiedSchema:
    cxt: ProjectContext = new_ProjectContext(repo=repo)
    """
    I could write auto detection code, but why not just ask the llm?
    """
    prompt = f"""
We are setting up a newly cloned github repository.
Can you determine the project schema from the following files?

--- setup.py ---
{cxt.setup_py}
--- requirements.txt ---
{cxt.requirements_txt}
--- pyproject.toml ---
{cxt.pyproject}
--- README.md ---
{cxt.readme}
-------------------------------
only setup.py exists -> setup.py
only requirements.txt exists -> requirements.txt
only pyproject.toml exists -> poetry or rye or uv
if no poetry like field in pyproject.toml -> rye
only README.md exists -> README.md
both setup.py and requirements.txt exist -> setup.py
any uv related settings to uv in pyproject.toml -> uv
[tool.uv] exists in pyproject.toml -> uv
If the pyproject.toml explicitly states which tool to use in comment, please follow that.
    """
    logger.info(prompt)
    res: IdentifiedSchema = await a_cached_llm_for_ml_nexus(
        prompt,
        response_format=IdentifiedSchema
    )
    return res


class RequirementsTxt:
    text: str
    justification: str


@injected
async def a_generate_requirements_txt_from_readme(a_cached_llm_for_ml_nexus, /, readme: str):
    prompt = f"""
Please generate a requirements.txt from the following README.md:
```markdown
{readme}
```
"""
    return a_cached_llm_for_ml_nexus(prompt, response_format=RequirementsTxt)


@injected
async def a_schema_to_setup_script_with_deps(
        a_generate_requirements_txt_from_readme,
        new_ProjectContext,
        /,
        schema: IdentifiedSchema,
        repo: Path,
):
    cxt = new_ProjectContext(repo=repo)
    match schema.schema:
        case RyeSchema():
            script = "rye sync"
            deps = ['rye']
        case PoetrySchema():
            script = "poetry install"
            deps = ['poetry']
        case UVSchema():
            script = "uv sync"
            deps = ['uv']
        case RequirementsTxtSchema():
            script = "pip install -r requirements.txt"
            deps = ['pyvenv','requirements.txt']
        case SetupPySchema():
            script = "pip install -e ."
            deps = ['pyvenv','setup.py']
        case ReadmeSchema():
            # let's generate requirements.txt
            src = cxt.readme.unwrap()
            # is it IO[str]? or str? idk...
            req_txt = await a_generate_requirements_txt_from_readme(src)
            # let's use hear document
            script = f"""pip install -r - <<EOF
{req_txt.text}
EOF"""
            deps = ['pyvenv']
        case _:
            raise NotImplementedError(f"schema:{schema.schema} is not implemented yet")
    return SetupScriptWithDeps(cxt=cxt, script=script, env_deps=deps)


@injected
async def a_prepare_setup_script_with_deps(
        a_identify_project_schema,
        a_schema_to_setup_script_with_deps,
        /,
        repo: Path
):
    schema = await a_identify_project_schema(repo)
    return await a_schema_to_setup_script_with_deps(schema, repo)


test_identify_project_schema: IProxy = a_identify_project_schema(
    test_repo := Path(".")
)
test_schema_to_setup_script_with_deps: IProxy = a_schema_to_setup_script_with_deps(
    test_identify_project_schema, test_repo
)
test_prepare_setup_script_with_deps: IProxy = a_prepare_setup_script_with_deps(test_repo)

__meta_design__ = design(

)