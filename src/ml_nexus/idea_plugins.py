import shlex
from dataclasses import dataclass

from pinjected import *
from pinjected.helper_structure import IdeaRunConfiguration
from pinjected.module_inspector import ModuleVarSpec
from pinjected.module_var_path import ModuleVarPath

from ml_nexus.project_structure import IRunner
import pinjected


@injected
async def _run_command_with_env(env: IRunner, tgt_var_path: str):
    cmd = f"python -m pinjected run {tgt_var_path}"
    if hasattr(env, "pinjected_additional_args"):
        for k, v in env.pinjected_additional_args.items():
            cmd += f" --{k}={shlex.quote(v)}"
    return await env.run(cmd)


# this is the entry point
run_command_with_env = _run_command_with_env(
    injected("target_environment"),
    injected("target_variable"),
)


@injected
def add_configs_from_envs(
    command_environments: list[ModuleVarPath],
    interpreter_path,
    default_working_dir,
    /,
    tgt: ModuleVarSpec,
) -> list[IdeaRunConfiguration]:
    res = []
    tgt_script_path = ModuleVarPath(tgt.var_path).module_file_path
    for env in command_environments:
        if isinstance(env, str):
            env = ModuleVarPath(env)
        var_name = tgt.var_path.split(".")[-1]

        res.append(
            IdeaRunConfiguration(
                name=f"submit {var_name} to env: {env.var_name}",
                script_path=str(pinjected.__file__).replace(
                    "__init__.py", "__main__.py"
                ),
                interpreter_path=interpreter_path,
                arguments=[
                    "run",
                    "ml_nexus.idea_plugins.run_command_with_env",
                    f"--meta-context-path={tgt_script_path}",
                    f"--target-environment={{{env.path}}}",
                    f"--target-variable={tgt.var_path}",
                ],
                working_dir=default_working_dir.value_or("."),
            )
        )
    return res


@injected
@dataclass
class TestEnv(IRunner):
    async def run(self, cmd, *args, **kwargs):
        print(f"running command: {cmd}")
        return 0


TEST_ENV: Injected = TestEnv()


@instance
async def test_run():
    print("hello")


__meta_design__ = providers(
    custom_idea_config_creator=add_configs_from_envs,
) + instances(command_environments=[ModuleVarPath("ml_nexus.idea_plugins.TEST_ENV")])
