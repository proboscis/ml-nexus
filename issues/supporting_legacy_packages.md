# ビルド時に特定の前提を要求するパッケージが散見される
特にtorchなどを要求する場合が多い。
uvでこれらに対応するには。
問題のパッケージを以下の様に分離する
```toml
[project.optional-dependencies]
build = [
  "torch==2.3.0",
  "cython",
  "numpy>=1.17"
]
basicsr = [
  "basicsr==1.3.5"
]
[tool.uv]
no-build-isolation-package = ["basicsr"]
```
そして、schematicsのinit_scriptをhackする

```python
schematic = schematic_universal(project)
@injected
async def a_hack_uv_sync_with_torch_dep_package(lines: list[str]) -> list[str]:
    # This hack works!
    res = []
    for line in lines:
        if 'uv sync' in line:
            res += [
                "uv sync --extra build",
                "uv sync --extra build --extra basicsr"
            ]
        else:
            res.append(line)
    return res
hacked_schematics = schematic.a_map_scripts(a_hack_uv_sync_with_torch_dep_package).await__()
```